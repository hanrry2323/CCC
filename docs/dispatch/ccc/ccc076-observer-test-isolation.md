# 任务卡 ccc076 · observer 测试隔离修复——全量 pytest 不再污染检出（DSH 执行）

> 关联：无方案（2026-08-24 地基加固 · 总调度直派） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

> 状态校正（2026-08-24 · 受老板一次性授权，总调度执行）：工程已交付且分支就绪，磁盘卡由「待分派」如实校正为「已回写」以终结重派循环；合入归环节②。

## 目标

server/tests/test_observer.py::test_run_observer_output 隔离不全：只 mock 三个 loader，
run_observer 内部 scan_findings(cfg, PROJECT_ROOT) 吃真实仓库根、write_roadmap_draft 未被
mock → 任何检出跑全量 pytest 都会向所在仓 docs/projects/mx/roadmap.md 追加巡查行
（ccc068 三次污染实证；ccc074 调查报告主链结论）。

## 实现

白名单：server/tests/test_observer.py。

1. 为 write_roadmap_draft 补 mock（patch 到测试内 tmp 路径或 MagicMock），并断言其被调用参数落在 tmp 内；
2. scan_findings 的仓库根注入 tmp 根（消除对真实 PROJECT_ROOT 的读依赖亦可，但写路径必须隔离）；
3. 新增守护断言：用例结束后 git status --porcelain docs/projects/mx/roadmap.md 为空（在仓内运行时）。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 只改测试文件的 mock/断言；禁改 observer.py 与 roadmap.py 生产逻辑（行为治理另卡 ccc077）。
3. 禁写机审区/验收区/置已关闭。

## 步骤

1. Read 本卡全文与相关代码现状。
2. 按实现节修改；自测运行下方门禁命令，退出码必须=0。
3. commit+push 到本分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。职责终点=已回写，合入归环节②。

## 验收标准

1. 门禁命令真实退出码=0（wrapper 证据日志为准）。
2. 白名单外零触碰。
3. 卡头=已回写；维护区四问非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/ccc076 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_observer.py -q

## 回写区

**回写时间**：2026-08-24 · 执行体：DSH（ox-alpha）

**实现说明**：
- 白名单内仅 `server/tests/test_observer.py`（62+/6-），生产代码零改动。
- 卡实现节三点全落地：① `test_run_observer_output` 为 `write_roadmap_draft` 补 tmp 绑定替身
 （外层 patch `server.board.roadmap._repo_root`→tmp，替身内断言每次调用写目标
  `is_relative_to(tmp_path)`）；② `observer.PROJECT_ROOT/REPO_ROOT` 注入 tmp 根，
  `scan_findings(cfg, PROJECT_ROOT)`/`_auto_fix_deterministic`/docs-notes 落点全部随迁，
  并加隔离断言 `summary['findings'] == []`；③ 用例末新增守护断言：
  `git status --porcelain -- docs/projects/mx/roadmap.md` 为空（在仓内运行时生效，非 git 环境自动跳过）。
- **自测中发现同文件第二污染点并一并加固**：`test_run_observer_writes_draft_for_consistency`
  已 mock write_roadmap_draft 但未注根，run_observer 尾段 `notes_dir = PROJECT_ROOT/'docs'/'notes'`
  把巡查报告写进真实仓（实证：报告 mtime 2026-08-24 14:33:57 变更、内容即该测试两个 mock findings；
  该路径被 `.gitignore:178` 覆盖、porcelain 沉默，属隐形污染）→ 同样注入 tmp 根后指纹不再变化。

**自测结果**：
- 门禁：`python3 -m pytest server/tests/test_observer.py -q` → **26 passed，退出码 0**（多次复跑一致）。
- 全量回归（历史污染触发场景）：`python3 -m pytest server/tests -q` → 1175 条跑毕后指纹对照：
  `docs/projects/mx/roadmap.md` mtime 不变、该路径 porcelain 0 行；
  `docs/notes/2026-08-24-ccc-patrol.md` mtime 不变（第二污染点修复实证）；
  全仓 porcelain 除本测试文件改动外零新增。
