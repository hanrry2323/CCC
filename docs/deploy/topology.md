# CCC 部署拓扑 — 现行（2026-08-06）

> **旧文已作废。** Hub `:7777` / Board `:7775` / M1 sidecar `:7788` / hub-tunnel `:17777` 全部退役。  
> 权威：`docs/INDEX.md` §0 · `CURSOR.md` · `.ccc/infrastructure.md` · `location-truth.mdc`

## 一句话

**M1 = git 写源 + IDE 中枢；Mac2017 = 唯一生产 HTTP `:7788` + Engine + 中继 6100/6102。**  
老板只聊 IDE、只看板/运维/Δ；`CCC_AUTO_PULL` 负责中间同步。

| 角色 | 机器 | 职责 |
|------|------|------|
| 开发副本 | M1 `192.168.3.140` | push `main`；不出生产服务 |
| 生产节点 | 2017 `192.168.3.116` | web / engine / board-scheduler / relay |

Desktop 壳暂缓。历史双机/Hub 正文见 `docs/archive/`。
