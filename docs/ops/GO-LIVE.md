# CCC 正式启用卡 — Go Live（v0.51.0）

> **日期**：2026-07-19 · **状态**：可正式使用（**主入口 = CCC Desktop**）  
> Desktop LAN 上线卡：[`GO-LIVE-DESKTOP.md`](./GO-LIVE-DESKTOP.md)  
> 详细盘点：[`fleet-hygiene-2026-07-18.md`](./fleet-hygiene-2026-07-18.md)

## 开箱即用（每天这样用）

```text
1. 打开 CCC Desktop（Server = http://192.168.3.116:7777，账号 ccc/ccc）
2. 选业务项目（不要选编排仓下达）
3. 对话定稿 → 转任务 → 右栏看编排进度
4. Engine 自动：product → dev → review/test → kb
5. 需要看板/运维时用侧栏（浏览器）或网页 Hub
```

| 入口 | 地址 |
|------|------|
| **CCC Desktop** | `/Applications/CCCDesktop.app` |
| Hub（运维/兼容） | http://192.168.3.116:7777 |
| Board API（Server 本机） | http://127.0.0.1:7775 |
| Engine stats（Server 本机） | http://127.0.0.1:7776/api/stats |

## 角色分工（记住就够）

| 你要做的事 | 去哪 |
|------------|------|
| 业务功能 / 项目验收 | Hub → 对应业务仓 |
| 改 CCC 平台本身 | **Cursor 开 CCC 仓**（R-15；禁止下到 CCC 看板） |
| 看舰队健康 | `python3 scripts/ccc-workspace-doctor.py` 或 Hub 运维 |

## 就绪检查（本机已 PASS）

| # | 项 | 状态 |
|---|-----|------|
| 1 | `VERSION` = v0.51.0 | OK |
| 2 | 控制面 `enabled` + invent 硬关 | OK |
| 3 | Engine 消费 **7 apps**，跳过 CCC orch | OK |
| 4 | Hub 拒投 CCC（400） | OK |
| 5 | doctor `errors=0`（`qx` WARN=零件库，预期） | OK |
| 6 | launchd：engine + board + chat-server | OK |

## 舰队（Engine 消费）

`xianyu` · `qb` · `clawmed-ccc` · `ai-loop-router` · `hp` · `Medio-0` · `qxo`  
**不消费**：CCC（orch）· `qx`（未登记零件库）

## 常用命令

```bash
# 舰队医生
python3 ~/program/CCC/scripts/ccc-workspace-doctor.py

# 控制面（保持 enabled 即可；勿 invent）
bash ~/program/CCC/scripts/ccc-autostart-guard.sh status

# 重启（改了 Hub/Engine 代码后）
launchctl kickstart -k gui/$(id -u)/com.ccc.engine
launchctl kickstart -k gui/$(id -u)/com.ccc.chat-server

# 新业务仓接入
python3 ~/program/CCC/scripts/ccc-init.py ~/program/<app> --register
python3 ~/program/CCC/scripts/ccc-workspace-doctor.py
```

默认业务项目：可用环境变量 `CCC_HUB_DEFAULT_PROJECT=clawmed-ccc`（写入 chat-server plist）或浏览器记住上次选择。

## 已知不影响启用的项

- Hub 仍能「看见」`qx`，但 `engine_eligible=false`，不能下达
- `clawmed-ccc` 本地仓无 `origin` remote（不影响 Engine；若要备份自加 remote）
- 空板 + invent 关 = Engine **闲置正常**，不是坏了

## 第一周建议节奏

1. 选 1 个业务仓（建议先 `clawmed-ccc` 或你最熟的）跑通「定稿→下达→released」
2. 每天开场：Hub 对齐基线；收工：doctor 一眼
3. 平台想改：只开 CCC + Cursor；改完 kickstart Engine/Hub
