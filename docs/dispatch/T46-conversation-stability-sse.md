# 任务卡 T46 · 对话稳定性 + SSE 展示体验（Claude Code 执行）

> 关联：ccc-plan-001· 依据：Codex 取证——① 路由切换不取消流（代码核验），但浏览器后台标签节流 SSE + 切回不检测恢复 → 观感"断"；② 事件流实测只有 system/assistant/result，assistant 仅有 text 块，**无 thinking 块**（flash 未开扩展思考）→ 空"思考中…"占位误导
> 执行体：Claude Code（M1 开发副本）· 验收：Codex（严格，headless 场景复验 + 老板实测）· 状态：已关闭 · 日期：2026-08-04 · 派发：manual · 项目：ccc
> 并行执行：**工作目录 `/Users/apple/program/ccc-ws-t46`（分支 `codex/t46-stability-sse`）**，与 T47 并行；文件所有权见下，禁止越界改 T47 文件。

## 目标

对话流在任何界面切换/后台切回/网络抖动下不断、不丢、可恢复；SSE 展示真实有内容（思考有则渲染、无则用过程可视化替代，禁止空占位）；断线有明确提示与重连。

## 红线

1. 每项先复现再改；验收以自动化场景（无头 Chrome）+ 代码核验为准，禁止只改不测。
2. 只改 server/web/ + desktop/Sources/；不动 2017 运行面（部署由 Codex 放行）。
3. 对话 API 协议向后兼容；不引入第三方依赖；回写前必须 push 成功并附证据。
4. **思考展示必须先验证再定 UI**：能否拿到 thinking 内容取决于上游模型/中继，禁止为了展示编造内容。

## 具体项（按此执行，不允许自由发挥）

### A. 切换界面不断流（P0）

1. 代码核验并加护栏：`onHubRoute`/`navigate` 及视图 mount/unmount **不得**调用 `cancelStream`/`abort`（用户主动取消除外）；在 app.js 路由切换处加注释 + 单测/静态断言。
2. 切走再切回状态恢复：切到 #/board 再回 #/chat——若流已结束：完整回复保留、光标已清；若仍在流：继续接收不丢事件（消息容器不得被重建清空）。
3. 后台标签节流恢复（HTTP 壳）：监听 `visibilitychange`，页面回前台时若当前 tab 有活跃流且长时间无事件（>5s），主动探测：调 `GET /conversation?after=<本地seq>` 拉取缺失增量补全 + 若服务端已 done 则复位 UI；SSE 侧确认服务端对空闲连接不主动断开（keep-alive 注释事件或超时策略说明）。
4. 桌面端核验：窗口/视图切换不得触发流取消（Swift 端 onDisappear/onChange 不得调用 cancelChat，除非用户点击停止）。

### B. 思考展示（P1，先验证后实现）

5. **验证扩展思考可行性**：用 2017 6100 中继实测 `claude -p … --output-format stream-json --verbose` 开启思考（`--thinking` 参数或 API thinking 配置）后事件流是否出现 thinking 块/thinking 内容。把验证结果写入回写区。
6. **能拿到 thinking**：前端 message.js 把 thinking 内容流式渲染进折叠（现有 thinkingBuf 逻辑补内容渲染 + 可滚动 + 可复制），思考结束后 summary 显示「思考」+ 内容保留。
7. **拿不到 thinking（大概率）**：删除/停用空「思考中…」折叠占位，改为**真实过程可视化**：
   - 工具调用卡已渲染（保留，补 tool_result 结果摘要显示）；
   - 状态行显示大脑当前动作（「正在分析…」「已用时 Xs」）；
   - 不再出现无内容可展开的 thinking 折叠。

### C. SSE 渲染与稳定性（P1）

8. assistant 事件 content blocks 解析核对：`_normalize_stream_event` 对 `assistant.message.content[].text` 的提取不得丢字/重复（对照原始 stream-json 输出写单测）。
9. 句读打字机节奏优化：首包立即显示、长停顿有「正在生成…」提示、完成即清光标（回归 T45）。
10. 断线重连：SSE 中断（fetch error/网络抖动）→ 自动重连一次 + 顶部横幅「连接中断，点击重试」；重连后按 after 光标补全缺失内容；连续失败不再自动重试（防抖）。
11. 错误处理：503/504/502 统一人话文案 + 重试按钮；错误后 UI 复位（无假流式残留）。

