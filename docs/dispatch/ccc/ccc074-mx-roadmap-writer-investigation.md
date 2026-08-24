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

独立复核记录（worktree ccc074 @ 2271ebcae · 本席记录取代前席记录（93cbe4fbd/9789ae841），历史提交保留于谱系；结论全部命令可复现）：

1. **范围核对**：`git log --name-status origin/main..HEAD` 触面仅卡文件+白名单报告；merge 2271ebcae 第二父=origin/main(9e009d4c7)，`git diff 2271ebcae^2 2271ebcae --name-status` 恰为该两文件、无夹带；远端分支 tip=本地 HEAD=2271ebcae（ls-remote 属实）；main 未被直推（仍 9e009d4c7）；各提交均显式单/双文件 add，无 add -A 痕迹；worktree 干净。门禁命令本席重跑 exit=0。
2. **核心因果断言本席亲跑坐实**：一次性 detached worktree @2271ebcae（起步干净）→ 单跑 `pytest server/tests/test_observer.py::test_run_observer_output -q`（1 passed）→ 该 checkout 的 docs/projects/mx/roadmap.md 即脏；blob 对 a1abcb5a4c..d9462a1bcc，diff 与 /tmp/ccc068-stray-mx-roadmap.patch{,2,3} cmp 全 IDENTICAL；现场已还原、临时 worktree 已移除，主仓既有脏文件未被触碰。
3. **引用全链抽查（约 30 处逐行核对，零虚构零漂移）**：test_observer.py:94-99（仅 mock 三 loader、OBSERVER_FORCE=true 于 :99；「唯此一处失守」亦核实——test_write_roadmap_draft(:355) 以 patch `_roadmap_path` 到 tmp_path 隔离，其余 scan 测试走 tmp_path/mock_repo_root）；observer.py:40/:91-92/:106-124/:694-703/:715/:756-762/:777/:1598/:1609；roadmap.py:28-30/:307-308(fcntl 锁)/:320(date.today)/:604/:615-618/:625；scheduler.py:31(DEFAULT_INTERVAL_SECONDS=60)/:209-212(循环 sleep)/:267-273(loop-observer 注册 TASK_TYPE_READONLY)；web/server.py:2814/:3652-3666；mx/roadmap.md:64-66 M8「进行中」且 plans/005~008 头部状态全「已完成」（根因数据条件属实）；plist RunAtLoad/KeepAlive=true；PID 31668 PPID=1 起于 08-22 11:40:12、命令行逐字吻合；patch 三连 1283B@04:29/05:01/05:27 + patch4 空@06:01 全属实。

**发现与处置**：

- F1（观察·活体新证·非缺陷）：主仓脏文件 mtime 已由报告快照 06:09:27 漂移至 13:47:58——本席审计期间生产写入者再次动手（main 仓 13:44:07 落 ccc073 merge → cards.index.jsonl 变更触发 loop-observer 实跑，scheduler 日志可见同一 M8 finding 重报于 13:53 轮）；当前 diff 与三份留档 patch 仍字节级一致、blob 对不变。「清了又脏」循环被实时坐实，报告结论强化而非削弱；报告内 mtime 为写作时点事实，不构成失实，无需改报告。
- F2（复核确认）：前席就地修正的报告 4 处行号漂移（roadmap.py :28-30/:615-618/:625/:320）经本席逐行复核全部吻合，现行引用零漂移。
- F3（红线邻近·论证不越线）：「只读取证」vs 动态复现——写入仅发生于一次性 detached worktree 内、事后还原清理、零持久副作用，报告与回写区双处如实披露；本席以同手段独立复现并同样清理，判定为受控取证手段而非越线。
- F4（观察项）：维护区 Q3/Q4 说明仅「[否]。」，过机械门禁但信息量退化，后续卡建议各写一句实情；另 scheduler 日志无时间戳致逐轮写入归因精度受限（报告未定项已如实声明），支持其治理建议中写权限闸+任务标注修正的方向。

severity 计分：影响面 1（纯调查文档卡，触面 2 文件、无代码变更）+ 改动深度 1（+131 行文档）+ 红线邻近 2（只读取证 vs 受控动态复现）= 4 → 轻（无高维度，不触发强制重）。

机审：通过

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
