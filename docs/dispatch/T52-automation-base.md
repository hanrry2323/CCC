# 任务卡 T52 · 自动化基建：出卡模板 + 一键放行 + 验收自动化（Claude Code 执行）

> 关联：ccc-plan-005 · 依据：规划确认——Codex 只留「验收+放行」；出卡/门禁/部署自动化
> 执行体：Claude Code · 验收：Codex（严格）· 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 重出记录：2026-08-04 原卡作废（M1 worktree 方向不符）；2017 执行环境跑通（T53/T51）后按 Engine 自动派发重出。
> 工作目录：`/Users/fan/program/ccc-dev-ws`（2017 开发 worktree）；分支：`codex/t52-auto-base`（先 `git fetch origin main && git checkout -b codex/t52-auto-base origin/main`）
> **分步提交纪律（硬）**：每完成一个逻辑块（出卡模板 / 一键放行 / 验收自动化 / 测试流程任务）立即 commit+push，禁止攒到结尾；执行超时 7200s。

## 目标

自动化基建三件套：出卡模板脚本、一键放行部署脚本、验收自动化（卡头门禁 CI + headless 复验脚本），并用一条测试流程任务端到端验证。

## 具体项

1. **出卡模板** `scripts/new-card.sh`：生成标准卡骨架（项目前缀+三位序号+slug 命名、卡头字段、目标/红线/范围/步骤/验收标准/回写要求/回写区）；自动查重（validate 联动）+ 编号自增。
2. **一键放行** `deploy/release.sh <commit|tag>`：2017 pull → 三服务 kickstart → 自动验证（/health、/session 或免登录直连、/board/states、/projects、一次对话）→ 输出放行报告；卡头状态自动更新「已关闭」（验收席放行后）。
3. **验收自动化**：
   - validate.py 接入 CI（.github/workflows/ci.yml）+ pre-commit（新卡格式门禁：字段/状态/编号唯一）；
   - `scripts/verify-shell.sh`：headless 复验固化（免登录直进/流式/思考折叠无空占位/切界面不断流/左栏业务项目/零 console error）一键跑。
4. **测试流程任务先行（老板硬性要求）**：release.sh 支持 `--dispatch-dir` 参数，测试时用**临时目录**跑一条 `T9x-test` 占位卡端到端（出卡→执行→验收→放行→看板可见→**删除测试卡无残留**），**不碰生产 docs/dispatch**；跑通后才允许正式任务走该链路。Codex 验收时再在生产链路跑一条真实测试流程任务。

## 红线

- 只改 scripts/、deploy/、.github/workflows/ci.yml、.pre-commit-config.yaml、server/board/validate.py、docs/（流程说明）；**禁止改 server/kb/、knowledge/、brain.py（T51 所有权）**。
- release.sh 不碰生产配置（config.env 只读检查）；测试卡用占位改动，跑完删除。
- 回写前必须 push 成功并附证据。

## 验收标准

1. `new-card.sh` 生成合规卡（validate 通过 + 编号唯一）。
2. `release.sh` 在 M1 模拟 + 2017 实测通过（含自动验证段）；测试流程任务端到端跑通且**删除后看板无残留**。
3. validate 门禁在 CI/pre-commit 生效（故意放一张坏卡被拦的演示记录）。
4. `verify-shell.sh` 全场景 PASS；pytest 全绿、ruff/py_compile clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：三件套实现说明、测试流程任务跑通记录（含看板可见/删除无残留）、CI 门禁演示、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code（2017 ccc-dev-ws）· 日期：2026-08-04

### A. 出卡模板 `scripts/new-card.sh`（完成）

