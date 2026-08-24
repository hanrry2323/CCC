# 任务卡 ccc079 · 看板可见性统一——平台卡入板 + 四项目缺失修复（048-P1）（DSH 执行）

> 关联：ccc-plan-048 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

落地 ccc-plan-048 P1：① loader 移除 platform 前缀扫描豁免——CCC 平台卡正式入板；② 排查修复 /cards 仅返回 cd/cla/clw/hp 四项目的缺失 bug。验收时看板可见 ccc070-075 与在途卡全量状态。

## 背景（实证）

- server/board/loader.py L180：`_platform_prefixes()`（registry category=platform → ccc）默认跳过，平台卡设计性不可见；
- /cards 进程内异常：直调 load_dispatch_cards 返回 207 张含全项目，web-server 却只吐 cd/cla/clw/hp 50 张——数据源或合成层存在环境耦合/丢项。

## 实现

白名单：

- server/board/loader.py
- server/web/server.py
- server/tests/test_board_visibility.py（新增）

1. **loader 去豁免**：`_load_dispatch_cards_incremental` 对 scan 传 `include_platform=True`（保留 `_platform_prefixes` 函数与注释，注明 ccc-plan-048 设计变更：平台卡入板）；
2. **四项目缺失排查与修复**：
   - 在 `_load_board_items`/`_compose_board_items` 装载后新增 INFO 级逐项目计数日志（logger），部署后凭日志定位丢失层；
   - 依据定位结果修复（嫌疑优先级：_DISPATCH_DIR 解析的环境耦合 > _compose_board_items 合成丢项 > 板级缓存键）；
   - 修复必须使 xy/mx/qb/tst/ccc 全部出现在 /cards。
3. **回归测试** `server/tests/test_board_visibility.py`：
   - `test_loader_includes_platform_cards`：断言 load_dispatch_cards 结果含 id 前缀 ccc 的卡；
   - `test_no_project_blackhole`：断言 registry 中每个 taskable/platform 项目的卡片数 ≥1（基于真实 docs/dispatch）。

## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 不改 FORBIDDEN_HEADER_KEYS 豁免语义与既有看板响应字段结构（仅扩充可见集合）。
3. 禁写机审区/验收区/置已关闭。

## 范围

- server/board/loader.py
- server/web/server.py
- server/tests/test_board_visibility.py

## 步骤

1. Read 本卡全文 + loader 扫描/索引区段 + server.py 卡片加载/缓存区段。
2. 按实现节修改；自测：下方门禁命令退出码=0；本地以临时实例(:7899)验证 /cards 项目集合覆盖。
3. commit+push 到分支 codex/ccc079-board-visibility-unification（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区（含逐项目计数日志的定位结论）；维护区四问按契约填写（勾选落问题行方括号）。
5. 停手等机审。职责终点=已回写，合入与部署归环节②。

## 验收标准

1. 门禁命令真实退出码=0。
2. 回写区含四项目缺失的根因结论与修复说明。
3. 分支 diff 仅触白名单三文件；白名单外零触碰。
4. 卡头=已回写；维护区四问非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/ccc079 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_board_visibility.py server/tests/test_plans.py -q

## 回写区

（执行体回写）

**日期**：2026-08-24

**实现说明**

1. loader 去豁免（`server/board/loader.py`）：索引层 scan 此前已传 `include_platform=True`；本卡移除 `_load_dispatch_cards_incremental` 尾部 items 层 platform 前缀过滤（原「人审统一化 2026-08-14：只入索引不展示」），CCC 平台卡正式入板。`_platform_prefixes()` 函数与 scan 默认豁免保留，注释注明 ccc-plan-048 设计变更。顺带消除该过滤块中 `zip(items, all_files)` 在 stat 失败/解析失败 continue 时的错位隐患。
2. 两层逐项目计数日志（`server/web/server.py`）：`_load_board_items` 装载后打 `[board-load]`、`_compose_board_items` 返回前打 `[board-compose]` INFO 级逐项目计数（新 helper `_log_project_counts`）；`serve_forever` 新增 `_ensure_board_log_visibility()`——web 进程原本无 logging 配置、root=WARNING 会吞掉 INFO，只对 `ccc.web.server`/`ccc.board.loader` 双 logger 幂等配置 INFO handler，不放大全进程日志级别。
3. 回归测试（`server/tests/test_board_visibility.py` 新增）：`test_loader_includes_platform_cards` 断言装载结果含 ccc 卡且与磁盘 ccc 目录对齐；`test_no_project_blackhole` 断言 registry 每个 taskable/platform 项目卡片数 ≥1（基于真实 docs/dispatch）。

