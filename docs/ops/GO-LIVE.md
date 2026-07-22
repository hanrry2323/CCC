# CCC 正式启用卡 — Go Live

> **日期**：2026-07-22 · **状态**：可正式使用（**主入口 = CCC Desktop**）  
> **版本**：以根目录 `VERSION` 为准（当前 **v0.60.0** · LPSN 意图飞轮）  
> Desktop 上线卡：[`GO-LIVE-DESKTOP.md`](./GO-LIVE-DESKTOP.md)  
> LPSN 出门：[`../product/lpsn-ship-gate.md`](../product/lpsn-ship-gate.md)  
> 详细盘点：[`fleet-hygiene-2026-07-18.md`](./fleet-hygiene-2026-07-18.md)（史）

## 开箱即用（每天这样用）

```text
1. 打开 CCC Desktop（Hub 默认本机隧道 http://127.0.0.1:17777，账号 ccc/ccc）
2. 选业务项目（不要选编排仓下达）
3. 对话定稿 → 转任务（验收含可重放意图探针）→ 右栏看编排进度
4. Engine 自动：product → dev → review/test → kb → released（= code_landed）
5. 意图稳定：regress 回放探针 → L1 mark intent_stable（见 LPSN）
6. 需要看板/运维时用侧栏或网页 Hub（运维页看后勤心跳；不定时点日审）
```

Mac2017 后勤定时（可选，减负）：`bash scripts/install-ops-plist.sh install --enable --apply-ammo`；regress 用 [`../deploy/launchd/com.ccc.regress.plist.example`](../deploy/launchd/com.ccc.regress.plist.example)（WorkingDirectory=业务仓）。弹药禁打 CCC orch。

| 入口 | 地址 |
|------|------|
| **CCC Desktop** | `/Applications/CCCDesktop.app` |
| Hub（M1 默认） | http://127.0.0.1:17777（`com.ccc.hub-tunnel`） |
| Hub（2017 / 排障 LAN） | http://192.168.3.116:7777（**非** Desktop 默认） |
| Board API（Server 本机） | http://127.0.0.1:7775 |
| Engine stats（Server 本机） | http://127.0.0.1:7776/api/stats |

## 角色分工（记住就够）

| 你要做的事 | 去哪 |
|------------|------|
| 业务功能 / 项目验收 | Desktop → 对应业务仓 |
| 改 CCC 平台本身 | **Cursor 开 CCC 仓**（R-15；禁止下到 CCC 看板） |
| 看舰队健康 | `python3 scripts/ccc-workspace-doctor.py` 或 Hub 运维 |
| 意图是否完成 | 勿看 VERSION/`released` 数；看探针 + regress + L1 `intent_stable` |

## 就绪检查

| # | 项 | 口径 |
|---|-----|------|
| 1 | `VERSION` | 读根目录 `VERSION`（现 v0.60.0） |
| 2 | 控制面 `enabled` + invent 硬关 | 日常生产 |
| 3 | Engine 只消费业务 apps，跳过 CCC orch | R-15 |
| 4 | Hub 拒投 CCC（400） | OK |
| 5 | M1 Hub 默认隧道 `:17777` | 勿把 LAN 当默认 |
| 6 | LPSN 门禁 | `bash tests/e2e/test_lpsn_flywheel.sh` |

## 常用命令

```bash
python3 ~/program/CCC/scripts/ccc-workspace-doctor.py
bash ~/program/CCC/scripts/ccc-autostart-guard.sh status
python3 ~/program/CCC/scripts/ccc-board.py regress   # LPSN · P 回放
python3 ~/program/CCC/scripts/ccc-authority-patrol.py
```

## 已知不影响启用的项

- 空板 + invent 关 = Engine **闲置正常**
- `released` / VERSION bump ≠ 意图完成（须 LPSN P→S）
- LAN `:7777` 仅排障；Desktop/sidecar 默认隧道

## 第一周建议节奏

1. 选 1 个业务仓跑通「定稿（含探针）→下达→released→regress→intent_stable」
2. 每天开场：Desktop 对齐基线；收工：doctor 一眼
3. 平台想改：只开 CCC + Cursor；改完 kickstart Engine/Hub
