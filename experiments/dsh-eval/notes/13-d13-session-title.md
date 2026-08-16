# 实验 D13 · session-title 双 provider 语义

- **状态**：✅ 完成（源码级）
- **批次**：B4 会话
- **环境**：源码 + 会话日志
- **日期**：2026-08-16

## 结论

**session-title 是「确定性 fallback（首消息前 N 词）+ 可选 LLM provider」双轨**。本部署实测全部走 fallback（标题「你好」source.kind='fallback'），LLM 生成路径（title-llm-request）存在但未启用。

## 证据

- `dsh-session-title/lib/index.js:54-60`：`fallbackSessionTitle(input, maxWords, maxBytes)` 确定性 fallback
- `:126`：source.kind 含 `fallback`；`:129` 含 `provider`（LLM 路径）
- 实测会话标题 source.kind='fallback'（报告维度三已确认）
- `fallbackMaxWords` 可配（:145）

## 结论细节

- fallback：取首条用户消息前 N 词（确定性、零成本）。
- LLM 路径：可选 provider 生成标题，走 `title-llm-request` 记录。
- 本部署无 LLM 标题 provider 配置 → 全 fallback。无并发语义问题（fallback 是同步确定性的）。

## 风险 / 对 CCC 借鉴的影响

- 标题这种「低价值、可确定性」的元数据走 fallback 省一次模型调用——CC 出卡/命名等可借鉴「确定性默认 + 可选增强」模式。
