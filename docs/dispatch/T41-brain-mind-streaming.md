# 任务卡 T41 · 大脑心智升级 + 流式输出体验（OpenCode 执行）

> 关联：新阶段「双壳可用 + 心智升级」· 依据：Codex 实地取证——brain 系统提示词仅「方案讨论/知识核查/任务拆解」，无规划/写卡/验收/看板维护能力契约；/conversation 为同步 subprocess 捕获，无 SSE 流式；前端无工具调用/思考过程渲染；桌面 APIClient 同步 POST
> 执行体：OpenCode · 验收：Codex（严格）· 状态：已回写 · 日期：2026-08-03
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

**执行体**：OpenCode · 日期：2026-08-03

### 1. 心智升级（BRAIN_SYSTEM_PROMPT，`server/web/brain.py:49-77`）

四段职责契约注入：
- **规划**：理解目标 → 拆可执行步骤 → 产出任务卡草案（粒度防过粗/过碎）。
- **写任务卡**：卡头字段/状态机/红线/验收标准，格式引用 `references/board-task-schema.md` 契约 §1/§2；五态机 待分派→执行中→已回写→已关闭（打回→待分派）；元数据行 `关联/执行体/状态/日期`；写卡前先读 `docs/dispatch/` 现有卡防撞号。
- **验收**：对照验收标准逐项判定 → 通过或打回+问题清单；不凭回写自述。
- **看板维护**：按状态机流转、打回附原因、不越范围（脑不抢执行）。
- **工具契约**：BM25 知识库检索优先，命中显式标条目 id；再按需 Claude Code 内置工具（Read/Write/Bash/WebFetch）+ MCP（memory/fetch）。
- **输出规范**：结论先行、中文、不给选择题、信息不足给假设+依据。
- **零外脑红线**：只读 knowledge/，禁止 qx-map/hp-kb。

### 2. SSE 实现与协议（`server/web/brain.py` + `server/web/server.py`）

- `stream_brain_events()`（brain.py:449）：`claude --output-format stream-json` 逐事件归一化 yield（`_normalize_stream_event` brain.py:289），事件：meta{model,tools,mcp_servers,skills} / thinking{data} / tool_use{id,name,input} / text{text} / tool_result{tool_use_id,content 截断 2000} / done{is_error,text,error} / error{status,message}。
- `/conversation?stream=1`（server.py:576 `_handle_conversation_stream`）：SSE `event: X\ndata: JSON\n\n`（server.py:601）；未配置→503、忙→503、超时→504、失败→502；断线/取消即释放单会话锁。
- **兼容**：不带 stream → 原同步 POST 全保留（鉴权/Bearer/锁不变）；仅 `done{is_error:false}` 写回历史。
- 服务端测试：`test_brain_stream.py`（20 用例）+ test_http_api.py 流式 5 用例。

### 3. 前端渲染实现

**legacy-chat（HTTP 壳）**：`api.js` streamChat/cancelStream（fetch ReadableStream 解析 SSE）；`message.js` 句读打字机缓冲（takeSentenceFragment/typewriterTick，按句渲染防逐字闪烁）、thinking 折叠（`<details>` 默认收起灰色斜体）、tool_use/tool_result 工具卡片（toolCall.js 进度轨）；`components.css` 对应样式。

**桌面 Swift 壳**：`APIClient.swift`（+180 行）BrainStreamEvent 枚举 + streamSession（request 60s/resource 600s，MockURLProtocol 注入点）+ `streamConversation`（401 清 token / 非 2xx 读 body 抛错 / bytes.lines 消费 / 取消→finish）+ parseStreamEvent；SSE 解析按 `event:` 行边界 flush（修复 `bytes.lines` 丢弃空行致事件合并 bug）。`AppModel.swift`（+225 行）consumeStream/finalizeStreamAssistant/takeStreamFragment/流式状态 + cancelChat 取消网络。`ToolProgressRail.swift` labelForToolUse（参数优先级 command>file_path>path>pattern>query>description，40 字截断）。

### 4. 心智 8 题实测（经 2017:6100 真实大脑，flash）

| 类 | 题 | 判定 | 耗时 |
|----|----|----|----|
| 规划 P1 | 长轮询历史增量 → 任务卡草案 | **通过**：核实单线程 HTTPServer 阻塞约束；编号取 T43 避开 T42 撞号；卡头/红线/可执行验收齐全；**实际落盘 `docs/dispatch/T43-conversation-long-poll.md`** | 148.7s |
| 规划 P2 | 桌面深色模式 → 规划+卡草案 | **通过**：核实 385 处颜色引用集中于 CCCTheme 静态常量、SettingsView/UserDefaults 可扩展；四步技术路线 + 风险（静态引用不自动刷新）+ T44 卡草案 | 109.1s |
| 拆卡 S1 | board loader 重构拆卡 | **通过**：拆 3 张（T44 配置基座→T45 导出/调度→T46 Web 读链路），依赖序 + 文件零重叠 + 粒度依据明确 | 171.4s |
| 拆卡 S2 | legacy-chat 流式前端拆卡 | **通过**：识别出即为 T41 范围、**拒绝新建卡**（撞范围/双派发/单事实源纪律），给 T41 细化验收清单 + 附条件 T44 草案 | 157.7s |
| 验收 A1 | T90 workspace 过滤验收 | **通过（打回判定）**：git 史实查明逻辑与测试由 T20 commit 96ff0de 引入，账实不符；docs/dispatch 无 T90 卡；问题清单 P1-P3 附补救 | 231.1s |
| 验收 A2 | T91 /health version 验收 | **通过（打回判定）**：产线 curl 实测 /health 无 version 字段、v0.71.0 全仓零命中、T91 卡不存在；还揪出 server.py:231 现存版本字面量欠账 | 117.4s |
| 看板 B1 | T92 回写后流转 | **通过**：验收席 verdict 文件（红线11）→ 已关闭/打回→待分派；执行体不自验收不自关闭；IllegalTransitionError；board.export 同步 | 147.3s |
| 看板 B2 | T93 打回后能否改 T94 | **通过**：不可并行；契约§2 人工重派闭环 + 红线 3 越范围 + 红线 10 跨会话隐式记忆，3 条依据 | 269.4s |

工具调用统计：每题 7-15 次 tool_use（Bash/Read/mcp__memory），全为知识库与仓内文档实读，无 qx-map/hp-kb。

### 5. pytest / build 结果

- `pytest server/tests/ -q --tb=short` → **331 passed**（含新增 test_brain_stream.py 20 + test_http_api.py 流式 5）
- `ruff check server/` → All checks passed
- `python -m py_compile server/engine/main.py` → OK
- `swift build` → Build complete；`swift test` → **52 tests, 0 failures**（含新增 StreamTests.swift 27 项）
- 三扫描：qx-map/hp-kb 仅存在于 brain.py 禁止读取红线文案；越范围扫描 0 命中（改动全在卡范围）

### 6. push 证据

commit `6e26448` feat(shell): T41 心智升级 + 双壳 SSE 流式；`git push origin main` → `d28b0e2..6e26448 main -> main` 成功。

> 注：大脑在 P1 实测中产出的真实落盘卡 `docs/dispatch/T43-conversation-long-poll.md`（状态：待分派）留作心智能力证据，不随本次提交；如需派发请单独处置。
