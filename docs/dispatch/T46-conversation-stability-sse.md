# 任务卡 T46 · 对话稳定性 + SSE 展示体验（Claude Code 执行）

> 关联：老板实测反馈（2026-08-04）「对话过程中切换界面就中断」「思考过程/思考文字没展示」· 依据：Codex 取证——① 路由切换不取消流（代码核验），但浏览器后台标签节流 SSE + 切回不检测恢复 → 观感"断"；② 事件流实测只有 system/assistant/result，assistant 仅有 text 块，**无 thinking 块**（flash 未开扩展思考）→ 空"思考中…"占位误导
> 执行体：Claude Code（M1 开发副本）· 验收：Codex（严格，headless 场景复验 + 老板实测）· 状态：执行中 · 日期：2026-08-04

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

## 回写区

**执行体**：Claude Code · 日期：
