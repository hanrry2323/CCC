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

独立审查记录（worktree ccc076 · 审计基线 @ c4110a15a，谱系延展独立复核至 732166915 · 结论全部命令可复现）：

1. **范围核对**：分支 codex/ccc076-observer-test-isolation，merge-base(HEAD,origin/main)=54de3ce0=origin/main tip（基点最新）；ls-remote origin 分支=本地 HEAD=84bb98765（push 核验属实）。全分支 diff（54de3ce0..HEAD）仅卡文件+白名单内 server/tests/test_observer.py，白名单外零触碰；代码提交 efd02cc5e numstat=62+/6- 与回写声明逐字一致，6 行删除全部为移入 patch 上下文的断言（零断言损失）；observer.py/roadmap.py 生产代码零改动。
2. **动态复现（本席亲跑坐实核心声明）**：门禁 `python3 -m pytest server/tests/test_observer.py -q` → 26 passed、退出码 0；门禁前后 docs/projects/mx/roadmap.md（sha256 d24ed5d9…）与 docs/notes/2026-08-24-ccc-patrol.md（e648911d…）mtime+hash 零漂移；全量回归 server/tests 跑毕后两指纹仍零漂移、porcelain 除已知 untracked cards.index.jsonl 外零新增——「全量 pytest 不再污染检出」成立。注入面核对：run_observer 主链（dispatch_dir/list_plans/scan_findings/_auto_fix_deterministic/notes_dir 尾段）全部吃 observer.PROJECT_ROOT 模块全局，patch 生效路径完整；roadmap 写路径统一经 `_repo_root()`→已 patch 至 tmp。
3. **存量失败与本卡无关**：brain_kb/brain_stream/http_api 会话流失败集与回写区披露一致；本席抽 test_brain_stream::test_success_flow 单测隔离跑仍失败（期望桩文案 vs 真实模型答复，502≠503 中继环境问题），模块与本案不相交，pre-existing 成立。
4. **找茬记录**：
   - F1（轻·已就地修复）：维护区 Q3/Q4「说明」原为选择符回声「[否]。」，不满足 P1-b「说明须一句实情」——系 ccc074 机审 F4 同项建议后的重复发生；本席补写实情句随审计提交落盘。
   - F2（轻·已落实并经本席独立复验）：test_run_observer_output 替身内写目标原由 tmp_path 自构造再断言 is_relative_to(tmp)，属构造性恒真；并行机审实例以 732166915 将其改为取自 `board.roadmap._roadmap_path()` 真实派生链（_repo_root 补丁失效即越出 tmp 必红），本席逐行复核该提交并重跑门禁 26 passed exit=0、指纹零漂移后予以认可。
   - F3（核实非问题）：同文件 test_write_roadmap_draft 直接调 write_roadmap_draft，但 _roadmap_path 已 patch 直落 tmp，非第三污染点。
   - F4（观察·白名单外·另卡治理）：untracked docs/archive/legacy-t-cards/cards.index.jsonl 为历史全量跑副产物（执行体如实披露、本席复核属实），不影响合入。
   - F5（流程事件·如实入档）：本席审计推送 c4110a15a 后，发现同 worktree 存在 3 个并行 DSH 机审实例（同指令同授权）竞跑；兄弟实例于 15:05:47 落 732166915（F2 就地加固、白名单内 +4/-1）。本席不盲信不盲弃：独立复核内容+门禁+指纹全部通过后认可并纳入审计谱系。教训：同卡同 worktree 并行审计存在竞写风险，建议调度层保证一卡一 worktree 单实例。
   - F6（观察·元数据事件）：审计窗口内 docs/projects/mx/roadmap.md mtime 于 ~15:03:10 被触碰一次；经查 sha256=d24ed5d9… 与基线逐字节一致、porcelain 干净、对 origin/main 零 diff——纯元数据漂移无内容变化，并发实例下写入者不可归因，记录在案。
5. **维护区核对**：四问均合法单选（否/无/否/否）、docgate 机械判据通过；Q1/Q2 说明含实情句，Q3/Q4 经 F1 就地补实情；抽查声明真实性全部吻合（push ls-remote 一致、62+/6-、patrol 报告 mtime 14:33:57 第二污染点实证、.gitignore 巡查报告沉默路径、cards.index.jsonl 未跟踪状态）。

severity 计分：影响面 1（白名单单测试文件+卡文、无生产变更）+ 改动深度 1（mock/断言加固）+ 红线邻近 2（P1-b 维护区说明判据边界、重复发生）= 4 → 轻（无高维度，不触发强制重）；谱系延展复核项（F2 落实/F5 并发审计事件/F6 元数据触碰）经独立核验均不抬升 severity。

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
