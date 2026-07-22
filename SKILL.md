---
name: ccc-protocol
description: "CCC — Connect–Claude Code. Loop Engineer: Hub 定意图 + Engine 自动编排自主执行。Trigger: '按 CCC 流程跑 X', 'ccc 跑一下 X', '定稿转任务', '用看板跑 X'"
---

# CCC — Connect–Claude Code

> **Loop Engineer。** 人定意图，系统自动编排与自主执行。  
> **Hub** 是入口（已替代第三方 Agent IDE 壳）。任务路由工具；**Skill + Prompt = 本次角色**（无穷角色）。  
> 叙事 SSOT：`docs/VISION.md` · 启动：`STARTUP-BRIEF.md` · 版本：`VERSION`（**v0.53.1**）

**含义**：**C**onnect–**C**laude **C**ode。

---

## 启动（懒加载）

```bash
cat STARTUP-BRIEF.md          # 必读
cat docs/VISION.md            # 定位（对外口径）
grep -A 15 "## 红线 11" references/red-lines.md
# 业务仓迁移 / Desktop 开项目对话（Agent 交接）
# docs/product/desktop-agent-handoff.md
# docs/runbooks/app-migrate-register-desktop.md
```

---

## 人机优先路径（Hub）

```text
对齐基线 → 下一步 → 定稿方案 → 转任务 → 下达并开工
→（控制面 enable）Engine Loop 自动开发/验收/归档
```

小改动（单文件 1–5 行 / 查信息）→ **直接处理，不强制走看板**（红线 12：不擅自启用 CCC）。

用户显式触发示例：「按 CCC 流程跑 X」/「用看板跑 X」/ Hub 上点转任务。

---

## 编排：阶段能力包（不是角色超市）

Engine 串行调度下列 **默认 Skill 包**——用户**不**需要选择：

| 阶段 | Skill | 看板 |
|------|-------|------|
| product | `skills/ccc-product` | pending epic → 扇出 work×N 入 planned；**epic 留 backlog** |
| dev | `skills/ccc-dev` | work: planned → in_progress → testing |
| reviewer | `skills/ccc-reviewer` | testing → verified |
| tester | `skills/ccc-tester` | testing → verified |
| ops | `skills/ccc-ops` | 不动 board |
| kb | `skills/ccc-kb` | verified → released |
| regress | `skills/ccc-regress` | released → backlog(epic) |

**无穷角色**：任意任务 = 工具路由 + 额外 Skill/Prompt 偏好（Hub 转任务卡可挂软偏好）。

```text
backlog(epic 常驻) ──扇出──► planned(work) → in_progress → testing → verified → released
epic.split_status: pending → planned → running → done（任 abnormal → failed）
```

---

## 红线（摘要）

| # | 一句话 |
|---|--------|
| 1 | 不动系统文件 / 密钥 |
| 3 | 不超出 plan/scope |
| 6 | 同任务内阶段职责不互串（拆解包不写业务代码等） |
| 11 | Verdict 必须有文件 |
| 12 | 禁止 agent 自主启用 CCC |

全文：`references/red-lines.md`

---

## 关键资产

| 路径 | 说明 |
|------|------|
| `docs/VISION.md` | 产品叙事 SSOT |
| `STARTUP-BRIEF.md` | 启动 SSOT |
| `scripts/chat_server/` | Hub |
| `scripts/ccc-engine.py` | Loop 主循环 |
| `skills/ccc-*/` | 阶段能力包 |
| `references/red-lines.md` | 红线 |

当前版本见 `VERSION`。历史见 `CHANGELOG.md`。
