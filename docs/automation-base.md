# CCC 自动化基建 · 出卡 / 放行 / 验收（T52）

> 状态：现行（2026-08-04 T52 落地）· 关联：`scripts/new-card.sh` · `deploy/release.sh` · `scripts/verify-shell.sh`
> 任务卡 = 唯一事实源（`docs/dispatch/T<n>-<slug>.md`）；本页是三条自动化链路的用法与门禁说明。

## 一、链路总览

```
出卡（new-card.sh）→ 执行（Engine 派发/人工）→ 验收（Codex）→ 放行（release.sh）→ 部署上线
   └─ 卡头门禁（validate 卡头字段/状态/编号唯一；CI + pre-commit 双闸）→ 不合规卡直接打回
   └─ 复验（verify-shell.sh）→ 部署后一键复验壳六场景
```

| 工具 | 路径 | 职责 |
|------|------|------|
| 出卡模板 | `scripts/new-card.sh` | 生成标准卡骨架；编号自增 + 查重；写卡后联动 validate 门禁 |
| 一键放行 | `deploy/release.sh` | 2017 pull → 三服务 kickstart → 自动验证 → 放行报告 → 卡头关闭 |
| 壳复验 | `scripts/verify-shell.sh` | 六场景 headless 复验（免登录/流式/思考折叠/切界面/左栏项目/零 error） |
| 卡头门禁 | `server/board/validate.py` | 字段/状态/编号唯一/编号一致；CI + pre-commit 双闸 |

## 二、出卡模板 `scripts/new-card.sh`

```bash
scripts/new-card.sh --title "任务标题" \
  [--project ccc] [--executor "Claude Code"] [--acceptance Codex] \
  [--related "关联文本"] [--dispatch engine|manual] \
  [--dispatch-dir docs/dispatch] [--id T90-test] [--slug xxx] [--dry-run]
```

- 命名 `T<序号>-<slug>.md`：序号扫描目标目录 `T<digits>` 最大值 +1 自增；`--id` 显式覆盖并查重（数字前缀冲突即拒）。
- 卡头：`关联 / 执行体 / 验收 / 状态 / 派发 / 项目 / 日期`；骨架节：目标 / 红线 / 范围 / 步骤 / 验收标准 / 回写要求 / 回写区。
- 零硬编码：项目/执行体/验收/关联/派发/python 均可用参数或 `CCC_*` 环境变量覆盖。
- **联动门禁**：写卡后自动 `python -m server.board.validate <dir>`，不合规卡删除并报错（自动查重）。

## 三、一键放行 `deploy/release.sh`

```bash
deploy/release.sh [<commit|tag>] \
  [--repo <path>] [--dispatch-dir <dir>] [--card T52] [--port 7788] \
  [--simulate] [--no-pull] [--no-kickstart] [--skip-conversation] [--json]
```

- **生产模式**（默认，在 2017 对生产仓执行）：
  1. `git fetch + checkout` 目标 commit/tag（2017 pull）；
  2. `launchctl kickstart -k` 三常驻服务（web-server / engine / board-scheduler）；
  3. 自动验证：`/health`、`/board/states`、`/projects`、`/session` 或免登录直连、**一次对话**（SSE 流式：完整回复 OK；超时但流式已通 FLOWING 视为在线；无事件/脑错误 FAIL）；
  4. 输出放行报告（stdout + `--report` 文件；`--json` 输出 JSON）；
  5. 验证全过后卡头状态自动更新「已关闭」（`--card` 指定，或按目标 commit 在回写区自动识别）。
- **模拟模式** `--simulate`（M1 模拟 / 临时目录测试）：跳过 git / kickstart / 在线检查；做 config.env 只读检查 + 看板可见性（`server.board.export` 自 `--dispatch-dir` 导出检索目标卡）+ 卡头关闭。**不碰生产**。
- config.env 只读检查：读运行参数，绝不写入。
- **测试流程任务先行**：`--dispatch-dir` 指向临时目录即可在隔离环境跑通 出卡→执行→验收→放行→看板可见→删除无残留，不动生产 `docs/dispatch`。

## 四、壳复验 `scripts/verify-shell.sh`

```bash
scripts/verify-shell.sh                    # 默认连 127.0.0.1:7788（已部署壳复验）
scripts/verify-shell.sh --local            # 起本地测试服务（随机端口；无大脑，默认跳对话场景）
scripts/verify-shell.sh --skip-conversation # 跳过对话类场景
```

六场景（API 级断言，零第三方依赖）：
1. **免登录直进**：`/health` auth_required=false + 未带 token 直连 `/projects` 200；
2. **左栏业务项目**：`/projects` 返回真实业务项目（非任务卡分组名）；
3. **零 console error**（服务端侧）：9 个壳端点全 2xx/3xx，无 5xx/401；
4. **流式**：`POST /conversation {stream:true}` → SSE 事件流动；
5. **思考折叠无空占位**：前端 `message.js` 空思考守卫（`!thinkingBuf` 不建折叠）+ 流式 thinking 事件（若出现）内容非空；
6. **切界面不断流**：长轮询增量契约（`GET /conversation?after=<seq-2>` 增量无缺口 = UI 切走再切回拉取不丢内容）。

对话类场景用隔离 `thread_id`（不污染生产历史）；脑忙（503/超时）重试 3 次后 SKIP（非壳缺陷）。
浏览器 DOM 层（折叠渲染/console 具体报错）依赖 Playwright（M1 环境）；本脚本覆盖服务端 + 前端守卫的机器可验部分。

## 五、卡头门禁（CI + pre-commit 双闸）

- `server/board/validate.py` 校验：卡头必需字段（关联/执行体/状态/日期）、状态五态、编号唯一（卡头 ID 重复报重）、编号一致（卡头 `T<N>` 与文件名数字前缀一致）。
- 历史卡把 关联/执行体/状态/日期 分布在多个 `>` 行——validate 与 loader 同款合并解析全部 `>` 行，不误报。
- R/X 变体卡（`T1` 与 `T1-R-...`）数字前缀允许共存，按卡头 ID 判重。
- CI：`.github/workflows/ci.yml` `card-validate` job（ubuntu + python3.12，`python -m server.board.validate docs/dispatch`）。
- pre-commit：`.pre-commit-config.yaml` `card-validate` hook（`docs/dispatch/` 改动即校验）。
- 坏卡演示：编号重复 / 卡头与文件名编号不一致 → validate exit 1 拦截；合规卡（new-card.sh 生成）exit 0。

## 六、端到端验证（T9x-test 临时目录，不碰生产）

```bash
# 1 出卡          2 执行完成           3 验收通过（Codex）     4 放行
new-card.sh --id T90-test --dispatch-dir /tmp/x/dispatch
#   → 状态 待分派
#   → 状态 已回写
deploy/release.sh --simulate --dispatch-dir /tmp/x/dispatch --card T90-test
#   → 看板可见性 PASS + 卡头关闭 已关闭 + 放行报告
# 5 删除测试卡无残留
rm /tmp/x/dispatch/T90-test-t52.md   # 重导 board.js 无 T90-test 残留
```

跑通后才允许正式任务走该链路；正式放行由 Codex 在 2017 生产链路上执行。
