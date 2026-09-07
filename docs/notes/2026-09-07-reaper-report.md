# P4.2 reaper 三方对账加固报告

> 日期：2026-09-08（按指令文件日期落账） · 范围：CCC 平台仓
> 依据：`docs/ENGINEERING-2.0.md` §P4.2、`/Users/fan/ccc-brain/docs/v2.0-execution-protocol.md`
> 实现：本仓 `server/ops/`、`scripts/ops/reaper-card-audit.sh`、`server/deploy/com.ccc.reaper.plist`

## 1. 交付物

| 文件 | 用途 |
|---|---|
| `server/ops/card_status.py` | 纯 stdlib 卡文件扫描/状态归一/卡 ID 与 `codex/*` 分支名映射 |
| `server/ops/reconcile.py` | 卡、看板、分支三方差异分类纯函数 |
| `server/ops/board_fetch.py` | GET `/cards?page_size=9999`，`CCC_BOARD_TOKEN` 优先，401/403 内存换 token 重试一次 |
| `server/ops/ledger_writer.py` | 追加写 `action=reaper_diff` ledger；原子写当前黄标快照 |
| `server/ops/reaper.py` | 每日对账 CLI；业务仓路径来自 `docs/projects/registry.yaml` |
| `scripts/ops/reaper-card-audit.sh` | launchd 安全入口（极简 PATH，python 绝对路径） |
| `server/deploy/com.ccc.reaper.plist` | 每日 06:05 日历触发模板，与 `ccc-prod-health` 同批 |
| `scripts/ops/install-reaper-plist.sh` | 占位符渲染+`plutil -lint`，仅安装不自动加载 |
| `server/tests/test_reaper_card_audit.py` | 分类矩阵与端到端辅助函数测试 |
| `server/web/server.py` | 看板 compose 时读 `reaper-active.jsonl` 只读黄标快照，注入 reason 供 UI 高亮 |
| `server/web/legacy-chat/js/components/taskCard.js` | 卡徽章渲染 reaper 标黄徽章（`⚠ 对账`） |
| `server/web/legacy-chat/css/components.css` | `.badge-reaper` 徽章样式 + 卡左侧警示条 |

## 2. 差异分类矩阵

| code | 触发条件 | severity | 处理 |
|---|---|---:|---|
| `card_missing_on_board` | 卡文件存在，看板 `/cards` 无同 ID | warn | `reaper-diffs.jsonl` + `reaper-active.jsonl` 黄标输入 |
| `board_orphan` | 看板存在，`docs/dispatch` 无同 ID | severe | ledger + 黄标；不自动删除看板数据 |
| `state_drift_disk_vs_board` | 卡头基础状态与看板原始 `state` 不同 | warn | ledger + 黄标；`board_column=机审` 为派生列，不作为漂移 |
| `branch_orphan` | `codex/*` 分支名解析出的卡 ID不存在 | warn | ledger + 黄标；不自动删除分支 |
| `branch_missing` | 活跃卡（待分派/执行中/已回写/打回）缺任一同名分支 | severe | ledger + 黄标；不自动创建分支 |
| `branch_merged_uncleaned` | 已关闭卡分支被 `merge-base --is-ancestor` 核验已合入 `origin/main`，但仍存在 | warn | ledger + 黄标；不自动删除分支 |
| `branch_card_state_conflict` | 作废卡仍挂分支，或已关闭卡分支存在但无法证明已合入 | severe | ledger + 黄标；保留分支供人工取证 |

`branch_missing` 的分支匹配按卡 ID 而非完整 slug：跨业务仓同卡分支只要任一仓存在即满足。分支列表同时扫描本仓和 registry 中存在的 `paths.mac2017` 仓；未能核验 merge 状态按未合入处理（fail-closed）。

## 3. 证据落点与安全边界

