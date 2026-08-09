# CCC 部署拓扑 — 现行（2026-08-06）

> **旧文已作废。** Hub `:7777` / Board `:7775` / M1 sidecar `:7788` / hub-tunnel `:17777` 全部退役。  
> 权威：`docs/INDEX.md` §0 · `CURSOR.md` · `.ccc/infrastructure.md` · `location-truth.mdc`

## 一句话

**2017 = 执行写码节点（engine worktree）+ 生产 :7788；M1 = 中枢出卡/验收/合入/看板 + 轻量开发；业务仓（qb 等）本体机器写码。**  
老板只聊 IDE、只看板/运维/Δ；`CCC_AUTO_PULL` 负责中间同步。

| 角色 | 机器 | 职责 |
|------|------|------|
| 中枢 | M1 `192.168.3.140` | 出卡/验收/合入/看板 + 轻量开发；不出生产服务 |
| 生产与执行 | 2017 `192.168.3.116` | 执行写码（engine worktree） + 生产 :7788（web / engine / board-scheduler / relay） |

Desktop 壳暂缓。历史双机/Hub 正文见 `docs/archive/`。