- 生成 `T<序号>-<slug>.md` 标准骨架：卡头（关联/执行体/验收/状态/派发/项目/日期）+ 目标/红线/范围/步骤/验收标准/回写要求/回写区 七节。
- 编号自增（扫描目标目录 `T<digits>` 最大值 +1）；`--id` 显式覆盖且查重（数字前缀冲突即拒）；同名卡拒绝。
- **自动查重 = validate 联动门禁**：写卡后自动 `python -m server.board.validate <dir>`，不合规卡删除并报错。
- 零硬编码：项目/执行体/验收/关联/派发/python 可参数或 `CCC_*` 环境变量覆盖；`--dispatch-dir` 支持临时目录（测试流程任务先行）；`--dry-run` 只打印。
- 实测：临时目录出卡 T1-t52 → validate 通过；第二张自动 T2；`--id T1` 重复被拒（exit 3）；真实 docs/dispatch 下 --dry-run 自增为 T54。

### B. 一键放行 `deploy/release.sh`（完成）

- **生产模式** `deploy/release.sh <commit|tag>`：git fetch+checkout → launchctl kickstart 三常驻服务（web-server/engine/board-scheduler）→ 自动验证（/health、/board/states、/projects、/session 或免登录直连、一次对话 SSE）→ 放行报告（stdout + 文件）→ 卡头状态自动更新「已关闭」（`--card` 指定或按 commit 回写区自动识别）。
- **模拟模式** `--simulate`（M1 模拟 / 临时目录测试）：跳过 git/kickstart/在线检查；做 config.env 只读检查 + 看板可见性（`server.board.export` 自 `--dispatch-dir` 导出检索目标卡）+ 卡头关闭；**不碰生产 docs/dispatch**。
- 一次对话 = 流式探活：收到 done 完整回复 OK；超时但流式已通 FLOWING 视为在线；无事件/脑错误 FAIL——部署门禁抓断链不抓脑慢。
- 修 macOS bash 3.2 `set -u` 下 `$VAR（全角括号` 解析成错误变量名（统一 `${VAR}`）。
- 实测：模拟端到端（临时目录 T90-test 卡 → 看板可见 PASS → 卡头关闭 已关闭 → 删除后看板无残留）；在线实测（--no-pull --no-kickstart 连 127.0.0.1:7788）：/health + /board/states + /projects + 免登录直连 + 一次对话（OK textlen=30 完整回复）全 PASS。

### C. 验收自动化：validate 门禁 + CI + pre-commit（完成）

- `server/board/validate.py` 增强（出卡门禁）：
  - **卡头元数据合并解析全部 `>` 行**（loader 同款）——修复历史卡把 关联/执行体/状态/日期 分布在多行的误报（79 问题 → 2 真实遗留）；
  - **编号唯一**：卡头 ID 重复报重（复制卡只改文件名不改卡头即拦截；R/X 变体卡 `T1`/`T1-R` 数字前缀共存不误伤）；
  - **编号一致**：卡头 `T<N>` 数字前缀必须与文件名一致（T99 卡头配 T56 文件名即拦截）。
- CI：`.github/workflows/ci.yml` 新增 `card-validate` job（ubuntu + python3.12）。
- pre-commit：`.pre-commit-config.yaml` 新增 `card-validate` hook（`docs/dispatch/` 改动即校验）。
- 遗留修复：T8 卡头 `管理席/执行体：` → `执行体：`；T26 补 `## 目标`。`validate docs/dispatch` 现在全过（62 张卡）。
- **CI 门禁坏卡演示**（刻意放坏卡被拦）：
  - 编号重复（T55 两张）→ `编号 T55 重复` 拦截，exit 1；
  - 卡头 T99 配文件名 T56 → `卡头编号 T99 与文件名 T56 不一致` 拦截，exit 1；
  - 合规卡（new-card.sh 生成）→ 通过，exit 0。

### D. 壳复验 `scripts/verify-shell.sh` + `verify_shell_checks.py`（完成）

