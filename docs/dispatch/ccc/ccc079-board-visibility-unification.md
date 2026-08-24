# 任务卡 ccc079 · 看板可见性统一——平台卡入板 + 四项目缺失修复（048-P1）（DSH 执行）

> 关联：ccc-plan-048 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-24

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

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[是]
   - 说明：（回写时据实填写）
2. **教训沉淀**：[有/无]
   - 说明：（回写时据实填写）
3. **档案/README**：[否]
   - 说明：（回写时据实填写）
4. **线路图**：[否]
   - 说明：（回写时据实填写）
