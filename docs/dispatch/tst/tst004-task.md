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

**实现说明**（2026-08-24 · DSH 执行体 · 第 3 轮派发回写）：

白名单两文件实现于提交 `0c1cc2b92`，本轮逐行核验与卡规格一致、零代码改动：

1. `server/tests/test_server.py`：`test_build_ports_payload_empty`（L774）与 `test_chat_bridge_token_empty`（L922）在既有隔离之上追加 `patch("server.web.server._env_or_config", return_value="")`，切断 config.env 回落；既有断言一字未动。
2. `scripts/approve-merge.sh`：竞态守卫位于 L663-666——`close_card "$path"`（L620）之后、`git add -- "$path"`（L667）之前；`grep -q "状态：已关闭"` 不成立即输出卡指定 `[ERROR] ${id}: 合入竞态——close_card 后卡头非已关闭……` 文案并 `return 1`（不提交/不推送/不部署）；其余逻辑零改动。

**前两轮机审打回定性（假阳性，已获平台侧证实并热修）**：

- 第 1/2 轮打回依据 `/Users/fan/.ccc/logs/exec/tst004.test-evidence.log` 的 `exit_code=127`：采集到的 cmd 为 `:TestPortNetwork::…`（`python3 -m pytest server/tests/test_server.py` 前缀被截丢），127=命令不存在，被测代码从未真实跑挂；根因是门禁行按首个 ASCII 冒号切键值，恰在 pytest node-id `test_server.py::` 处腰斩；
- 平台侧已治本：主仓 main 提交 `e21e974d2`「fix(scripts): test-evidence 门禁解析优先全角冒号」（受老板临时授权热修），落点在本卡最后一次假阳性打回（02:04:07）之后、本轮派发之前；本轮以同源 Python 解析器复验本卡门禁行，已能完整取出 `cd …; python3 -m pytest server/tests/test_server.py::TestPortNetwork::…` 全命令。

**自测结果**（本轮全量重跑 · 分支工作树 /Users/fan/program/CCC-wt/tst004 · 全部真实执行）：

- T1 卡门禁原命令：`python3 -m pytest server/tests/test_server.py::TestPortNetwork::test_build_ports_payload_empty server/tests/test_server.py::TestConversationDetailed::test_chat_bridge_token_empty -q` → **2 passed，退出码 0**；
- T2 回归面 TestPortNetwork+TestConversationDetailed 全类：**8 passed，退出码 0**；
- T3 `bash -n scripts/approve-merge.sh` → 通过（退出码 0）；
- T4 守卫语义探针（逐字节提取 L663-666 真实守卫块 + 桩环境）：开卡头（状态：已回写）→ 输出卡指定 `[ERROR] tst004: 合入竞态……` 文案且 rc=1 中止；已关闭头 → 无输出 rc=0 放行；
- T5 红基线（main 检出 /Users/fan/program/CCC 只读复跑未封闭化版，PYTHONDONTWRITEBYTECODE=1 + -p no:cacheprovider）：**2 failed**——ports 断言左值首条目即 `{&#39;port&#39;: 6100, &#39;name&#39;: &#39;relay-anthropic&#39;}`、token 得 `ccc-chat-bridge-2026`，与卡目标§1 描述逐字吻合，证实原始缺陷真实、封闭化必要且测试非空转。

**commit/push 证据**：实现 `0c1cc2b92` + 首轮回写 `4f38c6cd0` + 重试回写 `020ba30d4`；本轮第 3 次回写提交 `6e5b76445` 已推 origin（`git ls-remote origin codex/tst004-task` = 本地 HEAD = `6e5b76445`；其后证据段修订提交 `c45794f5f` 亦已快进推送，机审时点 ls-remote = 本地 HEAD = `c45794f5f`——机审席 2026-08-24 核验补正）。push 过程说明：按卡步骤执行 `git fetch origin && git rebase origin/main` 后推送被拒（non-fast-forward——rebase 重写哈希与远端既有原哈希线分叉，强推触禁令），遂按红线改走无损路线：重置回远端线 `291569269` 并干净 cherry-pick 本轮回写（无冲突），快进推送完成；代价是分支基点不含 main 最新两平台提交（ffee8f8e5 / e21e974d2）——经核不影响本卡：热修 e21e974d2 的采集器位于主检出 scripts/ 由机审 wrapper 直接调用，不经分支工作树，且白名单实现内容与已验证版本逐字一致。

## 机审区

（验收席专用——执行体禁止写入）

**DSH 机审席 · 2026-08-24 · severity：轻**

v4 对抗式独立审查，证据均在 worktree `/Users/fan/program/CCC-wt/tst004` 可复现，未引用执行体自述作判据。

