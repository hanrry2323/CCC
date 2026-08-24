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

（执行体回写）

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：[否]。地基加固直派卡无关联方案。
2. **教训沉淀**：[无]
   - 说明：[无]。机制教训随卡记录即可。
3. **档案/README**：[否]
   - 说明：[否]。
4. **线路图**：[否]
   - 说明：[否]。
