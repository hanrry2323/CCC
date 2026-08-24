# 任务卡 ccc077 · loop-observer 巡查草稿写入治理——roadmap 正文只读化（DSH 执行）

> 关联：无方案（2026-08-24 地基加固 · 总调度直派） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

> 状态校正（2026-08-24 · 受老板一次性授权，总调度执行）：工程已交付且分支就绪，磁盘卡由「待分派」如实校正为「已回写」以终结重派循环；合入归环节②。

## 目标

board-scheduler 每 60s 调度的 loop-observer 达阈值时经 write_roadmap_draft 直接写各项目
docs/projects/<p>/roadmap.md（辅链实证：pid 31668 命中与留档 patch 同源内容）。治理：
草稿写入改道专用目录，项目 roadmap 正文对自动链路只读化。

## 实现

白名单：server/engine/observer.py（必要时含 server/board/roadmap.py 的签名扩展）。

1. 新增环境开关 CCC_LOOP_OBSERVER_DRAFTS（默认 off）；
2. off 时 observer 循环内的草稿写入调用直接跳过（记 DEBUG 日志一次/轮）；
   on 时写入目标改为 data/drafts/roadmap/<project>-draft.md（不再触碰 docs/projects 正文）；
3. 保持人工流程对 roadmap 的写路径完全不变；
4. 附回归测试：off 时文件 mtime/内容不变；on 时草稿落 data/drafts 且正文不动。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 默认必须 off（生产行为保守化）；禁止删除既有草稿数据；人工写路径零变化。
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

测试：cd /Users/fan/program/CCC-wt/ccc077 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_observer.py server/tests/test_validator_closed_card_approval.py -q

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
