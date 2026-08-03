# 任务卡 T29 · 对话接大脑 Agent（/conversation 从裸模型直答改为调用 2017 Claude Code，带心智/工具/知识库）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 任意设备=壳，经 HTTP 直连 2017 大脑对话）· 依据：老板 2026-08-03 反馈「桌面端对话和弱智一样」；Codex 实锤根因：**/conversation 只做裸模型转发（6102 → deepseek-v4-flash），无 Agent 心智/工具/知识库**· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03

## 根因（Codex 已实锤）

当前对话链路：`App → 2017:7788 /conversation → 6102 /v1/chat/completions → deepseek-v4-flash（裸模型，无 system prompt、无工具、无知识库、无 Agent 心智）`。

这违反老板定方向「对话口接 2017 最强大脑 Agent（能读知识库、能用工具、有完整心智）」。6100 Anthropic 出口实测可用（Claude Code CLI 直连 6100 正常回复），接大脑基建已就绪。

## 目标

把 `/conversation` 从「裸模型转发」升级为「**2017 Claude Code Agent 对话**」：请求经 `server/web/server.py` 调用 2017 本机 Claude Code CLI（`claude -p`，走 `127.0.0.1:6100`），携带系统角色（CCC 大脑：方案/知识/工具心智）+ 历史上下文，回复真实 Agent 输出。桌面端与网页对话即恢复为智能对话。

## 红线（先看）

1. **只改 2017 `server/web/server.py` 的 `/conversation` 实现层**（或新建大脑代理模块）；不改桌面端/网页协议（仍是 POST /conversation + Bearer）。
2. **对话走 2017 Claude Code + 6100**（契约 §8 大脑在 2017；中转站决议 6100 为 CCC 体系出口）；不直接走 6102 裸模型。
3. **Claude Code 调用方式**：`claude -p "<prompt>" --output-format text`（或等价非交互模式），env 指向 `ANTHROPIC_BASE_URL=http://127.0.0.1:6100`、`ANTHROPIC_AUTH_TOKEN=ccc-relay-flash`、`ANTHROPIC_MODEL=flash`；超时与并发保护（单会话串行，超时返回 504 明确错误）。
4. 系统提示词（CCC 大脑人格）写入 `server/config/` 或 server 内常量：知识库可用（HP 6100 出口/本地检索如就绪）、方案讨论、任务拆解、多壳对话；不硬编码密钥。
5. 不碰：桌面端/网页壳、Engine、board-scheduler、M1 4100/4102、2017 中转站配置、Claude Code 全局配置（`~/.claude/settings.json` 不动）；不读写外脑。
6. 完成必须提交（真实 commit）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 步骤

### A. 大脑代理实现（2017 server）

1. `server/web/server.py`（或新建 `server/web/brain.py` 被 server.py 引用）`_handle_conversation_post` 改造：
   - 组装系统提示词（CCC 大脑人格：你是 CCC 的大脑 Agent，负责方案讨论/知识核查/任务拆解/多壳对话；可读项目文档与知识库；回答中文、结论先行、禁止选择题）；
   - 组装用户上下文：最近 N 轮历史 + 当前消息（复用现有 history）；
   - 调用 2017 Claude Code：`subprocess.run([claude, "-p", prompt, "--output-format", "text"], env={...6100...}, timeout=60)`；
   - 成功 → `{"reply": stdout}`；失败/超时 → 504/502 明确错误，不落历史。
2. 并发保护：同一时刻仅处理一个对话请求（模块级锁或串行队列），避免多壳同时打爆 Claude Code。
3. 保留：鉴权中间件、`/session`、`/health`、board/ops 只读接口。

### B. 配置化

4. `server/config/config.example.env` 增补（如缺）：`CCC_BRAIN_CLAUDE_BIN`（默认 `claude`）、`CCC_BRAIN_MODEL=flash`、`CCC_BRAIN_TIMEOUT=60`、`CCC_BRAIN_BASE_URL=http://127.0.0.1:6100`、`CCC_BRAIN_AUTH_TOKEN=ccc-relay-flash`（占位，2017 config.env 实际填）；server.py 读 env，零硬编码。
5. 2017 `config.env` 同步补配置（不进 git）。

### C. 测试

6. `server/tests/test_http_api.py` 新增：`/conversation` 走大脑代理的用例（mock 或真实 Claude Code：鉴权 401、缺配置 503、成功 200 reply、超时/失败 502/504）。
7. `pytest server/tests/ -q` 全绿（现 206+ 新增）。

### D. 部署 + 验证（2017）

8. M1 push → 2017 pull → 2017 web-server kickstart 加载新代码。
9. 2017 本机实测：`POST /conversation`（带 token）问「1+1=？只答数字」→ 回复来自 Claude Code Agent（非裸 flash 直答特征）；问「CCC 重构的目标是什么」→ 能结合知识库/心智回答。
10. 桌面端/网页跨机实测：对话智能程度明显提升（多轮上下文、结论先行、可读文档）。

### E. 提交 + 回写

11. 提交：`chore(server): T29 对话接大脑 Agent——/conversation 调用 2017 Claude Code（带心智/工具/知识库）`
12. 回写：卡头 `状态：待分派 → 已回写`，回写区填（实现说明、配置、测试输出、双端实测、验收自检表）。

## 回滚

- `git revert` 本卡提交 → 双端 kickstart（回到裸模型直答，但功能可用）。
- 触发条件：Claude Code 调用失败率高 / 对话延迟不可接受（>60s 频繁） / 桌面端或网页对话断 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `/conversation` 回复来自 2017 Claude Code Agent（代码核验 + 实测：回复质量/上下文/工具心智特征明显区别于裸 flash 直答）。
2. 走 6100（Claude Code 出口），不再直连 6102 裸模型；env 配置化零硬编码。
3. 鉴权/历史/超时/并发保护齐全；`pytest` 全绿。
4. 桌面端与网页对话实测可用且智能度明显提升。
5. 真实提交；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

（执行后填写）

### 执行明细

（执行后填写：A–E 各步结果）

### 验收自检

（执行后填写：对照验收标准逐条勾选）
