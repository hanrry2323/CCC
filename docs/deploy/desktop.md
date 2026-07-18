# CCC Desktop 客户端（Tauri）

> 产品主 UI 面。网页 Hub 为过渡。服务端见 [`topology.md`](topology.md)。  
> 执行器见 [`../executors/overview.md`](../executors/overview.md)。

## 连接服务端

默认指向 Mac2017 Hub：

```text
http://192.168.3.116:7777
```

覆盖：

```bash
export CCC_SERVER=http://192.168.3.116:7777
```

[`src-tauri/tauri.conf.json`](../../src-tauri/tauri.conf.json) 的 `devPath` / CSP `connect-src` 已对齐该地址。

## 构建（M1 客户端机）

```bash
cd /path/to/CCC
# 需 Rust + Tauri CLI
cargo tauri build
```

壳只做展示与多会话 UI；**Engine / 中转 / 工作区在 Server**。

## Session 契约（第三步实现；本步只定约）

桌面多会话的目标模型（对齐 Cursor/Codex，**不在网页 Hub 做多路大修**）：

| 字段 / 能力 | 说明 |
|-------------|------|
| `session_id` | 稳定 ID；跨窗口/冷启动可 resume |
| `project_id` | 绑定 registry 中的 app（如 `ccc-demo`），非 orch |
| `stream_handle` | 服务端流可 detach；UI 离开不杀生成 |
| `status` | `idle` / `streaming` / `error` / `cancelled` |
| 双 pane | MVP：同时可见 ≤2 个 session；更多进侧栏列表 |
| 取消 | 客户端发 cancel → 服务端停该 session 的 live slot |

### 非目标（第三步仍不做）

- 完整 IDE / 本地 Engine  
- 网页多 canvas 并发 paint  
- 把 OpenCode 嵌进桌面进程  

### 与执行器关系

- 对话 session → Hub → Claude 兼容 CLI（可切 loop-code）  
- 任务下达后由 Server Engine + OpenCode 跑；桌面只订阅看板/状态  

## 多会话（方向摘要）

Session 一等公民、后台流不随 tab 卸载、双 pane 起步——在桌面壳迭代。
