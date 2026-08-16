# 实验 F24 · sandbox-exec 废弃 + bwrap 迁移评估

- **状态**：✅ 完成（废弃确认）
- **批次**：B6 模型
- **环境**：本机 + 网络
- **日期**：2026-08-16

## 结论

**`sandbox-exec` 本机确认 DEPRECATED**（macOS 13.7.8，man 页首行「execute within a sandbox (DEPRECATED)」）。DSH 的 macOS bash 沙箱（Seatbelt）依赖它；若 Apple 移除，macOS 受限模式全部 fail-closed（bash 不可用）。**迁移方向是 Linux bwrap（DSH 已内置 bwrap-Landlock 后端），macOS 侧无官方替代**。

## 证据

- `man sandbox-exec`：`execute within a sandbox (DEPRECATED)`
- 系统：macOS 13.7.8（Build 22H730）
- 报告维度四：bash 内核级沙箱用 `sandbox-exec`（Seatbelt）；DSH 自述「sandbox-exec 被 Apple 标 deprecated（哪天系统不再自带，macOS 受限模式全挂）」
- 报告维度四：Linux bwrap + Landlock 是 DSH 的另一后端

## 结论细节

- macOS 侧：sandbox-exec 仍在（13.7.8 自带），但已标记废弃，未来版本可能移除。
- 迁移：DSH 有 Linux bwrap 后端，但那是 Linux 不是 macOS；macOS 无等价的官方沙箱 exec 替代（App Sandbox 是容器/签名场景，不适用 CLI exec）。
- 缓解：macOS 上的 DSH bash 沙箱应视为「有失效日期」，关键路径跑 Linux（bwrap）或加强 code 层隔离（A1/A3 已证 code 层本来就免沙箱）。

## 风险 / 对 CCC 借鉴的影响

- **macOS 上 DSH 的内核沙箱有生命周期风险**；加上 A1/A3（code 层免沙箱），「DSH 沙箱」在 macOS 上实际是双重薄弱。
- CCC 吸收 DSH 做执行体：安全隔离优先容器/VM 层，不依赖 DSH 内置 macOS 沙箱。
