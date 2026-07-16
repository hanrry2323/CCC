# CCC 运行控制面（v0.41）

> **SSOT**：`~/.ccc/control.json`（[`scripts/_ccc_control.py`](../scripts/_ccc_control.py)）  
> CLI：`bash scripts/ccc-autostart-guard.sh {status|disable|ui|enable|invent}`  
> 前端开发：`bash scripts/ccc-hub-dev.sh`（不碰 control / launchd）  
> 失败查询：见 [`observability.md`](observability.md)

**v0.41 产品规则**：Hub/Board **下达任务成功** → 强制 `enabled`（若非 invent）+ 写 `~/.ccc/engine.wake` + 尝试 launchd 拉起 Engine。**无确认弹窗。** 不打开 invent。

---

## 业务状态机

```
disabled ──默认──► 无常驻
ui       ──显式──► 仅 Hub+Board；无 Engine
enabled  ──显式──► Engine 只消费已有队列（禁止 invent）
invent   ──显式──► Engine + audit/evolve/auto_replenish/abnormal 回灌
```

| 模式 | Hub/Board | Engine | 自造任务 |
|------|-----------|--------|----------|
| `disabled` | 否 | 否 | 否 |
| `ui` | 可 | 否 | 否 |
| `enabled` | 可 | 可 | **否**（队列消费者） |
| `invent` | 可 | 可 | **是** |

**根因纠正**：`enable ≠ 永远在线自造任务`。空队列时 Engine **深睡 60s**，不跑 audit/abnormal。

Workspace 发现默认 **仅 CCC 自身**；全扫需 `CCC_DISCOVER_ALL=1` 或 `~/.ccc/workspaces.json` / `CCC_WORKSPACES`。

---

## 命令

```bash
bash scripts/ccc-autostart-guard.sh status
bash scripts/ccc-autostart-guard.sh disable
bash scripts/ccc-autostart-guard.sh ui [--start]
bash scripts/ccc-autostart-guard.sh enable [--start]   # 推荐日常自动化
bash scripts/ccc-autostart-guard.sh invent [--start]   # 显式允许自造（危险）
bash scripts/ccc-hub-dev.sh                           # 前端前台
python3 scripts/ccc-failure-report.py --last 20
```

---

## 禁止

1. crontab 里 `python3 ccc-engine.py &`
2. patrol `Popen(ccc-engine.py)`
3. 为看前端去 `launchctl load` KeepAlive
4. 把 `invent` 当成默认 enable

---

## 流水线环境变量（v0.40.1+）

| 变量 | 默认 | 作用 |
|------|------|------|
| `CCC_CLAUDE_BIN` | 自动解析 | claude 绝对路径（launchd PATH 不全时必设） |
| `CCC_UPSTREAM_STRICT` | off | `1` 时 upstream 探针仅 HTTP 200 算健康 |
| `CCC_REVIEWER_FALLBACK` | `static` | `static`=LLM 挂时 PASS+WARN 过门；`quarantine`=进 abnormal |
| `CCC_DAILY_REVIEW_LLM` | off | `1` 时日审走 Claude JSON（失败回退启发式） |

## 闭环步骤（角色名 = 给人看；自动化 = prompt+skill+harness）

```
对齐基线 → 下达 backlog → wake Engine
  → product(Claude) → planned
  → dev(OpenCode) → testing
  → pytest 硬门 → reviewer(Claude) → verified
  → kb 程序发布 → released
  → daily-diff-review（A–J）→ 必要时再 backlog+wake
```

日审：`python3 scripts/ccc-daily-diff-review.py --workspace <ws> [--apply]`

---

## 版本关系

- v0.37：空看板 invent 默认 OFF
- v0.39：启停控制面
- **v0.40**：`enabled`=队列消费者；`invent` 独立；失败账本
- **v0.40.1**：claude PATH / upstream 4xx / reviewer static fallback / hang 降噪
- **v0.41**：下任务强制开工；基线对齐；日审骨架；Hub SSE 去重
