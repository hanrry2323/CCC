# CCC 部署拓扑 — 现行（2026-08-06）

> **旧文已作废。** Hub `:7777` / Board `:7775` / M1 sidecar `:7788` / hub-tunnel `:17777` 全部退役。  
> 权威：`docs/INDEX.md` §0 · `.ccc/infrastructure.md` · `location-truth.mdc`（CURSOR.md 已随 Cursor 弃用移除）

## 一句话

**2017 = 执行写码节点（engine worktree）+ 生产 :7788；M1 = 中枢出卡/验收/合入/看板 + 轻量开发；业务仓（qb 等）本体机器写码。**  
老板只聊 IDE、只看板/运维/Δ；`CCC_AUTO_PULL` 负责中间同步。

| 角色 | 机器 | 职责 |
|------|------|------|
| 中枢 | M1 `192.168.3.140` | 出卡/验收/合入/看板 + 轻量开发；不出生产服务 |
| 生产与执行 | 2017 `192.168.3.116` | 执行写码（engine worktree） + 生产 :7788（web / engine / board-scheduler；watchdog 巡检。中转站 2026-08-24 退役拆除，执行体直连各自 CLI） |

Desktop 壳暂缓。历史双机/Hub 正文见 `docs/archive/`。

## 写鉴权与 plist 变更口径（2026-08-24 直修沉淀）

- **写鉴权**：读端点局域网直连；变更类请求（非 GET/HEAD/OPTIONS）强制 Bearer token（`POST /session` 账号 `ccc` 换取）。口令运行面 `~/.ccc/web-auth.txt`（600，不入 git）；`CCC_WEB_WRITE_AUTH=1` 默认开。豁免清单：无（原 /wall 前置豁免已拆除）。
- **plist 变更操作口径**：改动 `~/Library/LaunchAgents/com.ccc.*.plist` 内容后必须 `launchctl bootout` + `bootstrap` 重载——`kickstart -k` 只重启进程、**不重读 manifest/env**（本次实踩：新进程仍带旧 env）。
