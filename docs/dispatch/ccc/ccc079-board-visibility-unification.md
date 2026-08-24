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

（验收席专用——执行体禁止写入）

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