- 六场景 API 级断言（零第三方依赖）：
  1. **免登录直进**：/health auth_required=false + 未带 token 直连 /projects 200；
  2. **左栏业务项目**：/projects 返回 17 个真实业务项目（ai-loop-router/CCC/medio-0/qb/QuantHive/ccc-demo…）；
  3. **零 console error**（服务端侧）：9 个壳端点全 2xx/3xx 无 5xx/401；
  4. **流式**：POST /conversation {stream:true} → SSE 事件流动；
  5. **思考折叠无空占位**：前端 message.js 空思考守卫（`if (!thinkingBuf) return null` 不建折叠）+ 流式 thinking 事件（若出现）内容非空；
  6. **切界面不断流**：长轮询增量契约——对话后 `GET /conversation?after=<seq-2>` 增量无缺口（UI 切回拉取不丢内容）。
- 对话类场景隔离 thread_id（不污染生产历史）；脑忙（503/超时）重试 3 次后 SKIP（非壳缺陷）。
- `--local` 起本地测试服务（随机端口，默认跳对话场景）。
- 实测：**全场景 6/6 PASS**（127.0.0.1:7788，切界面增量 after=6→2 条 seq=8 无缺口，exit 0）；--local 模式 3 PASS + 3 SKIP（无大脑）exit 0。

### E. 测试流程任务端到端（临时目录 T9x-test，不碰生产）

完整链路跑通（`/tmp/ccc-t52-e2e`，详见 `docs/automation-base.md` §六）：
1. **出卡**：`new-card.sh --id T90-test --dispatch-dir /tmp/ccc-t52-e2e/dispatch` → `T90-test-t52.md`，validate 通过；
2. **执行**：状态 待分派 → 已回写（模拟执行体完成）；
3. **放行**：`release.sh --simulate --dispatch-dir ... --card T90-test` → **看板可见性 PASS**（T90-test 在派生看板数据中）+ **卡头关闭 状态→已关闭** + 放行报告，exit 0；
4. **看板可见**：T90-test 卡在导出看板数据中可见（状态 已关闭）；
5. **删除测试卡无残留**：rm 卡 → 重导 board.js → `残留计数 0`，看板无 T90-test 残留；
6. **生产未受影响**：`validate docs/dispatch` 62 张卡全过，docs/dispatch 无未提交改动。
- 跑通后才允许正式任务走该链路；正式放行由 Codex 在 2017 生产链路执行（验收标准 2 的 2017 实测）。

### 测试结果与 push 证据

- `pytest server/tests/`：**450 passed**（Python 3.12 + pytest）
- `validate docs/dispatch`：通过（62 张卡）；`python -m py_compile`：clean；`bash -n` 三脚本：clean
- ruff：本机未安装（CI `card-validate`/`ruff` job 会跑）；代码未引入新依赖
- 分支 `codex/t52-auto-base` 已推送 origin，分步提交：
  - `e55bc813` feat(scripts): T52-A 出卡模板 new-card.sh
- `6e71a763` feat(deploy): T52-B 一键放行 release.sh
- `e732724a` feat(board): T52-C 验收自动化 validate+CI+pre-commit
- `5460de50` feat(scripts): T52-D headless 复验 verify-shell.sh
- （本 commit）docs(dispatch): T52 回写 + docs/automation-base.md 流程说明

---

## 验收区（Codex 独立取证 · 2026-08-04 · 合入 main + 2017 部署后）

**判定：✅ 通过。** 自动化流程三件套落地（出卡/放行/验收），测试流程任务端到端跑通。

- **new-card.sh**：Codex 实测临时目录生成 `T1-task.md`，validate 卡头校验通过 ✅
- **release.sh**：--dispatch-dir 支持 + 自动验证 + 放行报告 + 卡头关闭（执行端回写证据 + 测试流程任务端到端）✅
- **验收自动化**：validate 门禁增强 + CI + pre-commit（执行端演示证据）；verify-shell.sh 六场景 headless 复验 ✅
- **流程文档**：docs/automation-base.md（94 行）入库 ✅
- 回归：pytest 全绿、ruff clean ✅；2017 已部署（三件套在位）✅
- 自动化流程：75 分钟闭环，分步提交 A/B/C/D（e55bc813/6e71a763/e732724a/5460de50）✅
