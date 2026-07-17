# CCC Startup Brief

> **读完 = 知道 CCC 怎么用。** 其他文件按需 grep。目标：启动 token 可控。  
> **叙事 SSOT**：[`docs/VISION.md`](docs/VISION.md) · **权威版本**：根目录 `VERSION`（当前应对齐 v0.42.x）

---

## 1. 一句话

CCC = **Connect–Claude Code** = **Loop Engineer**  
**Hub（入口）** + **Engine 串行编排** + **看板闭环** + **任务路由工具**（Claude / OpenCode…）  
**Skill + Prompt = 本次角色**（无穷角色；用户不选角色、不背 Skill）

**勿再说**：「接很多 IDE 当卖点」「用户先选 7 个角色」。

**4 个数字**：

| | |
|--|--|
| **Hub** | 对话 / 看板 / 控制台 · `:7777` |
| **6+1 列看板** | backlog(epic) + planned→…→released(work) + abnormal |
| **阶段能力包** | product / dev / reviewer / tester / ops / kb / regress（默认可插拔 Skill，非角色超市） |
| **2+ plist** | `com.ccc.engine` + Board + Hub（按需） |

---

## 2. 人机路径（优先）

```text
Hub：对齐基线 → 下一步 → 定稿方案 → 转任务 → 下达并开工
     →（enable）Engine 自动编排开发/验收/归档
```

端口与账密：[`docs/ccc-hub-ports.md`](docs/ccc-hub-ports.md)（`ccc` / `ccc`）  
上手：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)  
多项目绑定 / 新项目接入：[`docs/workspace-binding.md`](docs/workspace-binding.md)

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

**复杂度**：`small` 可跳过 reviewer+tester（v0.28.1）。

**大卡五态**（`split_status`，epic 永不离 backlog）：

`pending` → `planned` → `running` → `done`；任子卡 `abnormal` → `failed`（不沉底）。存量 `active`/`blocked` 为别名。

---

## 4. 控制面（v0.40+）

`~/.ccc/control.json`：

| 模式 | 含义 |
|------|------|
| `disabled` | 默认。无常驻 Engine |
| `ui` | 仅 Hub+Board |
| `enabled` | Engine **只消费队列** |
| `invent` | 允许自造 evolve/audit 等（显式） |

```bash
bash scripts/ccc-hub-dev.sh
bash scripts/ccc-autostart-guard.sh enable --start
bash scripts/ccc-autostart-guard.sh invent --start
python3 scripts/ccc-failure-report.py --last 20
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
grep -A 15 "## 红线 N" references/red-lines.md
python3 scripts/ccc-board.py index
```

**黄金规则**：Brief 够了 → 不够再 grep。

---

## 10. 调用链（1 行）

老板在 Hub 定稿转任务（或「按 CCC 跑 X」）→ task 落看板 →（enable）Engine 串行阶段能力包 → released。

---

**维护**：范式变更时同步 VISION + README + SKILL + STRATEGY-MAP（均链回本文或 VISION）。  
**约束**：禁止在 Engine 外并发依赖模块全局 `ROOT`（F-CON-03）。
