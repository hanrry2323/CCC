# CCC Startup Brief

> **读完 = 知道 CCC 怎么用。** 其他文件按需 grep。目标：启动 token 可控。  
> **叙事**：[`docs/VISION.md`](docs/VISION.md) · **事实+共识权威**：[`docs/product/loop-engineer-authority.md`](docs/product/loop-engineer-authority.md) · **版本**：`VERSION`（**v0.53.2**）  
> **边界**：[`docs/product/dialogue-orchestration-boundary.md`](docs/product/dialogue-orchestration-boundary.md)  
> **北星**：[`docs/product/hub-shell-roadmap.md`](docs/product/hub-shell-roadmap.md) · **索引**：[`docs/INDEX.md`](docs/INDEX.md)  
> **正式启用**：[`docs/ops/GO-LIVE.md`](docs/ops/GO-LIVE.md)

---

## 1. 一句话

**人定意图 → Hub 下达 → Engine 编排扇出 → 权威仓写码 → 验收纠错 → 回流飞轮；全程只认一个权威仓。**

CCC = **Connect–Claude Code** = **Loop Engineer**  
**对话面（Desktop + loop-code）** 定意图产 epic；**编排面（Engine + Board）** 远端开发；中间只交 transfer / flow。  
**Skill + Prompt = 本次角色**（用户不选角色）。机制：[`docs/product/role-formation.md`](docs/product/role-formation.md)

**v0.51+**：CCC 本体 = **orch**（**Cursor 改**）；Engine **只跑业务 apps**（R-15）。  
**开发通道**：平台改动 = **仅 Cursor（不更换工具 · 完整 IDE 能力）**；Desktop 对话默认 MiniMax。SSOT：[`docs/product/dev-channel.md`](docs/product/dev-channel.md)。  
**人格独立**：**Cursor ≠ Desktop Agent**；Desktop Plan「不写码」只约束桌面对话，不限制 Cursor。见 [`docs/product/loop-engineer-authority.md`](docs/product/loop-engineer-authority.md)。

**共识**：Demo ≠ 上线 ≠ 符合意图（行业共性）；已注册 ≠ 可开工（先全面对齐）；共识必须写入 `loop-engineer-authority.md` 再应用。

**勿再说**：「接很多 IDE」「先选 7 角色」「用 Claude Code / Trae / Zed 改 CCC 平台」。

**4 个数字**：

| | |
|--|--|
| **Desktop + sidecar `:7788`** | 对话 / 意图 / 转任务（M1 主入口） |
| **Hub `:7777`** | API host：transfer / flow / board / ops（Mac2017） |
| **6+1 列看板** | backlog(epic) + planned→…→released(work) + abnormal |
| **阶段能力包** | product / dev / reviewer / tester / ops / kb / regress（默认可插拔 Skill，非角色超市） |
| **2+ plist** | `com.ccc.agent-sidecar` + **`com.ccc.hub-tunnel`**（M1）+ `com.ccc.engine` + Board + Hub（2017） |

热路径假死 / 多端版本：[`docs/product/desktop-agent-sidecar.md`](docs/product/desktop-agent-sidecar.md) · [`docs/deploy/desktop.md`](docs/deploy/desktop.md)。  
**Hub 稳定性（M1）**：默认 SSH 隧道 `:17777`，勿直连 LAN `:7777` → [`docs/product/hub-ssh-tunnel.md`](docs/product/hub-ssh-tunnel.md)。

---

## 2. 人机路径（优先）

```text
Desktop（M1）：对齐基线 → 下一步 → 定稿方案 → 转任务 → 下达
     → POST /api/desktop/transfer → Mac2017 backlog epic
     →（2017 control=enabled）Engine 自动编排：product 扇出 → dev 写码 → review/test → kb → released
     → 右栏 SSE 实时回传编排进度
```

端口与账密：[`docs/ccc-hub-ports.md`](docs/ccc-hub-ports.md)（`ccc` / `ccc`）  
上手：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)  
多项目绑定 / 新项目接入：[`docs/workspace-binding.md`](docs/workspace-binding.md)  
**业务仓迁移 → 注册 → Desktop 开项目对话**：[`docs/runbooks/app-migrate-register-desktop.md`](docs/runbooks/app-migrate-register-desktop.md) · Agent 短交接：[`docs/product/desktop-agent-handoff.md`](docs/product/desktop-agent-handoff.md)  
**五仓舰队迁移（运维，非日常心智）**：[`docs/deploy/fleet-apps-migration-2026-07.md`](docs/deploy/fleet-apps-migration-2026-07.md) · 2017 布局：[`docs/deploy/server-layout.md`](docs/deploy/server-layout.md)

