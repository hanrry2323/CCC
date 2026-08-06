---
name: ccc-protocol
description: "CCC — Connect–Claude Code. Loop Engineer: 任意设备壳经 HTTP 直连 2017 单端服务；对话口接大脑 Agent；薄驱动 Engine + 文档流转 + 看板/HTTP 远端开发。Trigger: '按 CCC 流程跑 X', 'ccc 跑一下 X', '定稿转任务', '用看板跑 X'"
---

# CCC — Connect–Claude Code

> **Loop Engineer。** 人定意图，系统自动编排与自主执行。  
> **任意设备壳**经 HTTP 直连 **2017 单端 :7788**；对话口接**大脑 Agent**（Claude Code CLI via 6100）；编排面（**薄驱动 Engine + 文档流转 + 看板/HTTP**）。  
> 权威链：`docs/INDEX.md` §0 · 启动：`STARTUP-BRIEF.md` · Cursor：`CURSOR.md` · 版本：`VERSION`（**v0.70.0**）  
> **注意**：`docs/VISION.md` 仍含 Hub 时期段落（标待核），**勿当现行架构**。

**含义**：**C**onnect–**C**laude **C**ode。

---

## 启动（懒加载）

```bash
cat CURSOR.md                 # Cursor 角色（若在 Cursor）
cat STARTUP-BRIEF.md          # 必读
cat docs/INDEX.md             # §0 权威链
cat docs/architecture.md      # 架构概览
grep -A 15 "## 红线 11" references/red-lines.md
```

---

## 人机优先路径（HTTP 直连 2017）

```text
任意设备壳 → HTTP 直连 2017:7788 → /conversation 聊意图
  → 写任务卡到 docs/dispatch/T<n>-*.md
  → Engine 派发 Claude Code（可后台 CLI）/ 手动 GUI 挂起等人
  → 收单 → 五态：待分派 → 执行中 → 已回写 → 已关闭
```

小改动（单文件 1–5 行 / 查信息）→ **直接处理，不强制走看板**（红线 12：不擅自启用 CCC）。

用户显式触发：「按 CCC 流程跑 X」/「用看板跑 X」/ 设备壳上点转任务。

---

## 席位与执行体（2026-08-06）

| 席位 | 绑定 |
|------|------|
| 日常开发 | **OpenCode**（2017 默认，6102） |
| 点名开发 / 默认验收 | **Claude Code**（6100）；交叉：谁开发对家验收 |
| 难度突击 | **Cursor**（写码；**不验收**） |
| 管理 | **Codex**（出卡/裁决；**不验收**） |
| M1 IDE | 开发中枢 + 交叉验收入口 |
| Trae | 停用 |
| HTTP 看板/运维 | 人机实时面 |
| Desktop | 暂缓 |

Engine 按卡头派发开发；验收在 M1 由对家完成——用户**不**需要选 Codex 验收。

**状态机**：

```text
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回 → 待分派（人工重派）
```

非法转移抛 `IllegalTransitionError`。

---

## 红线（摘要）

| # | 一句话 |
|---|--------|
| 1 | 不动系统文件 / 密钥 |
| 3 | 不超出任务卡范围 |
| 11 | Verdict 必须有文件 |
| 12 | 禁止 agent 自主启用 CCC |
| R-15 | 禁止 CCC 本体经看板自消费 |

全文：`references/red-lines.md`

**已退役勿提**：Hub :7777 · Board :7775 · sidecar · scripts/ccc-engine · 6+1 列 ·「OpenCode 已禁用」误判。

---

## 关键资产

| 路径 | 说明 |
|------|------|
| `CURSOR.md` | Cursor 入口与现况 |
| `STARTUP-BRIEF.md` | 启动 SSOT |
| `docs/INDEX.md` | 文档索引 §0 |
| `docs/architecture.md` | 架构概览（新栈 `server/`） |
| `docs/product/dev-channel.md` | 席位谁干什么 |
| `server/engine/` · `server/board/` · `server/web/` | 新栈核心 |
| `docs/dispatch/` | ★ 任务卡唯一事实源 |
| `references/red-lines.md` | 红线 |

当前版本见 `VERSION`。历史见 `CHANGELOG.md`。