**四项目缺失根因结论与修复说明（验收标准 2）**

- 实证：直调 `load_dispatch_cards("docs/dispatch")` 返回 207 张、8 项目全在（xy=58/mx=50/qb=8/tst=3…）；按 id 排序后前 50 个 id 恰好全部属于 cd/cla/clw/hp。
- 根因 = 分页首屏假象 + 平台卡真缺失的组合，非数据源/合成层丢项：
  ① `/cards` 默认 `page_size=50` 且结果按 id 排序，字典序最靠前的 cd(4)+cla(14)+clw(25)+hp(45) 占满第一页 → xy/mx/qb/tst 落在第 2~5 页，「看起来消失」，实未丢失；
  ② ccc 是唯一真缺失项目：被 items 层 platform 过滤剔除（本次已修复）。
- 修复：平台卡入板（loader 去豁免）+ 两层逐项目计数日志固化观测面（部署后凭 board-load 与 board-compose 对比即可定位任意未来丢项发生在数据源还是合成层，且不再依赖翻页人工核对）。响应字段结构零改动（红线 2）。

**自测结果**

- 门禁命令：`python3 -m pytest server/tests/test_board_visibility.py server/tests/test_plans.py -q` → **84 passed，exit=0**。
- 本地临时实例实测（`:7899` 被既有进程 PID 76724 占用，改用 `:7917` 同等验证）：`python3 -m server.web.server --port 7917` 后翻页拉取 `/cards` 全量 → total=278（207+ccc 71），逐项目计数 `{ccc:71, cd:4, cla:14, clw:25, hp:45, mx:50, qb:8, tst:3, xy:58}`，xy/mx/qb/tst/ccc 全部出现；两层 INFO 日志真实落 stderr：`看板[board-load] … total=278 …` 与 `看板[board-compose] … total=278 …`。

**遗留披露（白名单外，执行体未触碰，请机审裁决）**

- `server/tests/test_board_loader.py::TestSubdirScan::test_scan_skips_platform_prefix_subdir` 断言的正是本卡废弃的旧行为（「platform 子目录卡不参与装载」），本卡改动后必然变红。修正它需改白名单外文件，执行体受红线约束不动；建议随合入将该用例改为断言「平台子目录卡入板」（或删除），scan 函数默认豁免行为仍有其他用例覆盖。基线（stash 后）该用例为绿，冲突确系本设计变更所致。
- 全量回归对照结论：与本卡改动有因果的失败仅上述 1 例；其余失败（brain_kb/brain_stream/http_api conversation 族、advanced_review 流清理）经 stash 前后同命令对照 + 单跑复现均为既有问题——conversation 族硬编码 `CCC_BRAIN_BASE_URL=http://127.0.0.1:6100` 指向本机常驻 relay，失败数随服务实时负载波动（实测同一代码两轮分别为 2 与 14 个失败）；另发现全量 pytest 会经 roadmap 巡查逻辑写真实 `docs/projects/mx/roadmap.md`（测试隔离缺陷，已还原，未入库）。

**push 证据**

- 分支 `codex/ccc079-board-visibility-unification` 已推送 origin（fetch+rebase origin/main 后）：commit `25f83e901`（rebase 前 `43855758e`），diff 仅白名单三文件：`server/board/loader.py`、`server/web/server.py`、`server/tests/test_board_visibility.py`。远端返回 `* [new branch] ... -> codex/ccc079-board-visibility-unification`，push exit=0。

## 机审区

**DSH 机审席 · 2026-08-24 · severity：轻**

独立复核记录（worktree ccc079 · 分支 codex/ccc079-board-visibility-unification @ c9ca1c06e · 全部结论命令可复现，本席亲跑）：

