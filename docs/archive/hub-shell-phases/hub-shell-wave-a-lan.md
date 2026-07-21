# Wave A — M1 → Mac2017 Hub LAN 可达性（验收）

> **日期**：2026-07-21 · **执行**：Cursor  
> **结论**：✅ **现网已通**（Hub 听 `*:7777` / `CCC_CHAT_HOST=0.0.0.0`）

---

## 复现与对照

| 探针 | 结果 |
|------|------|
| M1 `curl -m 8 -u ccc:ccc http://192.168.3.116:7777/api/desktop/projects` | **HTTP 200** · projects=8 · ~0.2–0.4s |
| M1 `nc` / ping `192.168.3.116` | 通 |
| 2017 `curl 127.0.0.1:7777` | 通 |
| 2017 `lsof :7777` | `TCP *:7777 (LISTEN)` |
| plist | `CCC_CHAT_HOST=0.0.0.0` · `CCC_CHAT_PORT=7777` |

早前 Phase14 手测时出现的 LAN timeout 为**间歇/瞬时**（防火墙或进程重启窗口）；当前配置正确，无需改业务协议。

## 运维备忘（已写入 topology）

Server 本机通、客户端超时 → 查：Python 入站防火墙、Hub 是否仍在 Listen、kickstart `com.ccc.chat-server`。

## Desktop（目视）

| 项 | 结果 |
|----|------|
| Settings / 默认 Hub | `http://192.168.3.116:7777` |
| 开 App → ccc-demo | 项目列表可拉；`hubReachable` 后转任务可用 |
| 右栏 | LAN 通时可跟一笔 epic / Phase14–16 手测不再被 timeout 挡 |

转任务仍依赖 `hubReachable`；断线时 toast「可聊；转任务暂不可用」。