---

## 3. 编排面：阶段能力包（Engine 串行）

> 下表是 **Engine 调度的默认阶段**，不是给终端用户点选的角色列表。

| 阶段 | Engine 触发 | 干 |
|------|-------------|-----|
| product | backlog 中 `pending` epic | Claude 扇出 work×N → planned；**epic 留 backlog**（`split_status=planned`） |
| dev | 只调度 `card_kind=work` | OpenCode 写代码 → testing（强制 `--dir` 目标仓） |
| reviewer | testing 门禁 | 语义审查 → **verdict.md** |
| tester | testing 门禁 | pytest + 验收清单 |
| ops | 调试 / 可选 | 健康检查（不动 board） |
| kb | verified 非空 | tag + CHANGELOG → released |
| regress | 23:30 / 手动 | 回测 → backlog(回归 epic) |

**复杂度**：`small` 仅表规模提示，**不**跳过 reviewer+tester（v0.53+ 假绿修复）。

**大卡五态**（`split_status`，epic 永不离 backlog）：

`pending` → `planned` → `running` → `done`；任子卡 `abnormal` → `failed`（不沉底）。存量 `active`/`blocked` 为别名。

---

## 4. 控制面（v0.51）

`~/.ccc/control.json`：

| 模式 | 含义 |
|------|------|
| `disabled` | 默认。无常驻 Engine |
| `ui` | 仅 Hub+Board |
| `enabled` | Engine **只消费 app 队列**（正式使用保持此项） |
| `invent` | **已退役**（`invent_hard_disabled`）；勿启用 |

```bash
bash scripts/ccc-hub-dev.sh
bash scripts/ccc-autostart-guard.sh enable --start
python3 scripts/ccc-failure-report.py --last 20
python3 scripts/ccc-workspace-doctor.py
```

禁止 crontab 拉 `ccc-loop-monitor`；patrol 禁止旁路 `Popen` 起 Engine。  
空看板默认不 auto_replenish / evolve（`CCC_AUTO_REPLENISH=0`）。

---

## 5. 看板（一行）

```text
backlog(epic 常驻) ──扇出──► planned(work) → in_progress → testing → verified → released
                              └ abnormal ←──（work 失败；父 epic → failed）
```

不可跳列（X4）。Hub 定稿转任务默认建 **epic**；若已种子 plan/phases 的单卡 work 可跳过 product。

---

## 6. 红线（极简）

全文：`references/red-lines.md`

致命：

- **1** 不动系统文件 / 密钥  
- **11** Verdict 必须落文件（口头 PASS 无效）  
- **12** 禁止 agent 自主启用 CCC  
- **R-15** 禁止 CCC 本体经看板自消费（平台改动用 Cursor）  
- **X4** 每 phase 走看板  

---

## 7. 教训（5 条）

| # | 避坑 |
|---|------|
| 27 | `claude -p` 的 prompt 走 stdin |
| 28 | 口头 PASS ≠ 真 PASS |
| 32 | opencode 模型名带 provider 前缀 |
| 33 | 长 prompt 走 `--file` |
| 35 | 默认「执行器写码 + 审查门禁」 |

---

## 8. 模型（执行面）

```bash
opencode run --model loop/flash "<msg>"
```

禁止裸 `flash` / 乱写 provider。Token 治理与分层见 `docs/model-tier-strategy.md`。

---

## 9. 懒加载

```bash
cat docs/VISION.md
cat docs/STRATEGY-MAP.md          # 全景
grep -A 15 "## 红线 11" references/red-lines.md
python3 scripts/ccc-board.py index
```

**黄金规则**：Brief 够了 → 不够再 grep。

---

## 10. 调用链（1 行）

老板在 Desktop（M1）定稿转任务（或「按 CCC 跑 X」）→ task 落 Mac2017 看板 →（2017 control=enabled）Engine 串行阶段能力包（product=Claude Code 扇出 / dev=OpenCode 写码）→ released。

---

**维护**：范式变更时同步 VISION + README + SKILL + STRATEGY-MAP（均链回本文或 VISION）。  
**约束**：禁止在 Engine 外并发依赖模块全局 `ROOT`（F-CON-03）。