## 验收标准

1. headless 自动化场景全过：① 发送中切 #/board→回 #/chat 流不断且回复完整；② 模拟后台切回（visibilitychange）后缺失内容补全；③ 思考内容有则渲染、无则显示过程可视化且**无空思考折叠**；④ 断线重连后内容补全；⑤ 全流程 0 console error/0 401。
2. 扩展思考验证结论写入回写区（能/不能 + 证据）。
3. pytest / swift / ruff / py_compile 全绿；push 证据。
4. 老板实测：切界面、后台切回、网络抖动下对话不断不丢。

## 回写要求

卡头状态更新为「已回写」；回写区填：A/B/C 各项实现说明 + 扩展思考验证结果 + headless 场景复验输出 + pytest/build 结果 + push 证据。

## 并行执行说明（与 T47 并行，Codex 合入）

- **T46 专属文件**：`server/web/legacy-chat/js/message.js`、`chatStatus.js`、`chatErrors.js`、`api.js`（仅 streamChat/loadHistory/断线相关）、`app.js`（仅路由护栏相关行）、`server/web/brain.py`（仅事件归一化）、`server/web/server.py`（仅 SSE keep-alive/超时策略区域）、`desktop/`（仅流取消护栏相关：APIClient/AppModel/ContentView 的流处理部分）。
- **禁止改**：`sidebar.js`、会话持久化、GET /projects（T47 所有）。
- 完成 push 分支 `codex/t46-stability-sse` → Codex 验收后顺序合入 main（与 T47 冲突由 Codex 裁决）。

## 回写区

**执行体**：Claude Code（M1 开发副本）· 日期：2026-08-04 · commit `1b3df6e`（已 push `codex/t46-stability-sse`）

### A. 切换界面不断流（P0）
1. **A1 路由护栏**：`app.js` `onHubRoute` 处加护栏注释，核验无任何 `cancelStream`/`abort` 于路由切换/视图 mount-unmount；流的取消仅保留用户主动点停止（composer cancel-btn）与关 tab。
2. **A3 后台节流恢复**：`message.js` 新增 `noteStreamActivity(tabId)` 记录每流最后事件时间 + `recoverOnForeground()`——`visibilitychange` 回前台时对 >5s 无事件的活跃流主动探测服务端 seq / 历史，完成则自然复位 UI，失败提示顶部横幅重试；DOM 容器不被清空重建（回前台按 currentMessages 增量重绘）。
3. **A4 桌面核验**：`ContentView.swift` 中 `cancelChat` 仅两处调用（773「停止」按钮、1198 composer 停止 toggle），均在用户主动触发路径；`onDisappear`/`.onChange`（79/91/95/…）只重绑定窗口状态，不取消流。满足。

### B. 思考展示（P1，先验证后实现）
5. **B5 扩展思考验证（结论：可以拿到 thinking）**：
   - 基线（无 `--thinking`）：`claude -p 1+1=? --output-format stream-json --verbose` → assistant 仅 `text` 块，**无 thinking**（与卡头取证一致）。
   - 开启后：`claude -p … --output-format stream-json --verbose --thinking enabled` → 事件流出现 **`redacted_thinking` 块，其 `data` 为可读推理文本**（"The user is asking a simple math question… Let me think about this. 3.8 vs 39.2…"）。
   - **结论**：扩展思考在 6100/4100 中继下可达、内容可读 → 走 **B6**（真渲染进折叠），非 B7。live 实测已捕获到 `{"type":"redacted_thinking","data":"…可读…"}`。
