# CCC 运行控制面（v0.39.2）

> **SSOT**：`~/.ccc/control.json`（模块：`scripts/_ccc_control.py`）  
> CLI：`bash scripts/ccc-autostart-guard.sh {status|disable|ui|enable}`  
> 前端开发：**`bash scripts/ccc-hub-dev.sh`**（不碰 control / launchd / Engine）

---

## 业务状态机

```
disabled ──默认──► 无常驻；install 只 stage
ui       ──显式──► 仅 Hub(:7777)+Board(:7775)；Engine 禁止
enabled  ──显式──► 全开；Engine 仅 launchd:com.ccc.engine
```

| 模式 | Hub/Board launchd | Engine | 适用 |
|------|-------------------|--------|------|
| `disabled` | 否 | 否 | 默认 / 停机 |
| `ui` | 可 | 否 | 只要看板 UI，不要流水线 |
| `enabled` | 可 | 可 | 跑任务闭环 |

**前端日常**：不要 `install --start`，用前台：

```bash
bash scripts/ccc-hub-dev.sh
```

这会设 `CCC_FOREGROUND=1`，不改 `control.json`，Ctrl-C 即停。

---

## 命令

```bash
bash scripts/ccc-autostart-guard.sh status
bash scripts/ccc-autostart-guard.sh disable
bash scripts/ccc-autostart-guard.sh ui [--start]       # 仅 UI 常驻
bash scripts/ccc-autostart-guard.sh enable [--start]  # 全开 + 可选 Engine
```

`install-hub-plist.sh --start` / `install-board-plist.sh --start` 只会把 control 设为 **`ui`**，**不会** enable Engine。

`install-ccc-roles.sh --start` 才会 `enabled` + bootstrap Engine；board 在该脚本里只 stage。

---

## 禁止

1. crontab 里 `python3 ccc-engine.py &`
2. patrol `Popen(ccc-engine.py)`
3. 为「看一下前端」去 `launchctl load` KeepAlive plist
4. 文档/脚本把 `install-*-plist` 写成默认会自动 load

---

## 与版本关系

- v0.37：空看板不自造任务
- v0.39：控制面 + 禁 Popen
- v0.39.1：install 默认只 stage
- **v0.39.2**：`ui` 模式 + `ccc-hub-dev.sh`，前端开发与 Engine 解耦
