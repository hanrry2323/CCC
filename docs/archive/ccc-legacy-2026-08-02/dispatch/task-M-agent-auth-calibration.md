# 任务书 M：Desktop ↔ sidecar Agent 登录契约校准 + 联调（窗口 M）

> 起草：知识大脑（Codex 审核）· 2026-08-02 · 执行：Claude Code（CCC 轨）
> 前置：窗口 K（sidecar，`codex/ws-7-agent-auth`@`aeb6c89`）、窗口 L（Desktop，`codex/ws-6-desktop-agent-auth`@`090b0c8`）均完成但**未合入 main**。

## 背景（审核发现，硬事实）

两端契约对不上，配置正确账号密码也会登录失败：

| 项 | sidecar（K，已实现+已测，权威） | Desktop（L，待校准） | 结论 |
|---|------|------|------|
| 请求体 | `{"user","password"}` | `{"username","password"}` | **不匹配 → 必 401** |
| 响应 | `{token, role, expires_in}` | 解码 `token, expires_at?, ttl_s?` | expires_in 未解析 → 过期跟踪失效 |

report-K §四 已明确契约（`user` + `expires_in`）；Desktop 端按旧 task-K 草稿实现，L 已预告「report-K 回后校准」但未执行。

## 任务（按序）

1. **校准 Desktop 端**（`desktop/Sources/CCCDesktop/APIClient.swift`）：`performAgentLoginInner` 请求体 key `username → user`；`AgentLoginResponse` 解码 `expires_at/ttl_s → expires_in`（保留 scheme 可选）。
2. **校准测试**（`desktop/Tests/CCCDesktopTests/AgentLoginTests.swift`）：mock 登录响应改 `{token, role, expires_in}`，请求体断言改 `user`；8 用例语义不变。
3. **联调冒烟**（不起产线 7788；本地起 sidecar + TestClient/URLProtocol 真连）：Desktop 配置账号密码 → 对话请求带 Bearer 会话 token；错密码 → 明确报错；未配置 → 降级共享密钥；清 token → 401 重登一次有界。
4. **合并准备**：确认两分支与 main 无冲突后，按既定合入流程合入（main 当前未动）；合入后清理 main 工作树残留的 Desktop 未提交副本（M/?? 文件，与 090b0c8 分叉，勿混入）。

## 红线（不许破）

- 凭证无默认弱口令；不新增降级路径（已配置被拒 → 报错不降级，保持老板拍板矩阵）。
- 产线 7788 不动（plist `CCC_AGENT_AUTH` 保持 0）；部署序（配凭证 → `CCC_AGENT_AUTH=1` → 重启）不提前。
- 兼容窗口：旧共享密钥仍接受，legacy 分支移除是后续项，不在本窗口。

## 验收条件

1. 两端字段完全对齐（请求 `user`；响应 `expires_in` 解析并驱动 TTL/刷新）。
2. Desktop 8 用例 + 既有测试全绿；sidecar 18 用例不回归。
3. 联调冒烟四项全过（带凭证 Bearer / 错密码报错 / 未配置降级 / 401 有界重登）。
4. 提交 ≤2、显式路径、只碰校准文件；交接文档补「校准与联调记录」。
