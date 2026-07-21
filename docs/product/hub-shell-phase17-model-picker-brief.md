# Hub-Shell Phase17 — Desktop 对话模型快选（Brief）

> **日期**：2026-07-21 · **执行者**：Cursor · **VERSION**：建议 bump **v0.52.2**  
> **对齐**：[`dev-channel.md`](dev-channel.md)

## 目标

用户在 Desktop **应用内**选择对话模型逻辑名；**默认 MiniMax-M3**（存盘键 `flash`）；不改 `~/.zshenv` / 个人 Claude Code；不把 118 做成默认。

## 必须做

| # | 成功标准 |
|---|----------|
| A | Composer + Settings 可见「对话模型」短列表；首项 **MiniMax-M3** |
| B | `@AppStorage("ccc.preferredModel")` 持久化；重启仍记住 |
| C | 发消息走 `resolvedModel()` → sidecar 请求体 `model`（既有通路） |
| D | 文案标明：现网逻辑名均映射同一 MiniMax 上游；plist 定出口、UI 定请求级标签 |
| E | 切换时 toast；失败沿用既有 Agent 错误路径 |
| F | brief/验收/状态板/CHANGELOG；装机 `stat` 一致 |

## 不做

- 默认启用 118/ops4.8  
- 多供应商计费面板  
- 改 Engine OpenCode 模型选择  