**范围核对**：分支 `codex/tst004-task` 相对 merge-base `b6a6427a8` 改动 6 文件 = 白名单 2 + 本卡回写 + Doc-Gate 强制文档 3。实现提交 `0c1cc2b92` 恰触白名单两文件（`git show --stat 0c1cc2b92`），且 `git diff 0c1cc2b92..HEAD -- server/tests/test_server.py scripts/approve-merge.sh` 为空——rebase 遭拒改走重置+cherry-pick 路线后实现零漂移属实。卡规格节（目标/实现/红线/范围/门禁/验收标准）相对出卡版零改动，无篡改。main 独有提交 `ffee8f8e5`/`e21e974d2` 触达文件与白名单 comm 求交为空，后续合入无冲突面。

**实现核验**：①测试封闭化——两用例既有断言逐字保留（diff 中 `assert result.get("ports") == []` / `assert result == ""` 原样在位），仅新增 `with patch("server.web.server._env_or_config", return_value="")` 隔离；patch 目标真实存在（`server/web/server.py:785 def _env_or_config`），符合红线3「仅封闭化」。②竞态守卫——`scripts/approve-merge.sh` 实测顺序 L620 `close_card "$path"` → L663-666 守卫（`if ! grep -q "状态：已关闭"` 不成立即输出卡指定 `[ERROR] ${id}: 合入竞态——…` 文案并 `return 1`）→ L667 `git add -- "$path"`，位置与文案逐字合卡；`${id}` 同函数既有使用（L627/L654）、`return 1` 与既有 L617 同范式；`close_card` L306 确以 `状态：已关闭` 回写卡头，happy-path 不误伤，守卫语义 fail-closed。③push 证据——`git ls-remote origin codex/tst004-task` = 本地 HEAD = `c45794f5f`；引用哈希 `0c1cc2b92`/`4f38c6cd0`/`020ba30d4`/`6e5b76445`/`291569269`/`e21e974d2`/`ffee8f8e5` 经 `git cat-file -t` 全部存在；平台热修 `e21e974d2` 在 main 属实（`scripts/test-evidence.sh` +6/-1，主题与回写区陈述一致）。

**观察项（均不计违规）**：
1. 验收标准#3「分支相对 main 的 diff 仅触白名单两文件」与同卡 Doc-Gate（维护区答「有/是」必须同步 plans/notes/README，否则打回）字面相抵。本席按意图判定：代码严守白名单、文档同步系流程强制产物（tst003 先例同判）。建议制卡侧后续将#3 措辞收窄为「代码 diff 仅触白名单」。
2. 回写区 push 证据原括注停留在第 3 轮快照「本地 HEAD = `6e5b76445`」，其后证据段修订提交 `c45794f5f` 才为最终推送 HEAD；不变式「远端=本地」始终为真，非声明不实——已由本席就地补正并注明。
3. 守卫通过后至 `git add` 之间残留毫秒级理论窗口，系卡规格收敛设计的固有边界；fail-closed 且并发改写会在下次合入再被拦截，可接受。

**severity 评分**：影响面 1（发现均为文档精度层面，不触及代码行为与合入安全）+ 改动深度 1（仅卡内一处括注补正，无代码改动）+ 红线邻近 1（无越界、无断言削弱、无私写机审/验收区、未直推 main）= 3 → 轻。

**维护区四问核对**：四问均单选落位问题行方括号（[否]/[有]/[否]/[是]），说明均为一句实情非占位；抽查引用工件全部存在且内容吻合——`docs/projects/tst/plans/001-pipeline-smoke.md:3` 关联卡含 tst004、`docs/notes/2026-08-24-tst-lessons.md` 恰两条教训与说明一致、`docs/projects/tst/README.md:34` 近况行在位。核对通过。

机审：通过（被审 c45794f5fc31）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：方案 tst-plan-001 关联卡原缺 tst004，已补全（plans/001-pipeline-smoke.md 关联卡追加 tst004）；方案目标（管线冒烟）已于 tst002 达成，状态维持「已确定/100%」不变。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：docs/notes/2026-08-24-tst-lessons.md 现两条——①gitignored config.env 只在主检出存在，分支 worktree 门禁会假绿，封闭化必须隔离配置读取源；②门禁行按首个 ASCII 冒号切键值会在 pytest node-id `::` 处腰斩命令致 exit 127 机审假阳性（tst004 两轮误打回实证，平台热修 e21e974d2）。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：仅测试内部 mock 封闭化与 approve-merge 守卫各一处，无结构/技术栈/路径变化。
4. **线路图**：项目近况/下一步是否变化？[是]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：docs/projects/tst/README.md「线路/近况」已补 2026-08-24 一行（tst003 合入竞态事故 → tst004 治本修复）。
