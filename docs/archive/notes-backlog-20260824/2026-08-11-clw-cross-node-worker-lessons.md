# 2026-08-11 clw 跨节点 Worker 路由测试 · 教训

> 关联卡：clw019 · 关联方案：ccc-plan-020（集群 Worker 池蓝图）

## 验证结论（全链路成功）

clw019「前端设计角色注入验证」由 **W9（252 移动终端 Claude Code）** 跨节点认领执行成功：

1. **角色→Skill 注入生效**：卡头「角色：前端设计」→ 执行提示注入 `ui-ux-pro-max` → 252 加载该 Skill 按设计准则审查
2. **跨节点路由可行**：252 经 GitHub deploy key 访问 clwarp 源码 → 只读审查 → 产出高质量报告
3. **主写源收口**：252 只读消费，报告由 M1/2017 统一提交（符合权限矩阵）
4. **报告质量**：4 项建议（配色/排版/UX/一致性），含文件:行号引用，符合 ui-ux-pro-max 准则

## 可复用教训

0. **看板状态 ≠ 磁盘卡状态（clw019 排查核心）**：看板 `:7788/cards` 的状态由 **Engine sidecar（`~/.ccc/logs/exec/state/cards.jsonl`）覆盖磁盘卡文件**（server.py `_compose_board_items`）。机审打回会在 sidecar 写 `state:待分派`，此后即使磁盘改回已回写 + 机审通过，sidecar 旧记录仍覆盖看板显示。**修复：`clear_card_state(log_dir, card_id)` 清除 sidecar 记录，等 20s 缓存 TTL 即恢复**。判卡状态只信 `:7788/cards` API（已含 sidecar 合成）。
1. **验证卡任务前提必须先核实（clw019 事故核心）**：首次任务"检查登录页 UI"——clwarp 是本地桌面驾驶舱**无登录页**，任务前提虚构 → AI 对着不存在的页面编了 4 条建议（幻觉式产出）。修正为真实组件后二次验证通过。**教训：出卡方必须先确认任务对象真实存在，验收标准必须含"产物可追溯"校验（每条建议引用真实文件:行号）**。
2. **deploy key 每仓库一个**：同一 SSH 公钥不能跨仓库复用 → 每仓库生成独立 key + SSH config host 别名（github.com / github.com-qxmap / github.com-clwarp）
3. **Windows 无 grep/head**：远程命令用 `findstr` / PowerShell，避免 grep 不可用
4. **SSH 超时 ≠ 任务中断**：claude -p 在远程可能继续跑，SSH 断开后需 tasklist 确认 + 轮询产物
5. **只读 Worker 的产物收口**：消费节点（read 权限）产出的报告，由主写源统一 commit/push，保证权威源单一写入口
6. **跨仓收口走 M1 主写源**：2017 clwarp 工作区可能被其他 Agent 切到开发分支（codex/*），报告提交应从 M1 clone→add→push，绕开多 Agent 共用工作区的分支混乱
7. **manual 派发适合节点路由测试**：`派发：manual` 让 Engine 不抢占，由指定 Worker 认领
8. **跨节点 Worker 需在 executors.json 登记**：2017 生产 executors.json 无 W9 → Engine `none_skips` 跳过卡。登记 W9（手动 GUI 分类，Engine 不 spawn，外部触发认领）后不再跳过

## 意义

这是集群 Worker 池（ccc-plan-020）的**首个跨节点实证**：突破 2017 单机并发瓶颈的技术路径已验证——任意终端注册 W 号 + 角色注入 = 立即成为可用 Worker。
