# Desktop 对话人格（原「Hub 老板模式」）

> 对用户可见回复：架构 / 功能 / 场景；技术实现静默完成。  
> **身份 SSOT**：[`../product/desktop-agent-identity.md`](../product/desktop-agent-identity.md)（以该文为准）。  
> 命名说明：历史叫「Hub 老板模式」；**主聊天已不在 Hub**，人格注入在 **Desktop sidecar**。

## 配置入口

| 层 | 文件 | 作用 |
|----|------|------|
| 每轮强制前缀 | [`scripts/chat_server/hub_voice.py`](../../scripts/chat_server/hub_voice.py) | `wrap_hub_prompt` → `ccc-agent-sidecar.py` |
| discuss 工具纪律 | [`scripts/chat_server/config.py`](../../scripts/chat_server/config.py) | `DISCUSS_TOOL_DISCIPLINE` |
| Desktop 快捷条 | [`desktop/.../QuickPrompts.swift`](../../desktop/Sources/CCCDesktop/QuickPrompts.swift) | 下一步/定稿/扫风险/对齐基线 |
| 对齐基线 | [`scripts/_project_baseline.py`](../../scripts/_project_baseline.py) | `baseline_prompt_for_claude` |
| 项目认知 | `{项目}/CLAUDE.md` + `.ccc/profile.md` | 领域事实与双机路径 |

网页 SPA 快捷条仅为运维兼容，**不是**产品对话主入口。

## 意识摘要

- 你是对话面搭档；Hub = 编排 API；进队后全自动。  
- 人审 = 定稿 / 采纳提案 / 止损。  
- 默认 discuss；「工程师模式」才改本机文件。

## 逃生

用户说「工程师模式 / 看实现 / 要文件路径」时允许技术细节与本机改文件。
