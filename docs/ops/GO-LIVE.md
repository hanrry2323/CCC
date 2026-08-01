# CCC 正式启用卡 — Go Live

> **日期**：2026-07-29 · **状态**：可正式使用（**主入口 = CCC Desktop**）  
> **版本**：以根目录 `VERSION` 为准（当前 **v0.65.0** · 意图链自动投 + 编排自愈）  
> Desktop 上线卡：[`GO-LIVE-DESKTOP.md`](./GO-LIVE-DESKTOP.md)  
> LPSN 出门：[`../product/lpsn-ship-gate.md`](../product/lpsn-ship-gate.md)  
> 本版发布：[`../releases/v0.65.0.md`](../releases/v0.65.0.md)  
> 详细盘点：[`fleet-hygiene-2026-07-18.md`](./fleet-hygiene-2026-07-18.md)（史）

## 开箱即用（每天这样用）

```text
1. 打开 CCC Desktop（Hub 默认本机隧道 http://127.0.0.1:17777，账号 ccc/ccc）
2. 选业务项目（不要选编排仓下达）
3. 战略讨论 → Agent 自动投意图链（验收含可重放意图探针；勿等人点「转意图卡」）→ gate 绿自动进代办 → 右栏意图卡链 + 看板计数
4. Engine 自动：product → dev → review/test → kb → released（= code_landed）
5. 意图稳定：regress 回放探针 → L1 mark intent_stable（见 LPSN）
6. 需要看板/运维时用 Desktop 侧栏（网页 Hub `#/board` `#/ops` 可用，2026-07-31 已恢复；`#/console` 应急）
```

Mac2017 后勤定时（可选，减负）：`bash scripts/install-ops-plist.sh install --enable --apply-ammo`；regress 用 [`../deploy/launchd/com.ccc.regress.plist.example`](../deploy/launchd/com.ccc.regress.plist.example)（WorkingDirectory=业务仓）。弹药禁打 CCC orch。

| 入口 | 地址 |
|------|------|
| **CCC Desktop** | `/Applications/CCCDesktop.app` |
| Hub（M1 默认） | http://127.0.0.1:17777（`com.ccc.hub-tunnel`） |
| Hub（2017 / 排障 LAN） | http://192.168.3.116:7777（**非** Desktop 默认） |
| Board API（Server 本机） | http://127.0.0.1:7775 |
| Engine stats（Server 本机） | http://127.0.0.1:7776/api/stats |

## Hub 鉴权两态（`CCC_AUTH_REQUIRE_BEARER`）

Hub 默认账密 `ccc`/`ccc`（Basic），过渡期按 **operator 全权**兼容。可设环境变量切换为仅 Bearer：

| 态 | 设置 | Basic 行为 | 适用 |
|----|------|-----------|------|
| **兼容（默认）** | 不设 / `0` | operator/viewer 全权放行（迁移 debug 日志） | 现状；Desktop/sidecar/工具链零破坏 |
| **REQUIRED** | `CCC_AUTH_REQUIRE_BEARER=1` | 普通端点 **401**；仅 `POST /api/auth/token` 仍接受 Basic 换 token | 强制走会话 token |

- 会话 token：`POST /api/auth/token`（Basic 凭证一次）→ Bearer，TTL 1h，重启失效。
- **回滚**：取消该 env 即回到兼容态，不停服务。

### 已迁移调用方（scripts 侧统一走 `_hub_auth` / `ccc-hub-token.sh`，2026-08-01 窗口 G）

| 类 | 调用方 | 机制 |
|----|--------|------|
| 工具 | `ccc-hub-lens.py` · `ccc-mind-update.py` · `ccc-submit-proposal.py` · `verify-ccc-hub.py` · `ccc-stress-matrix.py` | `_hub_auth.hub_headers()`（Bearer 优先，换发失败回退 Basic） |
| Hub 服务 | `chat_server/services/hub_agent_tools.py` · `transfer_outbox_flush.py` | `_hub_auth` 薄壳 + 401 重取 |
| 对话链 | `ccc-agent-sidecar.py`（`_hub_auth_headers` → `_hub_auth`；`_hub_proxy_sync` 401 自愈） | Desktop→sidecar→Hub 全程 Bearer |
| Shell | `ccc-hub-probe.sh` · `smoke-hub-empty-transfer-retry.sh` · `smoke-desktop-stable.sh` | `ccc-hub-token.sh` 换 Bearer，空 token 回退 `-u` |

- 其余 `-u` env 驱动 demo/ops 脚本（`smoke-ccc-demo-*`、`smoke-qb-biz-small.sh` 等）与 `ccc-fleet.sh` 为**已知残留**：非硬编码（env 派生），开关 on 前需同样迁移；`smoke-hub-outage-outbox.sh` 内 ssh 远程恢复探针为远程 Hub 自身鉴权校验（保留 `-u ccc:ccc`）。
- `_ccc_control.py` 无任何 Hub HTTP 请求（no-op，无需迁移）。

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
| 1 | `VERSION` | 读根目录 `VERSION`（现 v0.62.0） |
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