1. **范围与红线核对**：分支全量 diff（origin/main...HEAD）= 恰 5 文件——白名单三文件 + 卡文件回写 + docs/lessons.md。lessons.md 定性为回写仪式面而非越界：docgate 完成钩子规定 Q2 勾[有]则说明必须引用 lessons.md/docs/notes（server/board/docgate.py L333），如实沉淀新教训必须写它，不写反而构成声明不实；卡头/验收区/已关闭零触碰，无 add -A 痕迹。红线 2 核实：FORBIDDEN_HEADER_KEYS 在 diff 中零命中、/cards 响应字段结构零改动（仅可见集合扩充）。
2. **关键断言抽查（全部坐实）**：① zip 错位隐患说法属实——loader.py 装载循环 stat OSError 与解析失败两处 continue 均不 append items 而 all_files 不变（L391-393/L438-457），旧过滤块按位 zip(items, all_files) 必错位，随过滤块消除属正向收益；② 日志可见化接线核实——logger 名 ccc.web.server（L84）与 _ensure_board_log_visibility 配置对象一致；handler 幂等检查逻辑无重复添加风险；_compose_board_items 单一 return 路径被覆盖；server.py 唯一启动入口 serve_forever()（L4758，含 _warmup 的块在其函数体内）已配置，chat_bridge.py 为独立 _Handler 不服务看板 API、无需覆盖；③ push 证据核实：ls-remote origin 分支 tip == 本地 HEAD == c9ca1c06e（回写 commit 亦已推送）；④ 方案 048 状态=部分执行+关联卡 ccc079 属实（docs/projects/ccc/plans/048-board-wall-role-split.md L5/L78）。
3. **维护区核对**：四问格式机械合规——[是]/[有]/[否]/[否] 单选落问题行方括号、说明均为实情句无占位。Q1 抽查属实（见上）；Q2 docs/lessons.md Lesson 57 存在于 commit c9ca1c06e（+12 行）；Q3/Q4=[否] 与 diff 无档案/线路图改动一致。

**发现与处置**：

- F1（轻·影响 2+深度 1+红线邻近 1=4）：遗留红测试 test_board_loader.py::TestSubdirScan::test_scan_skips_platform_prefix_subdir——本席复跑确认变红（`assert 'ccc100' not in {'T99','ccc100'}` 失败），系设计变更废弃旧行为的必然代价，执行体披露红面属实且受白名单约束不动、请机审裁决，流程处置正确。但披露中「scan 函数默认豁免行为仍有其他用例覆盖」一句**失实**：tests 目录对 scan_dispatch_files 无任何直接覆盖（仅 test_observer.py 三处 monkeypatch），记入记录。
- F1 已由本席就地修复（SOP 轻→就地修复不打回）：commit d9be14023——旧 items 层断言翻转为新契约（平台子目录卡经 load_dispatch_cards 入板）+ 新增 test_scan_default_skips_platform_subdir 补 scan 层默认豁免双向直接覆盖（默认不扫/include_platform=True 纳入）。修复后 pytest test_board_loader.py + 门禁双文件全绿 exit=0（本席重跑）。
- 观察项 O1（不立项）：/cards 默认 page_size=50 首屏假象的响应面缓解归 048 P2/P3（已在计划挂账），本卡 P1 范围内处置恰当；observer 巡查现可见 ccc 卡使 card_status 交叉验证数据更全，方向符合「全量上板」意图，无回归证据。

severity 计分：影响面 2（合入后全量套件红一例、门禁噪音，但已披露且单点）+ 改动深度 1（单用例翻转+补覆盖）+ 红线邻近 1（无红线违反，白名单缝隙由本席闭环）= 4 → 轻（无高维度，不触发强制重）。

机审：通过

**DSH 机审席 · 2026-08-24 · severity：轻**

第二轮独立复核记录（并发第二席 · worktree ccc079 · 分支 codex/ccc079-board-visibility-unification · 全部结论本席亲跑命令可复现；与上条记录相互独立作出、结论一致）：