- 差异原始逐轮记录：`~/.ccc/logs/reaper-diffs.jsonl`。
- 当前黄标快照：`~/.ccc/logs/reaper-active.jsonl`；无差异/看板不可用时原子清空，避免旧黄标残留。
- 审计账本：`data/audit/ledger.jsonl`（可由 `CCC_AUDIT_LEDGER` 隔离覆盖），每行 `action=reaper_diff`、`kind=reaper_diff`、`code`、`card_id`、`severity`、`detail`。
- 看板 API 不可达或鉴权失败：不把空列表当一致；写 `reaper_source_unavailable` severe，退出非零，当前黄标快照清空。
- token/密码只在 Python 进程内存；不写 reaper 日志、ledger 或 git。
- 脚本不执行分支删除、不改卡状态、不执行 transition；仅报告差异，保留人工/合入席裁决边界。
- 看板标黄实现为**只读合成**：`_compose_board_items` 读取 `~/.ccc/logs/reaper-active.jsonl`
  当前快照，把命中卡的 `reason` 追加 `reaper: <code>` 前缀，UI 据此渲染 `⚠ 对账` 徽章与
  黄色警示条；不写卡文件、不改状态机、不调用任何 board transition。
  快照无差异/看板不可用时由 reaper 原子清空，黄标自动消失。

## 4. launchd

模板：`server/deploy/com.ccc.reaper.plist`。

- `StartCalendarInterval`: `Hour=6`, `Minute=5`。
- `RunAtLoad=false`；每日由系统日历触发。
- 标准输出/错误合并到 `~/.ccc/logs/reaper.launchd.log`。
- 安装：

```bash
bash scripts/ops/install-reaper-plist.sh
```

安装脚本只渲染并 `plutil -lint`，不自动 `bootstrap`/`kickstart`。本次仅交付配置，不擅自加载运行面；实际加载需要运维确认。

## 5. 测试与复现

定向测试：

```bash
.venv-hub/bin/pytest -q server/tests/test_reaper_card_audit.py
# 23 passed
```

全量测试：

```bash
.venv-hub/bin/pytest -q            # 全量：全部通过（含新增 reaper 用例）
.venv-hub/bin/ruff check server/ops server/tests/test_reaper_card_audit.py server/web/server.py
# 改动路径 ruff 全净；全库 ruff 仅存量 docs/archive 遗留问题（非本改动）
```

静态检查：

```bash
bash -n scripts/ops/reaper-card-audit.sh scripts/ops/install-reaper-plist.sh
/usr/bin/plutil -lint server/deploy/com.ccc.reaper.plist
# plist: OK
python3 -m compileall -q server/ops
```

测试覆盖：7 个分类代码逐类断言、无差异矩阵、跨仓同 ID 多分支、括号状态、坏卡、ledger 追加、黄标快照、看板不可达 fail-closed、认证文件解析、plist 占位符替换。

## 6. 未执行项 / 待部署

- 未加载 `com.ccc.reaper`，因此本报告不宣称 launchd 已运行；只报告模板 lint 与安装渲染测试通过。
- 全量 pytest 全绿（本报告 §5 记录）；全量 ruff 仅存量 `docs/archive/ccc-legacy-2026-08-02/...` 遗留 803 项 F541 类问题，
  与本改动路径无关；改动路径 ruff 全净。
- 生产首次运行前建议用临时 `CCC_REAPER_LOG_DIR` 做一次只读演练，核对三方数量与 registry 业务仓可达性，再加载 plist。
- web-server/engine 需随代码变更重启才能让看板黄标面生效（经 `launchctl kickstart`，重启前后 `/health` 验证）。

## 7. 生产演练（隔离日志目录 · 只读）

```bash
tmpdir=$(mktemp -d)
CCC_REAPER_LOG_DIR="$tmpdir/logs" \
CCC_AUDIT_LEDGER="$tmpdir/ledger.jsonl" \
scripts/ops/reaper-card-audit.sh
# 实测：cards=14（三仓合计），diffs=10（存活业务仓 codex 分支 + 本地 codex 分支残留），
# reaper-diffs.jsonl / reaper-active.jsonl / ledger.jsonl 三处落盘齐全，退出码=1（有差异，fail-closed）。
```

本次演练只写临时目录，未触碰生产 `~/.ccc/logs` 与生产 ledger。最终退出码语义：
差异为空且三源可用 → 0；任何差异存在 → 1；看板不可达 → 1 并写 `reaper_source_unavailable`。
