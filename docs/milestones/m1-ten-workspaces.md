# M1 — 多仓生产就绪（v0.50.0）

> **对内里程碑**：个人用 CCC 日常维护约 **10** 个独立业务仓。  
> 非对外 marketing；验收以本文件 DoD + `ccc-workspace-doctor` 为准。

## 目标

```text
对齐基线 → 下一步/定稿 → 下达 epic → Engine 扇出 work → 写码/审/测/归档
```

在最多约 10 个登记仓上稳定可重复；**不**做无人 invent。

## DoD

| # | 门槛 |
|---|------|
| D1 | `~/.ccc/workspaces.json` 无死路径；登记数 ≤10；均有 `.ccc/board` |
| D2 | 舰队仓 `state`/`board` 无假进度；done epic `ui_hidden` |
| D3 | 每仓有 Agent 入口（`CLAUDE.md` 或明确指向） |
| D4 | `python3 scripts/ccc-workspace-doctor.py` → ERROR=0 |
| D5 | 控制面 `enabled` + invent 硬关；空板闲置不算失败 |
| D6 | CHANGELOG / `docs/releases/v0.50.0.md` / 本手册 / CCC `.ccc/state.md` |

## 接入新仓（runbook）

```bash
python3 ~/program/CCC/scripts/ccc-init.py ~/program/<app> --register
# 编辑 CLAUDE.md / .ccc/profile.md / .ccc/state.md
python3 ~/program/CCC/scripts/ccc-workspace-doctor.py
# Hub：选项目 → 对齐基线 → 定稿 → 下达
```

摘除：`python3 scripts/ccc-workspace-doctor.py unregister <path|name>`  
清死路径：`… prune --apply`

## 初始舰队（2026-07-18）

| Hub 名 | 路径 |
|--------|------|
| CCC | `/Users/apple/program/CCC` |
| xianyu | `/Users/apple/program/xianyu` |
| qb | `/Users/apple/program/projects/qb` |
| cla / clawmed-ccc | `/Users/apple/program/clawmed-ccc` |
| qxo | `/Users/apple/program/qx-observer` |
| qx | `/Users/apple/program/projects/qx` |

还可再接 ~4 个仓至上限 10。

## 故障速查

| 现象 | 排查 |
|------|------|
| Engine 闲置 | 空板？invent 关？→ 正常。有卡？看 registry / control / upstream 熔断 |
| Hub 有项目 Engine 不跑 | `doctor` 是否 `engine=False` → register 或下达 |
| 串仓 commit | 隔离审计；确认 OpenCode `--dir`；查 `~/.ccc/workspaces.json` |
| upstream 熔断 | Engine 日志；查 `AGENT_PLANNER_BASE_URL` |
| doctor ERROR | prune；补 CLAUDE.md；压登记数 ≤10 |

## 相关文档

- [`../workspace-binding.md`](../workspace-binding.md)
- [`../hub-ops-console.md`](../hub-ops-console.md)
- [`../program-housekeeping.md`](../program-housekeeping.md)
- [`../releases/v0.50.0.md`](../releases/v0.50.0.md)
