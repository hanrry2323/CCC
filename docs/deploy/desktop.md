# CCC Desktop 客户端（SwiftUI）

> **主产品入口**。网页 Hub 为运维/兼容。服务端见 [`topology.md`](topology.md)。  
> 架构 SSOT：[`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md)  
> 本机对话热路径：[`../product/desktop-agent-sidecar.md`](../product/desktop-agent-sidecar.md)  
> 降级说明：[`../product/deprecate-web-hub.md`](../product/deprecate-web-hub.md)

## 连接服务端

默认 `CCC_SERVER`：

```text
http://192.168.3.116:7777
```

应用内 Settings 可改；Basic Auth 默认 `ccc` / `ccc`。  
本机 Agent：`ccc.agent` → `http://127.0.0.1:7788`（**禁止**回退 Hub 聊天）。

## 三栏

| 栏 | 作用 |
|----|------|
| 左 | 项目文件夹 + 统一 Thread 列表（`+` 新建会话；发送跟本窗 `threadId`，不强制 `::main`） |
| 中 | 方案 Agent 对话；转任务（仅 epic） |
| 右 | 编排流程（flow events / snapshot）；空板文案「编排空闲 · 下一笔定稿后出现在这里」≠ 对话故障 |

## 模型出口

| 工具 | 上游 |
|------|------|
| Desktop ↔ sidecar ↔ loop-code | **MiniMax** 直连 |
| Engine Claude（product/reviewer） | **MiniMax** 直连 |
| Engine OpenCode（dev） | **讯飞** `xfyun/code` 直连 |

~~ai-loop-router `:4000/:4002` 已退役。~~ 见 [`topology.md`](topology.md)。

## 运行与打包

源码：[`../../desktop/`](../../desktop/)

```bash
cd desktop
swift run CCCDesktop
bash scripts/package-baseline.sh   # → .build/CCCDesktop.app
cp -R .build/CCCDesktop.app /Applications/
```

发版后 **重启已打开的 Desktop**（否则仍跑旧二进制）。  
sidecar 随仓更新后需 `kickstart` 一次才能加载新 Python（见 sidecar 文档「多端版本对齐」）。

### 多端核对清单（对话热路径）

| 端 | 应一致 | 命令摘要 |
|----|--------|----------|
| M1 仓 | `git rev-parse --short HEAD` = 目标 commit | `cd ~/program/CCC && git pull` |
| M1 Desktop | `/Applications/CCCDesktop.app` 已重装 | `package-baseline.sh` + `cp -R` |
| M1 sidecar | `/health` ok；进程读本机仓 | `launchctl kickstart -k gui/$(id -u)/com.ccc.agent-sidecar` |
| Mac2017 仓 | 同 commit | `ssh mac2017 'cd ~/program/CCC && git pull --ff-only'` |
| Mac2017 Hub | transfer / flow / ops | `kickstart -k …/com.ccc.chat-server` |

## 废弃

- **双对话分屏**（旧 Tauri / `dualPane.js`）— 不再作为产品能力
- **嵌网页 Hub SPA** — Desktop 不嵌 SPA
- Tauri WebView 壳 — 非主线

## API

| 路径 | 说明 |
|------|------|
| `GET /api/desktop/projects` | 项目树 |
| `GET/POST /api/desktop/threads` | 统一会话 |
| `POST /api/desktop/transfer` | 聊透门禁 → epic |
| `GET /api/desktop/flow/events` | SSE |
| `GET /api/desktop/flow/snapshot` | 右栏快照 |
| `GET /api/ops/router-usage` | **兼容 stub**（ai-loop-router 退役后恒零）；本机 Agent 用量见 Desktop 顶栏 |


端到端冒烟：`bash scripts/smoke-desktop-e2e.sh`
