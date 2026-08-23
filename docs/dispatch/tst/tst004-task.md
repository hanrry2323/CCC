# 任务卡 tst004 · 管线修复验证·合入竞态防护与部署测试封闭化（DSH 执行）

> 关联：tst-plan-001 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：tst · 日期：2026-08-24

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/tst/README.md`

## 目标

治本修复 tst003 事故暴露的两个管线缺陷，恢复「合入→部署→关卡」链路可信：

1. **部署测试环境泄漏**：server/tests/test_server.py 两用例在生产机必挂——
   test_build_ports_payload_empty 只 mock 了 _scan_listening_ports，未隔离 _env_or_config("CLUSTER_PORT_NAMES"/"CLUSTER_BUSINESS_PORTS") 的 config 回落（生产配置含 relay-anthropic:6100 等 → known 未监听分支补条目 → ports==[] 断言失败）；
   test_chat_bridge_token_empty 清了 env 但 _chat_bridge_token() 经 _env_or_config 回落读 config 得 ccc-chat-bridge-2026 → 断言空串失败。
2. **合入竞态静默回退**：approve-merge 在 close_card 之后、git add 之前存在窗口，
   并发 server/git_sync.py:_force_align_dispatch 按「远端 main（本批尚未推送）」强制对齐 docs/dispatch，
   把刚合入的卡改写回出卡占位版并被当真提交推送（tst003 合入提交 266f77dd7 实为净回退：卡 blob 与出卡版完全相同），随后引擎按磁盘权威无限重派开发。

## 实现

白名单仅下列两文件，改动之外零触碰：

1. server/tests/test_server.py
   - test_build_ports_payload_empty：在既有 _scan_listening_ports mock 基础上，追加 patch("server.web.server._env_or_config", return_value="")（或等价隔离两个 CLUSTER_* 配置键），使端口无任何来源 → 断言 ports == [] 通过。
   - test_chat_bridge_token_empty：追加同样的 _env_or_config 隔离（返回空串），保持 env clear 不变，断言返回空串通过。两用例既有断言语义不得削弱。
2. scripts/approve-merge.sh
   - 在 close_card "$path" 调用之后、git add -- "$path" 之前插入竞态防护断言：
     若 grep -q "状态：已关闭" "$path" 不成立 → 输出
     [ERROR] ${id}: 合入竞态——close_card 后卡头非已关闭（疑似 git_sync 强制对齐并发改写工作树）→ 中止合入（不提交/不推送/不部署），请排除干扰后重跑
     并 return 1。
   - 其余既有逻辑一律不改。

注：若注入的 biz_worktree 为不含 server/ 的骨架仓，一切验证以分支工作树 /Users/fan/program/CCC-wt/tst004 为准（tst003 先例）；下方门禁命令已自带目录回退。

## 红线（先看）

1. 禁止触碰白名单外任何文件；禁直推 main（执行体只推 codex 分支）。
2. 禁写机审区/验收区/置已关闭。
3. 测试改动仅限封闭化（mock/隔离外部源），禁删除或放宽既有断言。

## 范围

- server/tests/test_server.py
- scripts/approve-merge.sh

## 步骤

1. Read 本卡全文与目标代码现状（两个用例、_build_ports_payload/_chat_bridge_token/_env_or_config、approve-merge 的 close_card 至 git add 区段）。
2. 按「实现」完成修改并自测：bash -n scripts/approve-merge.sh 通过；运行下方门禁测试命令退出码=0。
3. commit+push 到分支 codex/tst004-task（勿直推 main）；push 前 git fetch origin && git rebase origin/main。
4. 卡头改「已回写」并填回写区（实现说明/测试结果/commit hash 与 push 证据）；维护区四问逐项填写——勾选符必须落在问题行的方括号内（如 [否]/[无]），说明行写一句实情（docgate 机械校验该格式，格式错=机审打回，tst003 教训）。
5. 停手，等机审与合入批准。

## 验收标准

1. 门禁测试命令真实退出码=0（wrapper 独立截获证据日志为准）。
2. bash -n scripts/approve-merge.sh 通过，且新增守卫确位于 close_card 之后、git add 之前。
3. 分支相对 main 的 diff 仅触白名单两文件；两用例断言语义未被削弱。
4. 卡头=已回写；维护区四问勾选落位问题行方括号、说明非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/tst004 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_server.py::TestPortNetwork::test_build_ports_payload_empty server/tests/test_server.py::TestConversationDetailed::test_chat_bridge_token_empty -q

## 回写区

**实现说明**（2026-08-24 · DSH 执行体 · 机审打回后重试轮）：

白名单两文件实现于上轮提交 `0c1cc2b92`，本轮逐行核验与卡规格一致、保持不变：

1. `server/tests/test_server.py`：`test_build_ports_payload_empty`（L784）与 `test_chat_bridge_token_empty`（L930）在既有隔离之上追加 `patch("server.web.server._env_or_config", return_value="")`，切断 config.env 回落；既有断言一字未动。
2. `scripts/approve-merge.sh`：竞态守卫位于 L663-666——`close_card "$path"`（L620）之后、`git add -- "$path"`（L667）之前；`grep -q "状态：已关闭"` 不成立即输出卡指定 `[ERROR] … 合入竞态……` 文案并 `return 1`（不提交/不推送/不部署）；其余逻辑零改动。

**打回原因核查（重要 · 上轮机审为假阳性）**：

上轮台账「不通过（测试真实失败）」实为证据采集缺陷，被测代码从未真实跑挂：
- 证据 `/Users/fan/.ccc/logs/exec/tst004.test-evidence.log`：采集到的 cmd 为 `:TestPortNetwork::…`（前缀 `python3 -m pytest server/tests/test_server.py` 被截丢），`exit_code=127` = 命令不存在，非断言失败；
- 根因：本卡为首张门禁含 pytest node-id `::` 的卡。`scripts/test-evidence.sh` L43 与 `server/engine/main.py` `parse_gate_section` L1759 同源解析缺陷——门禁行内含任意 ASCII 冒号即按第一个 ASCII 冒切键值（应按全角「：」切），恰在 `test_server.py::` 处误切；Python 逐字节复现与证据日志一致；
- 两处带病文件均在本卡白名单外（平台件），执行体按红线不越权修复。**在采集器修复前，重跑机审将复现同一 127 假阳性**，请平台侧先治本（建议：全角冒号优先切分，或仅识别行首键名后首个冒号）。

**自测结果**（本轮全量重跑 · 分支工作树 /Users/fan/program/CCC-wt/tst004）：

- T1 卡门禁原命令：`python3 -m pytest server/tests/test_server.py::TestPortNetwork::test_build_ports_payload_empty server/tests/test_server.py::TestConversationDetailed::test_chat_bridge_token_empty -q` → **2 passed，退出码 0**；
- T2 加强：注入 `CLUSTER_PORT_NAMES` + `CCC_CHAT_BRIDGE_TOKEN` 双泄漏键后仍 2 passed（封闭化对配置泄漏免疫）；
- T3 回归面 TestPortNetwork+TestConversationDetailed 全类：8 passed；
- T4 `bash -n scripts/approve-merge.sh` 通过；
- T5 守卫语义探针：开卡头 → 输出指定 `[ERROR]` 文案且 rc=1 中止；已关闭头 → rc=0 放行；
- T6 红基线（main 检出 /Users/fan/program/CCC 只读复跑未封闭化版）：**2 failed**——ports 断言得 registered_stale 条目、token 得 `ccc-chat-bridge-2026`，证实原始缺陷真实、封闭化必要。

**commit/push 证据**：上轮实现 `0c1cc2b92` + 回写 `4f38c6cd0`（push 前已 rebase origin/main）；本轮重试回写见最新提交（docs 仅触本卡）。分支 `codex/tst004-task` 已推 origin，`git ls-remote` 与本地 HEAD 一致。

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：方案 tst-plan-001 关联卡原缺 tst004，已补全（plans/001-pipeline-smoke.md 关联卡追加 tst004）；方案目标（管线冒烟）已于 tst002 达成，状态维持「已确定/100%」不变。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：新增 docs/notes/2026-08-24-tst-lessons.md——gitignored config.env 只在主检出存在，分支 worktree 门禁会假绿；封闭化必须隔离配置读取源并在生产检出复现红基线。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：仅测试内部 mock 封闭化与 approve-merge 守卫各一处，无结构/技术栈/路径变化。
4. **线路图**：项目近况/下一步是否变化？[是]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：docs/projects/tst/README.md「线路/近况」已补 2026-08-24 一行（tst003 合入竞态事故 → tst004 治本修复）。