- 套件存量失败与本案无关：test_brain_kb/test_brain_stream/test_http_api 会话流测试失败，
  stash 掉本次改动后复跑同样失败（502≠503，中继环境问题）——pre-existing，非本卡引入。

**push 证据**：
- 分支 `codex/ccc076-observer-test-isolation`（基点=origin/main@54de3ce0，push 前 fetch 复核无需 rebase）。
- commit：`efd02cc5e` test(ccc076): observer 测试隔离修复——run_observer 全链路注入 tmp 根。
- push 后核验：`git ls-remote origin refs/heads/codex/ccc076-observer-test-isolation`
  → `efd02cc5e191fce93f5674febf2d83e2c303d4b3` 与本地 HEAD 一致。

**白名单外附带发现（未触碰，供后续卡参考）**：
全量 pytest 会生成未跟踪文件 `docs/archive/legacy-t-cards/cards.index.jsonl`
（pytest 下 `get_index_path(dispatch_dir)` 返回 `<dir>/cards.index.jsonl`，
刷新者指向 test_board_loader.py 等针对真实归档目录跑 loader 的用例）。
本卡测试不触它（单文件门禁前后 mtime 对照不变）；该文件在 HEAD 与主仓均未跟踪。建议另开卡治理。

## 机审区

**DSH 机审席 · 2026-08-24 · severity：轻**

> 终审记录（本席，取代审查窗口内并行实例的全部中间记录）：审查对象=当前 HEAD
> 732166915 全谱系（54de3ce0..732166915）。reflog 实证审查窗口内有多并行 DSH 机审实例
> 竞写本卡（c4110a15a@15:04:56 已推远端、732166915@15:05:47 本地落盘），其产出经本席
> 逐项独立复核后方可采信，冲突以本记录为准；建议调度层落实一卡一 worktree 单实例。

独立复核记录（worktree ccc076 @ 732166915 · 结论全部命令可复现）：

1. **范围核对**：全谱系 diff --numstat 仅 docs/dispatch/ccc/ccc076-observer-test-isolation.md（55+/5-）与白名单内 server/tests/test_observer.py（65+/6-）；observer.py/roadmap.py 生产代码零改动，白名单外零触碰；工作树仅余执行体披露过的 untracked docs/archive/legacy-t-cards/cards.index.jsonl。代码提交 efd02cc5e numstat=62+/6- 与回写声明逐字一致，6 行删除均为移入 patch 上下文的断言（零断言损失）。
2. **隔离机制逐链坐实（静态·对源码行号）**：run_observer 全部写点 dispatch_dir(observer.py:735)/list_plans(:744)/scan_findings(:756)/_auto_fix_deterministic(:777)/notes_dir 尾段(:812) 均经 observer.PROJECT_ROOT 模块全局在调用时解析→patch 生效路径完整；草案真实写入链 observer.write_roadmap_draft(:1574)→board.roadmap.create_draft/_write_roadmap→_repo_root() 同为动态解析→patch 至 tmp 后落点必在 tmp。执行体自报第二污染点（docs/notes 巡查报告，.gitignore 沉默路径）与该链吻合，随 PROJECT_ROOT 注入一并消除。机械门禁归引擎裁决（26 passed exit=0 以 wrapper 证据日志为准），本席不重跑。
3. **谱系末位修复复核成立（732166915）**：替身写目标原由 tmp_path 自构造再断言 is_relative_to(tmp)，属构造性恒真；现改为 `board.roadmap._roadmap_path(str(project))` 真实派生链——_roadmap_path(roadmap.py:268) 动态调 _repo_root()，patch 一旦失效即越出 tmp、断言必红；board_roadmap 于用例内导入、闭包可用，引用无误。
4. **找茬记录**：
   - F1（轻·已闭环）：维护区 Q3/Q4「说明」原为选择符回声「[否]。」，不满足 P1-b「说明须一句实情」；现已各含实情句，四问均合法单选 [否]/[无]/[否]/[否]。
   - F2（轻·已闭环）：替身写目标同义反复断言 → 732166915 改真实派生链，详见第 3 条（本席逐行复核成立）。
   - F3（观察·另卡治理·本席新增）：存量 test_write_roadmap_draft 未注根，_write_roadmap 经 _acquire_roadmap_lock(roadmap.py:394) 触碰真实仓 docs/projects/ccc/.roadmap.lock 的 mtime（0 字节、*.lock 已 ignore 故 porcelain 沉默；本席 ls+check-ignore 实证）——非检出污染，但属隐形触碰面，建议后续卡对该用例一并注入 tmp 根。
   - F4（观察·设计取舍）：守护断言测绝对洁净而非增量，检出若带历史脏 mx/roadmap.md 会误红——fail-loud 取向可接受。
   - F5（流程事件·如实入档）：审计窗口内多并行 DSH 机审实例竞写（见顶注）；另 docs/projects/mx/roadmap.md mtime 于 15:03:10 被触碰一次，本席复验 sha256 前缀 d24ed5d9874d0cc8 与基线一致、porcelain 干净、对 origin/main 零 diff——纯元数据漂移无内容变化，并发实例下写入者不可归因，记录在案。
   - F6（观察·非阻塞）：origin/main 已前进至 c07560f10（无关 plan 文档提交），分支合入时由环节② 复核 rebase；push 时点基点核对（=当时 origin/main tip）在案属实。
