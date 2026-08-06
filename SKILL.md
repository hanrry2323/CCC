---
name: ccc-protocol
description: "CCC — Connect–Claude Code. Loop Engineer: 任意设备壳经 HTTP 直连 2017 单端服务；对话口接大脑 Agent；薄驱动 Engine + 文档流转 + 看板/HTTP 远端开发。Trigger: '按 CCC 流程跑 X', 'ccc 跑一下 X', '定稿转任务', '用看板跑 X', '验收看板'"
---

# CCC — Connect–Claude Code

> **Loop Engineer。** 人定意图，系统自动编排与自主执行。  
> **任意设备壳**经 HTTP 直连 **2017 单端 :7788**；对话口接**大脑 Agent**；编排面（**薄驱动 Engine + 文档流转 + 看板/HTTP**）。  
> 权威链：`docs/INDEX.md` §0 · **文档规范**：`docs/DOC-PROTOCOL.md` · **项目注册**：`docs/projects/registry.yaml` · 启动：`STARTUP-BRIEF.md` · Cursor：`CURSOR.md` · 版本：`VERSION`（**v0.70.0**）  
> **注意**：`docs/VISION.md` 仍含 Hub 时期段落（标待核），**勿当现行架构**。  
> **硬**：读写项目文档必须按 DOC-PROTOCOL；禁止落点外新建、禁止双写 registry。

**含义**：**C**onnect–**C**laude **C**ode。

---

## 启动（懒加载）

```bash
cat CURSOR.md                 # Cursor 角色（若在 Cursor）
cat STARTUP-BRIEF.md          # 必读
cat docs/INDEX.md             # §0 权威链
cat docs/DOC-PROTOCOL.md      # 文档落点 / 项目注册（读写必遵）
cat docs/projects/registry.yaml
cat docs/product/accept-board-sop.md   # 「验收看板」终验
cat docs/architecture.md      # 架构概览
grep -A 15 "## 红线 11" references/red-lines.md
```

---

## 人机优先路径（两层验收 · 2026-08-06）

```text
任意设备壳 / M1 IDE → 出卡（执行体 OpenCode · 验收 Claude Code）
  → push → 2017 自动 pull → Engine 派发 OpenCode → worktree
  → 机械门禁（新 commit + 非空 diff）→ 已回写
  → Engine 拉 Claude 机审 → ## 机审区 通过
  → 老板说「验收看板」→ M1 终验 → ## 验收区 + 已关闭 → 合入
```

小改动（单文件 1–5 行 / 查信息）→ **直接处理，不强制走看板**（红线 12：不擅自启用 CCC）。

用户显式触发：「按 CCC 流程跑 X」/「用看板跑 X」/「验收看板」/ 设备壳上点转任务。

---

## 席位与执行体（2026-08-06 · 两层验收）

| 席位 | 绑定 |
|------|------|
| 日常开发 | **OpenCode**（2017 默认，6102）→ 已回写；不写机审/验收区 |
| 点名开发 | **Claude Code**（6100）→ 则 OpenCode 机审/终验 |
| 2017 机审 | 卡头「验收」方（默认 Claude）写 `## 机审区`（回写后自动） |
| M1 终验 | 听「验收看板」；Claude↔OpenCode 交叉；写 `## 验收区`+已关闭 |
| 难度突击 | **Cursor**（写码；**不验收、不响应验收看板**） |
| 管理 | **Codex**（出卡/裁决；**不验收**） |
| M1 IDE | 开发中枢 + 「验收看板」终验入口 |
| Trae | 停用 |
| HTTP 看板/运维 | 人机实时面 |
| Desktop | 暂缓 |

用户**不**需要选 Codex/Cursor 做验收。终验 SOP：`docs/product/accept-board-sop.md`。

**状态机**（五态不变；可终验 = 已回写 + 机审通过）：

```text
待分派 → 执行中 → 已回写 →（机审区）→ 已关闭
              ↓        ↑
            打回 → 待分派（再派开发）
```

非法转移抛 `IllegalTransitionError`。

---

## 红线（摘要）

| # | 一句话 |
|---|--------|
| 1 | 不动系统文件 / 密钥 |
| 3 | 不超出任务卡范围 |
| 6 | 机械门禁 + 机审 + M1「验收看板」；Codex/Cursor 不验收 |
| 11 | Verdict 必须有文件 |
| 12 | 禁止 agent 自主启用 CCC |
| R-15 | 禁止 CCC 本体经看板自消费 |

全文：`references/red-lines.md`

**已退役勿提**：Hub :7777 · Board :7775 · sidecar · scripts/ccc-engine · 6+1 列 ·「OpenCode 已禁用」误判 ·「M1 交叉=唯一验收」。

---

## 关键资产

| 路径 | 说明 |
|------|------|
| `CURSOR.md` | Cursor 入口与现况 |
| `CLAUDE.md` | 开仓作战卡片 / 双模式 |
| `STARTUP-BRIEF.md` | 启动 SSOT |
| `docs/INDEX.md` | 文档索引 §0 |
| `docs/architecture.md` | 架构概览（新栈 `server/`） |
| `docs/product/dev-channel.md` | 席位谁干什么 |
| `docs/product/accept-board-sop.md` | M1「验收看板」终验 |
| `server/engine/` · `server/board/` · `server/web/` | 新栈核心 |
| `docs/dispatch/` | ★ 任务卡唯一事实源 |
| `references/red-lines.md` | 红线 |

当前版本见 `VERSION`。历史见 `CHANGELOG.md`。
