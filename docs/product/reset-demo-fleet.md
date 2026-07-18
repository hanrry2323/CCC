# 产品重置 — demo-only 舰队

> 从「自用多仓舰队」切到「可分发通用产品」默认态。  
> 日期：2026-07-18

---

## 目标默认态

| 登记 | role | path（Server） |
|------|------|----------------|
| CCC | orch | `/Users/fan/program/CCC` |
| ccc-demo | app（engine） | `/Users/fan/program/apps/ccc-demo` |

- 无 clawmed / qxo / xianyu / qb / hp / Medio-0 等预装登记  
- Hub 默认项目 → `ccc-demo`（或未设置 sticky）  
- 业务仓由用户后期 `register`，不写死进产品代码  

---

## 代码硬编码清理清单（P2）

扫描并去掉产品默认路径/展示名依赖（示例，执行时以 grep 为准）：

| 区域 | 问题 |
|------|------|
| `scripts/chat_server/routers/projects.py` | `clawmed-ccc` 等展示别名 |
| `scripts/board/roles/ops.py` | 写死 `qx-observer` 路径 |
| `scripts/ccc-patrol-v4.py` / `ccc-loop-monitor.sh` | 写死多仓 map |
| `scripts/tests/*` | `/Users/apple/program/xianyu` 等绝对路径 → fixture |
| 文档叙事 | 「十仓舰队」作默认 → 改为「如何注册」示例 |

工具：`python3 scripts/ccc-workspace-doctor.py unregister|register|prune|doctor`

---

## 运行时（Server `~/.ccc`）

1. 备份 `~/.ccc/workspaces.json`  
2. unregister 非 orch/非 ccc-demo 项  
3. 确保 ccc-demo 已 register 且 `engine_eligible=true`  
4. 重置 `~/.ccc/hub-prefs.json`（去掉自用 sticky）  
5. `doctor` 无 ERROR  

---

## 不做

- 删除用户业务仓库磁盘（仅摘注册）  
- 把 M1 舰队配置「整包搬」进 2017 当产品默认  