5. **维护区核对**：四问均合法单选且说明行皆含一句实情；抽查声明真实性吻合——62+/6- 与回写声明一致、push 核验哈希与当时 ls-remote 一致、patrol 报告 mtime 14:33:57 第二污染点实证、.gitignore 巡查报告沉默路径在案、cards.index.jsonl 未跟踪属实。

severity 计分：影响面 1（白名单单测试文件+卡文、无生产变更）+ 改动深度 1（测试 mock/断言加固+一处派生链修正）+ 红线邻近 2（P1-b 维护区判据曾擦边已闭环、并发竞写流程事件已入档）= 4 → 轻（无高维度，不触发强制重）。

后到席补注（732166915 作者 · 终局收口）：① **F5 破案**：15:03:10 的 mx/roadmap.md mtime 触碰即本席的守护断言负控实验——人为追加标记行 → 单跑用例见红（FAILED … M docs/projects/mx/roadmap.md）→ git checkout 还原；sha 复原 d24ed5d9…、仅 mtime 漂移，时点吻合，悬案关闭。② **F3 就地闭环核验**：前席工作区遗留的 test_write_roadmap_draft 注根 tmp 改动经本席复核成立（_acquire_roadmap_lock(roadmap.py:394) 经未 patch 的 _repo_root 在真实仓落 .roadmap.lock，本席 ls+check-ignore(.gitignore:183 *.lock) 实证；注根后锁与草案全落 tmp），随本谱系提交入库；另查 clw/test 项目下亦有同类锁残留（同族触碰面，归后续治理卡）。③ 本席对上列全部关键主张独立复现（范围/注入链/门禁/指纹/负控/维护区/push 谱系），与前席结论一致、无新增否决项。审计谱系：c4110a15a → 732166915 → ebf4c8bc4 → adfdbf70a（前席终审记录）→ 44b555275（F3 注根闭环入库）→ 本提交，双席交叉确认收口。

机审：通过

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：[否]。地基加固直派卡无关联方案。
2. **教训沉淀**：[无]
   - 说明：[无]。机制教训随卡记录即可。
3. **档案/README**：[否]
   - 说明：[否]。本卡仅改 server/tests/test_observer.py 与卡文，未触 registry 与项目档案。
4. **线路图**：[否]
   - 说明：[否]。测试隔离修复无线路变化；mx 线路图全程指纹不变。
