# 任务卡 ccc074 · mx/roadmap 周期写入者定位调查（DSH 执行）

> 关联：无方案（2026-08-24 债务清偿 · 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

多个 worktree 反复出现 docs/projects/mx/roadmap.md 未提交改动（22 行 Loop 巡查行样式），三次污染出卡现场（patch 留档 /tmp/ccc068-stray-mx-roadmap.patch*）。定位写入者并产出治理建议，不实施修复。

## 实现

白名单：docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md（新建调查报告）。

线索起点：server/engine/observer.py 与 server/board/roadmap.py 含「巡查」字样；嫌疑面=engine observer 巡查、board-scheduler、patrol 脚本。方法建议：mtime 轮询+lsof 交叉、launchd 任务表、patrol 日志时间戳比对。

报告必填：写入进程命令行与父链、触发周期、写入内容生成点（file:line）、是否属预期设计、治理建议（停止/改道/加锁）三选一及理由。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 只读取证；报告文件为唯一产出。
3. 禁写机审区/验收区/置已关闭。

## 步骤

1. Read 本卡全文与相关代码/文件现状。
2. 按实现节修改；自测运行下方门禁命令，退出码必须=0。
3. commit+push 到本分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。

## 验收标准

1. 门禁命令真实退出码=0（wrapper 证据日志为准）。
2. 白名单外零触碰。
3. 卡头=已回写；维护区四问非占位。

## 门禁

测试：test -s docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md && grep -qE "写入者|结论" docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md && echo OK

## 回写区

（执行体回写 · 2026-08-24 DSH）

**实现说明**：只读取证 + 一次性动态复现，未实施任何修复。写入者定位为同一代码路径的双触发面：(A) 测试链——`server/tests/test_observer.py:94-115 test_run_observer_output` 隔离缺口（`OBSERVER_FORCE=true` 强制实跑，`scan_findings(cfg, PROJECT_ROOT)` 吃真实仓库根、`write_roadmap_draft` 未 mock），任何 checkout 跑全量 pytest 即对所在 checkout 的 `docs/projects/mx/roadmap.md` 追加 Loop 巡查草案行（路径基准 `server/board/roadmap.py:26 _repo_root` 与 `observer.py:40 PROJECT_ROOT` 均基于 `__file__`）——此为 worktree 污染元凶，与 ccc068 多轮全量 pytest 节奏吻合；(B) 生产链——launchd `com.ccc.scheduler` 常驻进程（PID 31668，PPID=1，cwd=主仓，60s 轮询，12:32:46 实跑日志命中与 patch 逐字相同的 mx/M8 发现）经 `run_observer→write_roadmap_draft(:762)→create_draft(roadmap.py:604)→_write_roadmap(roadmap.py:307)` 写主仓。反复复现根因：M8 声明「进行中」而 4 关联方案实际全部已完成的数据条件未消除。治理建议三选一取「改道」：测试补 mock 治本 + 写权限环境闸收口 + M8 数据收口；不选停止（拆治理闭环）、不选加锁（已有 fcntl 锁，锁不解越权写入面）。详见报告：docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md。

**自测结果**：门禁命令真实退出码=0——
```
$ test -s docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md && grep -qE "写入者|结论" docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md && echo OK
OK        （gate-exit=0）
```
附加动态复现自测：一次性 detached worktree 内单跑 `pytest server/tests/test_observer.py::test_run_observer_output -q`（1 passed）后该 checkout 的 `docs/projects/mx/roadmap.md` 立即变脏（+3/-2），diff blob 对 `a1abcb5a4..d9462a1bc` 与 /tmp/ccc068-stray-mx-roadmap.patch* 字节级一致；复现现场已还原并移除临时 worktree。主仓现存脏文件为既有证据，按红线未触碰。

**push 证据**：分支 `codex/ccc074-mx-roadmap-writer-investigation`，实现 commit `f5922a1be`（fetch+rebase origin/main 后显式 add 单文件提交，非 fast-forward 风险已消），已 push 至 origin 新建远端分支成功；卡回写 commit 随后追加同分支。

## 机审区

**DSH 机审席 · 2026-08-24 · severity：轻**

独立复核记录（worktree ccc074 @ c10af19e6，结论全部命令可复现）：

1. **范围核对**：`git log --name-status origin/main..HEAD` 仅 2 提交——f5922a1be（新增白名单报告）、c10af19e6（卡回写），触面=卡文件+白名单报告，白名单外零触碰；`git ls-remote origin refs/heads/codex/ccc074-mx-roadmap-writer-investigation` = c10af19e6 = 本地 tip，push 属实；未直推 main；无 `git add -A` 痕迹（两提交各只含单文件）。门禁命令本席重跑 exit=0。
2. **核心因果断言独立复现坐实**（本席亲跑）：自建一次性 detached worktree @HEAD（起步干净）→ 单跑 `pytest server/tests/test_observer.py::test_run_observer_output -q`（1 passed）→ 所在 checkout 的 `docs/projects/mx/roadmap.md` 即脏（+3/-2）；diff 与 `/tmp/ccc068-stray-mx-roadmap.patch`、`.patch2`、`.patch3` 全部字节级一致（cmp IDENTICAL）；前后 blob hash-object = a1abcb5a4..d9462a1bc 与报告断言精确一致；复现现场已还原清理，主仓既有脏文件（+3/-2，mtime 08-24 06:09:27）确认未被触碰。
3. **引用抽查 15 处全真、零虚构**：test_observer.py:94-115（仅 mock 三 loader、OBSERVER_FORCE=true 于 :99）；observer.py:40 / :91-92 / :715 / :756 / :762 / :694-703 / :777 / :1598 / :1609；roadmap.py:604 / :307（fcntl 锁 docstring :308）；scheduler.py:31 / :267-273（loop-observer 注册 TASK_TYPE_READONLY 属实）；web/server.py:2814 / :3652-3666；mx/roadmap.md:64-66 M8「进行中」且 mx-plan-005~008 头部状态全「已完成」（根因数据条件属实）；launchd plist RunAtLoad/KeepAlive 属实；生产进程 PID 31668 本席复核时仍在运行、命令行与报告一致。

**发现与处置**：

- F1（轻·已就地修复）：报告行号漂移 4 处（内容零虚构）——roadmap.py「26-28」实为 :28-30；去重「614-616」实为 :615-618；_write_roadmap 调用「618-624」实为 :625；头部日期 date.today() 实位于 :320。已修正报告并随本区提交（机审席轻量就地修复授权）；卡回写区「roadmap.py:26」同一漂移以本条勘误为准，不回改执行体历史记录。
- F2（红线邻近·论证未越线）：「只读取证」vs 动态复现——写入仅发生于执行体自建的一次性 detached worktree 内、事后还原清理、零持久副作用，报告与回写区双处如实披露，判定为受控取证手段而非越线。
- F3（观察项）：维护区四问逐项单选+说明齐备、引用工件真实存在；Q3/Q4 说明仅「[否]。」，过机械门禁但信息量退化，后续卡建议各写一句实情；Q2 判「无」与白名单约束自洽（lessons 新文件在白名单外，另立即越界）。

severity 计分：影响面 1 + 改动深度 1 + 红线邻近 2 = 4 → 轻（无高维度，不触发强制重）。

机审：通过（被审 c10af19e6639）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：[否]。债务清偿直派卡无关联方案。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：[无]。机制性教训（测试吃真实仓库根=隐式写仓器）已完整落在本卡白名单产物 docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md，不另立 lessons 文件。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：[否]。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：[否]。
