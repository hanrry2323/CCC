# CCC Desktop 客户端（Tauri）

> 产品主 UI 面。网页 Hub 为过渡。服务端见 [`topology.md`](topology.md)。  
> 执行器见 [`../executors/overview.md`](../executors/overview.md)。

## 连接服务端

默认指向 Mac2017 Hub：

```text
http://192.168.3.116:7777?desktop=1
```

覆盖：

```bash
export CCC_SERVER=http://192.168.3.116:7777
# 可选：本机 sidecar 开发
export CCC_DESKTOP_LOCAL=1
export CCC_COCKPIT_PORT=7777
```

壳启动时导航到 `CCC_SERVER`（自动加 `desktop=1`），**默认不启本地 Hub sidecar**。

[`src-tauri/tauri.conf.json`](../../src-tauri/tauri.conf.json) 的 `devPath` / CSP 已对齐 LAN Hub。

## 双 pane 多会话（MVP，已实现）

| 能力 | 行为 |
|------|------|
| 启用 | `?desktop=1`、Tauri、或 `localStorage.ccc_dual_pane=1`；标题栏「分屏」按钮 |
| 双 pane | 左右各一可见会话；点击窗格切换焦点 |
| 后台流 | `streamRegistry` 保留；`canPaint` 对**任一可见 pane 的 tab** 放行 |
| 发送/取消 | 针对当前 `activeTabId`（焦点窗格） |
| 并发上限 | Hub `chat_session_max_live`（默认 4） |

实现：[`dualPane.js`](../../scripts/chat_server/frontend/js/dualPane.js) + `canPaint` 放宽。

浏览器临时体验：打开  
`http://192.168.3.116:7777?desktop=1` → 点分屏按钮。

## 构建（M1 客户端机）

```bash
cd /path/to/CCC/src-tauri
export CCC_SERVER=http://192.168.3.116:7777
cargo tauri dev    # 或 cargo tauri build
```

壳只做展示与多会话 UI；**Engine / 中转 / 工作区在 Server**。

## Session 契约

| 字段 / 能力 | 说明 |
|-------------|------|
| `session_id` | tab.sessionId；历史可 resume |
| `project_id` | tab.projectId |
| `stream_handle` | FE `streamRegistry` + 服务端 Claude slot；切 tab/pane 不 abort |
| `status` | streaming via registry；cancel 走 AbortController |
| 双 pane | MVP 已上；更多会话仍在 titlebar 列表 |
| 取消 | 取消焦点 tab 的流 |

### 非目标（本步仍不做）

- 完整 IDE / 本地 Engine  
- 网页默认多 canvas（需 `?desktop=1`）  
- 把 OpenCode 嵌进桌面进程  

### 与执行器关系

- 对话 session → Hub → Claude 兼容 CLI  
- 任务下达后由 Server Engine + OpenCode 跑  
