# Hub 老板对话模式（v0.51+）

> 对用户可见回复：架构 / 功能 / 场景；技术实现静默完成。

## 配置入口

| 层 | 文件 | 作用 |
|----|------|------|
| Hub 每轮强制前缀 | [`scripts/chat_server/hub_voice.py`](../../scripts/chat_server/hub_voice.py) | `wrap_hub_prompt` 注入 `chat.py` |
| 快捷按钮话术 | [`scripts/chat_server/frontend/js/components/quickPrompts.js`](../../scripts/chat_server/frontend/js/components/quickPrompts.js) | 下一步/风险/审阅等 |
| 对齐基线 | [`scripts/_project_baseline.py`](../../scripts/_project_baseline.py) | `baseline_prompt_for_claude` |
| 全局 Claude | `~/.claude/CLAUDE.md` | Hub+CLI 共用回复规范 |
| 项目认知 | `{项目}/CLAUDE.md` | 领域事实（勿写「必须输出文件树」） |

## 逃生

用户说「工程师模式 / 看实现 / 要文件路径」时允许技术细节。
