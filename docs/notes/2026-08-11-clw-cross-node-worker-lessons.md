# 2026-08-11 clw 跨节点 Worker 路由测试 · 教训

> 关联卡：clw019 · 关联方案：ccc-plan-020（集群 Worker 池蓝图）

## 验证结论（全链路成功）

clw019「前端设计角色注入验证」由 **W9（252 移动终端 Claude Code）** 跨节点认领执行成功：

1. **角色→Skill 注入生效**：卡头「角色：前端设计」→ 执行提示注入 `ui-ux-pro-max` → 252 加载该 Skill 按设计准则审查
2. **跨节点路由可行**：252 经 GitHub deploy key 访问 clwarp 源码 → 只读审查 → 产出高质量报告
3. **主写源收口**：252 只读消费，报告由 M1/2017 统一提交（符合权限矩阵）
4. **报告质量**：4 项建议（配色/排版/UX/一致性），含文件:行号引用，符合 ui-ux-pro-max 准则

## 可复用教训

1. **deploy key 每仓库一个**：同一 SSH 公钥不能跨仓库复用 → 每仓库生成独立 key + SSH config host 别名（github.com / github.com-qxmap / github.com-clwarp）
2. **Windows 无 grep/head**：远程命令用 `findstr` / PowerShell，避免 grep 不可用
3. **SSH 超时 ≠ 任务中断**：claude -p 在远程可能继续跑，SSH 断开后需 tasklist 确认 + 轮询产物
4. **只读 Worker 的产物收口**：消费节点（read 权限）产出的报告，由主写源统一 commit/push，保证权威源单一写入口
5. **manual 派发适合节点路由测试**：`派发：manual` 让 Engine 不抢占，由指定 Worker 认领

## 意义

这是集群 Worker 池（ccc-plan-020）的**首个跨节点实证**：突破 2017 单机并发瓶颈的技术路径已验证——任意终端注册 W 号 + 角色注入 = 立即成为可用 Worker。
