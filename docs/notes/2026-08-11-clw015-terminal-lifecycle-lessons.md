# clw 015 教训沉淀 (2026-08-11 · 终端生命周期修复)

> 来源：clw015 终端生命周期修复（StrictMode 泄漏 / 视图切换保活 / 事件时序 / loading 死锁）。
> 触发：Tauri + React 19 桌面应用在 PTY 会话生命周期管理上的时序与卸载竞态问题。

## 教训

### 1. React StrictMode 双挂载会导致后台 PTY 泄漏

- **现象**：dev 模式每次打开终端泄漏一个会话（后端 PTY + 全局事件监听器）。
- **根因**：StrictMode 会挂载→卸载→再挂载。`startTerminal` 是 async，第一次挂载的 `invoke('spawn_terminal')` 未决时，同步 cleanup 先跑，此时 `activeSessionId` 仍为 null → 不杀后端 PTY；随后第一次挂载的 async 完成，泄漏一个后台 PTY + 两个全局监听器。
- **解决方案**：在 cleanup 中用同步 `isUnmounted` flag 标记卸载；所有异步 `invoke`/`listen` 成功后校验该 flag，若已卸载则即时 `kill_terminal` 清理。同时 `main.tsx` 保留 StrictMode（React 官方推荐），用竞态守卫而非移除 StrictMode。

### 2. 视图切换（切 tab/面板）不应卸载终端组件

- **现象**：切看板/设置面板时 TerminalView 卸载 → cleanup 执行 `kill_terminal` → 终端会话被强杀，切回后现场丢失。
- **根因**：把"切换视图"实现为"卸载/挂载"组件，触发了终端的卸载清理逻辑。
- **解决方案**：用 `display: none` / `display: contents` 样式保持 TerminalView 实例常驻（不卸载），配合 App 层保活机制，实现视图无感切换不杀会话。

### 3. 终端会话事件时序：先入表再读线程 + 启动握手

- **现象**：子进程秒退时（如 resume 无效 id），死会话被塞进 sessions map（前端显示已连接但写不进）；spawn 后初始输出丢失（前端先 invoke 再 listen）。
- **根因**：读线程先于 `sessions.insert` 启动（竞态）；前端 listen 事件在 invoke 返回后才挂载，期间初始输出丢失。
- **解决方案**：
  - 先同步 `sessions.insert` 再启动读线程，防秒退死会话入 map；
  - 用 `std::sync::mpsc` 让读线程就绪后再返回 invoke；
  - 引入 `frontend_ready` 启动握手 + 会话级 `output_buffer`，前端 listen 建立后再 flush 缓冲数据，根治首包丢失。

### 4. 后端读线程错误不能静默吞掉

- **现象**：`app_handle.lock()` 失败（毒化）或 `try_clone()` 失败时会话照样插入但没有读线程，前端永久无输出无退出，错误被吞。
- **解决方案**：读线程启动失败的路径必须返回错误或显式标记失败会话，不能 `if let Ok(...)` 三层静默降级。

## 关联

- 卡：clw015 · 方案：clw-plan-003 · 项目：clw
- 相关：clw013（设置接线）、clw016（CSP/配置加固）