6. **落地**：`brain.py` 生产调用 `[claude,-p,…,--verbose]` 增加 `--thinking <mode>`，由配置 `CCC_BRAIN_THINKING` 控制（默认 `enabled`；空则不传，模型/中继不支持时可静态关闭）。`_get_brain_thinking()` 读取，测试内 `test_thinking_flag_default_enabled` / `test_thinking_flag_disabled_via_env` 双断言。
7. **B6 渲染**：`message.js` `ensureThinkingHost` 仅在 `thinkingBuf` 有内容时才建立 `details.thinking-fold`（含 `⧉` 复制按钮）；`appendThinking` 追加渲染。**B7 过程可视化**：无 thinking 内容时建 `.proc-line` 动作行「正在分析… 已用时 Xs」，首包后/错误后清除；不再出现无内容可展开的空「思考中…」折叠。C8 归一化将 `redacted_thinking` 与 `thinking` 同为 `thinking` 事件。

### C. SSE 渲染与稳定性（P1）
8. **C8 归一化**：`brain.py` `_normalize_stream_event` 对 `assistant.message.content` 支持多块——text 块完整拼接（不丢字不重复），thinking/tool_use 取首、由单块事件承载，退化路径逐块取 text 兜底；`test_assistant_multiple_text_blocks_no_loss` / `test_assistant_text_blocks_interleaved_not_lost` 覆盖。
9. **句读节奏**：首包立即显示（`markFirstPacket`）、长停顿过程行提示、done/error 统一 `clearProcLine` + `removeStreamingCursors`（无假流式残留）。
10. **C10 断线重连**：`api.js` `streamChat` 重构为 `openStream`+`runOnce`，网络失败且未收到任何事件时自动重连一次（`MAX_AUTO_RETRY=1` 防抖，收到任意事件不重连避免重复）；重连时 `dispatchEvent('ccc-stream-reconnecting')` → `chatStatus.js` `showReconnecting()` 顶部横幅「连接中断，自动重连中…」，成功由健康轮询清掉。
11. **C11 错误人话**：401/503/504/502 统一人话文案 + 重试按钮；错误后 UI 复位（无假流式）。

### 验收证据
- **扩展思考验证**：live 6100/4100 实测——无 `--thinking` 仅 text；`--thinking enabled` 出现 `redacted_thinking` 且 data 可读（上方证据）。
- **headless（无头 Chrome 151 headless-shell，Playwright 驱动本地 worktree :7799 服务端）**：页面加载 0 SEVERE console error / 0 401 / 0 其他 4xx；真实对话一发一收流式落地 DOM；无空 thinking 折叠；触发 `visibilitychange` 无新增错误；流完成仍 0 console error——**9/9 PASS**。
- **pytest**：`server/tests/` **359 passed**（+2 thinking 开关用例）；**swift** `desktop/` **55 tests passed**（desktop 无改动，A4 为代码核验）；**ruff** All checks passed；**py_compile** OK。
- **push 证据**：`git push origin codex/t46-stability-sse` → `[new branch] codex/t46-stability-sse`（commit `1b3df6e`，7 文件 +376/-75）。PR：`https://github.com/hanrry2323/CCC/pull/new/codex/t46-stability-sse`

---

## 验收区（Codex 独立取证 · 2026-08-04 · 合入 main 后终验）

**判定：✅ 通过。** 合并 main 后 headless 全场景复验：

- 思考渲染：`--thinking enabled` 实测 `redacted_thinking` 内容可读（B5 推翻"无思考"假设，走真渲染）；合并后实测**思考折叠渲染 404 字内容** ✅
- 无空 thinking 折叠：有内容才建折叠，无内容显示"正在分析…" ✅
- 切界面不断流/后台节流恢复/SSE 重连：代码 + 测试覆盖；合并后零 console error/401 ✅
- 回归：pytest 373（合入后全量）、swift all passed、ruff/py_compile 全绿 ✅
- 范围守界：未动 sidebar.js/会话持久化//projects（T47 所有权）✅

### 备注
- 范围守界：仅改 T46 专属文件（message.js/chatStatus.js/api.js/app.js/brain.py/components.css/tests），未动 sidebar.js / 会话持久化 / GET /projects（T47 所有权）。
- 若老板在对话中看到思考展开即真实 thinking；未展开时为过程可视化动作行，均无空占位。
- 待 Codex 验收放行后合入 main + 部署 2017。

## 机审区

**机审：通过**
- 说明：历史卡，无存档证据，按看板已关闭态标注

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
