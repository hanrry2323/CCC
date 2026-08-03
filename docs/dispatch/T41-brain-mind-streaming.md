# 任务卡 T41 · 大脑心智升级 + 流式输出体验（OpenCode 执行）

> 关联：新阶段「双壳可用 + 心智升级」· 依据：Codex 实地取证——brain 系统提示词仅「方案讨论/知识核查/任务拆解」，无规划/写卡/验收/看板维护能力契约；/conversation 为同步 subprocess 捕获，无 SSE 流式；前端无工具调用/思考过程渲染；桌面 APIClient 同步 POST
> 执行体：OpenCode · 验收：Codex（严格）· 状态：执行中 · 日期：2026-08-03
> 变更记录：2026-08-03 老板指示 Trae 流量用完 → 改派 OpenCode；状态置「执行中」防 2017 Engine 抢跑（T38 教训）。

## 目标

大脑 Agent 心智达到「可规划、可写任务卡、可验收、可维护看板」的执行级智能体；双壳对话支持 SSE 流式输出、工具调用与思考过程可视化、文字流畅性优化；MCP/skills 工具调用在对话中可见。

## 红线（先看）

1. **心智升级只改 prompt 与契约注入，不绕过看板纪律**：写任务卡走 docs/dispatch 卡格式（契约 §1）；验收/看板维护仅通过对话输出结论与卡操作说明，不自动改代码（脑不抢执行，D 纪律）；违反即打回。
2. /conversation 协议兼容：新增流式入口不得破坏现有同步 POST（旧客户端可继续用）；鉴权/Bearer 不变；并发单会话锁保留。
3. 零外脑：大脑只读 knowledge/ + 自己仓文档，禁止读 qx-map/hp-kb（D2/D3）。
4. SSE 实现无新第三方依赖（Python stdlib 流式 + 前端 EventSource/fetch stream）；Swift 端用 URLSession 流式或等价。
5. 回写前必须 push 成功并附证据（P2-4 纪律）。

## 范围

server/web/brain.py（系统提示词升级 + 流式输出函数）、server/web/server.py（/conversation/stream 或 stream 参数支持）、server/web/legacy-chat/（中栏流式消费/思考折叠/工具卡片/markdown）、desktop/Sources/（APIClient 流式 + ConversationStore/ChatState + 渲染组件）、server/tests/ + desktop/Tests/、server/engine/README.md（如需）。

## 步骤

1. **心智升级（prompt 契约）**：重写 BRAIN_SYSTEM_PROMPT 为「CCC 全能智能体」：
   - 角色职责四段：规划（理解目标→拆步骤→产出任务卡草案）、写任务卡（卡头字段/状态机/红线/验收标准，格式引用契约 §1）、验收（对照验收标准逐项判定→通过/打回+问题清单）、看板维护（状态流转、打回附原因、不越范围）。
   - 工具契约：优先知识库检索（BM25 命中引用），再按需 Claude Code 内置工具（Read/Write/Bash/WebFetch）+ MCP；输出规范：结论先行、可执行、不甩选择题；写卡前先读 docs/dispatch 现有卡防撞号。
   - 知识库参考注入保留并强化（条目 id 显式标注，防编号混淆）。
2. **SSE 流式**：server 新增流式对话入口（如 POST /conversation?stream=1 或 /conversation/stream）：claude 以 stream-json（thinking/tool_use/text 事件）逐事件转发；断线/超时/并发锁处理；同步 POST 保持兼容。
3. **前端渲染（HTTP + 桌面）**：
   - 流式打字机：句读缓冲（按句渲染，避免逐字闪烁）+ 停止/重试。
   - 思考过程：thinking 事件折叠显示（可展开，灰色斜体风格）。
   - 工具调用卡片：tool_use 事件渲染为卡片（工具名 + 参数摘要 + 结果状态；MCP/skills 调用可见——如「搜索知识库」「读取文件」）。
   - markdown 渲染增强：代码块/表格/引用；长输出滚动锚定。
4. **心智基准测试**：规划题（给目标→产出任务卡草案）/ 拆卡题 / 验收题（给卡+改动→判定）/ 看板维护题（状态流转指令）4 类各 2 题，经 2017:6100 真实大脑实测记录。
5. 提交 + push（附证据）。

## 验收标准

1. 心智 4 类基准题实测达标：产出任务卡符合契约 §1 格式（字段齐全/状态机合法/带红线与验收）；验收判定给出通过或打回+问题清单；看板维护回答不越范围。
2. SSE 端到端：流式事件（thinking/tool_use/text）在双壳 UI 可见；工具调用渲染为卡片；同步 POST 兼容不回归。
3. 文字流畅性：打字机句读缓冲、markdown 渲染、长输出锚定；无逐字闪烁/乱序。
4. pytest 全绿 + 新增流式/心智用例；Swift build 通过；三扫描零命中。
5. 真实提交 + push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：prompt 契约全文要点、SSE 实现与协议、前端渲染实现、心智 8 题实测记录（题/答/判定）、pytest/build 结果、push 证据。

## 回写区

**执行体**：OpenCode · 日期：