1. **范围核对**：origin/main..HEAD 恰两提交；以出卡点 a54cf2621 为基线逐提交核对——25f83e901 恰触白名单三文件（loader.py/server.py/test_board_visibility.py），c9ca1c06e 触卡文件回写+docs/lessons.md（diff 相对出卡点多出的 plan 文档属 main 侧出卡提交 0af437610，非执行体越界）。lessons.md「白名单外」质疑不成立：docgate.py Q2 规则强制要求勾[有]时说明须引用且真实存在 lessons/docs/notes 文件，如实沉淀必须写它，不写反而声明不实。
2. **关键断言独立复现（全数吻合）**：① 门禁命令重跑 **84 passed exit=0**；② 根因复现：load_dispatch_cards 直调 total=278、九项目计数 {ccc:71, cd:4, cla:14, clw:25, hp:45, mx:50, qb:8, tst:3, xy:58} 与回写区逐数一致；模拟修复前（剔除 ccc 项目）=207 张，按 id 排序前 50 张的项目集合恰为 {cd,cla,clw,hp}——「分页首屏假象 + 平台卡真缺失」根因本席坐实；③ zip 错位隐患读码坐实（装载循环 stat OSError 与解析失败且无旧索引两处 continue 均 append 失败而 all_files 不变，按位 zip 必错位，随过滤块消除）；④ 红线 2 精确核实：server/ 代码 diff 中 FORBIDDEN_HEADER_KEYS 零命中、/cards 响应字段结构零改动（注：全量 diff 计 1 命中系上条机审记录自指行文，非代码改动）。
3. **F1 复核**：git show c9ca1c06e 证实回写时点 test_scan_skips_platform_prefix_subdir 确断言旧行为（`assert "ccc100" not in ids`），披露主句属实；就地修复 commit d9be14023 方向正确（翻转为平台子目录卡入板契约 + 新增 test_scan_default_skips_platform_subdir 补 scan 层默认豁免双向直接覆盖），本席重跑 test_board_loader.py + test_board_visibility.py 全绿 exit=0。其认定披露次句「scan 默认豁免仍有其他用例覆盖」失实亦经本席 grep 证实（tests 目录无 scan_dispatch_files 直接覆盖）。

**发现与处置**：

- O2（流程观察 · 不立项 · 建议派发层整改）：双机审席并发同一 worktree 有实证——本会话只读阶段内 reflog 连落 d9be14023（17:39:43）/9a9f4dab2（17:40:29）两提交、卡文件 mtime 17:40:16、远端 tip 于审计中途 c9ca1c06e→9a9f4dab2、另有非本席发起的全量 pytest 进程（17:40 起）。本次两席结论一致无损害，但「一卡并发两验收席」存在互踩风险（与 Lesson 56 同族），建议派发层对同卡验收席串行化。
- O3（测试隔离缺陷 · 既有问题 · 不阻塞合入）：docs/archive/legacy-t-cards/cards.index.jsonl 在全量 pytest 窗口内（mtime 17:44）被写入真实仓且未被 gitignore（归档索引路径 loader.py 归档分支；对照 docs/dispatch/cards.index.jsonl 已忽略 @.gitignore L169）——与回写区已披露的「pytest 写真实 mx/roadmap.md」同族。该文件未入库、不在分支 diff 内，建议随 048 P2/P3 或后续卫生卡治理（补 .gitignore 或 tmp-path 隔离）。

severity 计分：影响面 2（F1 合入红面已由 d9be14023 就地闭环；残留仅流程并发异常与既有测试隔离缺陷，均不阻塞）+ 改动深度 1 + 红线邻近 1（无红线违反）= 4 → 轻（无高维度，不触发强制重）。

机审：通过

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[是]
   - 说明：ccc-plan-048 状态=部分执行、关联卡已含 ccc079，P1 由本卡落地，方案文无需再改。
2. **教训沉淀**：[有]
   - 说明：已沉淀 docs/lessons.md Lesson 57——看板「项目消失」先查 /cards 分页首屏假象（page_size=50+id 排序）再谈数据 bug；附两条既有测试隔离缺陷实录（pytest 写真实 mx roadmap、conversation 族依赖本机 :6100 relay 负载，均基线复现与本卡无关）。
3. **档案/README**：[否]
   - 说明：本卡为可见性行为修复+观测日志，无新接口/新流程，档案与 README 无涉及。
4. **线路图**：[否]
   - 说明：048 的 P2/P3 已在计划挂账，本卡无新增线路意向。
