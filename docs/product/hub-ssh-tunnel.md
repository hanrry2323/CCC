# Hub SSH 隧道（M1 稳定性主路径）

> **状态**：现行 · 2026-07-22  
> **共识入口**：[`loop-engineer-authority.md`](loop-engineer-authority.md) · 连接契约：[`desktop-connection.md`](desktop-connection.md)  
> **拓扑**：[`../deploy/topology.md`](../deploy/topology.md)

## 一句话

**Mac2017 上 Hub 仍听 `0.0.0.0:7777`；M1 客户端默认不直连 LAN，而走本机 SSH 本地转发 `127.0.0.1:17777` → 2017 `127.0.0.1:7777`。**

这不是「Hub 搬到 M1」，也不是改 transfer/flow 契约；只换 **M1→Hub 的传输层**，解决 LAN 对 `:7777` 偶发/整段 HTTP 卡死。

## 为什么改

| 观察（2026-07-22） | 含义 |
|--------------------|------|
| 2017 本机 `curl 127.0.0.1:7777` 稳定 200 | Hub 进程正常 |
| M1 `curl 192.168.3.116:7777` 可 TCP 通，HTTP 曾 **0/30** 超时 | 链路/中间态问题（见过 ESTABLISHED + Send-Q 积压） |
| M1 `ssh -L 17777:127.0.0.1:7777 mac2017` 后 `curl 127.0.0.1:17777` **30/30** | SSH 控制通道可靠，宜作 Desktop/sidecar 主路径 |

**禁止**再把「直连 LAN `:7777`」写成 M1 默认或排障第一招。

## 组件

| 组件 | 落点 |
|------|------|
| launchd | M1 `com.ccc.hub-tunnel`（KeepAlive） |
| 包装脚本 | `~/.ccc/bin/ccc-hub-tunnel.sh` |
| 安装 | `bash scripts/install-hub-tunnel-plist.sh --start` |
| 状态 / 烟测 | `… --status` · `… --smoke` |
| Desktop | `ccc.server` 默认 `http://127.0.0.1:17777`；若仍写 LAN 且隧道通 → 启动自动迁移 |
| sidecar | `CCC_HUB_URL` 默认同上；`install-agent-sidecar-plist.sh --start` 会顺带确保隧道 |
| CLI | `ccc-hub-lens.py` / `ccc-mind-update.py` 默认同隧道 URL |

## 谁仍直连 7777

| 角色 | 地址 |
|------|------|
| Mac2017 本机 Hub / Engine / Board 反代 | `127.0.0.1:7777` |
| 同机 curl / 2017 上跑的烟测 | `127.0.0.1:7777` 或本机环境变量 |
| M1 Desktop / sidecar / 透镜 / 心智 / outbox flush | **`http://127.0.0.1:17777`** |

## 排障

```bash
bash scripts/install-hub-tunnel-plist.sh --status
bash scripts/install-hub-tunnel-plist.sh --smoke
# 日志
tail -50 ~/Library/Logs/CCC/hub-tunnel.err
# 强制重建
bash scripts/install-hub-tunnel-plist.sh --stop
bash scripts/install-hub-tunnel-plist.sh --start
```

SSH Host 默认 `mac2017`（`~/.ssh/config`）。换线：`CCC_HUB_SSH_HOST=tb-mac2017 bash scripts/install-hub-tunnel-plist.sh --start`。

隧道挂了时：对话仍可走 sidecar；转任务进 outbox；恢复后自动 flush（既有 F1 SLA）。先修隧道，勿先改业务仓。
