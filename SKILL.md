---
name: ccc-protocol
description: "CCC — Connect–Claude Code. Loop Engineer: 任意设备壳经 HTTP 直连 2017 单端服务；对话口接大脑 Agent；薄驱动 Engine + 文档流转 + 看板/HTTP 远端开发。Trigger: '按 CCC 流程跑 X', 'ccc 跑一下 X', '定稿转任务', '用看板跑 X'"
---

# CCC — Connect–Claude Code

> **Loop Engineer。** 人定意图，系统自动编排与自主执行。  
> **任意设备壳**（Desktop / 网页 / 手机）经 HTTP 直连 **2017 单端 :7788**；对话口接**大脑 Agent**（Claude Code CLI via 6100）；编排面（**薄驱动 Engine + 文档流转 + 看板/HTTP**）远端开发。  
> 叙事 SSOT：`docs/VISION.md` · 启动：`STARTUP-BRIEF.md` · 权威链：`docs/INDEX.md` §0（重构决策定稿 + 契约 v1 最高优先级）· 版本：`VERSION`（**v0.70.0**）

**含义**：**C**onnect–**C**laude **C**ode。

---

## 启动（懒加载）

```bash
cat STARTUP-BRIEF.md          # 必读
cat docs/VISION.md            # 定位（对外口径）
cat docs/INDEX.md             # §0 权威链
grep -A 15 "## 红线 11" references/red-lines.md
cat docs/architecture.md      # 架构概览
```

---

## 人机优先路径（HTTP 直连 2017）

```text
任意设备壳 → HTTP 直连 2017:7788 → /conversation 聊意图
  → 写任务卡到 docs/dispatch/T<n>-*.md
  → Engine 派发执行体（可后台 CLI 自动拉起 / 手动 GUI 挂起等人）
  → 收单 → 状态机流转：待分派 → 执行中 → 已回写 → 已关闭
```

小改动（单文件 1–5 行 / 查信息）→ **直接处理，不强制走看板**（红线 12：不擅自启用 CCC）。

用户显式触发示例：「按 CCC 流程跑 X」/「用看板跑 X」/ 设备壳上点转任务。

---

## 编排：执行体注册表（契约 §7）

Engine 按 `server/config/executors.json` 注册表派发执行体——用户**不**需要选择角色：

| 角色 | 分类 | 当前绑定 | 看板状态机 |
|------|------|----------|------------|
| product | 可后台 CLI | Claude Code | 拆任务卡 → 子卡 |
| dev | 可后台 CLI | OpenCode | 写代码 → 提交 |
| reviewer | 可后台 CLI | Claude Code | 语义审查 → verdict |
| tester | 可后台 CLI | OpenCode | pytest + 验收清单 |
| ops | 手动 GUI | — | 健康检查（不动 board） |

**派发规则**：`可后台 CLI` → Engine 自动拉起；`手动 GUI` → 挂起等人；未知角色 → 不派发。

**状态机 = 契约 §2 五态**：

```text
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回（附问题清单）→ 待分派（人工重派）
```

**非法状态转移一律抛 `IllegalTransitionError`。**

---

## 红线（摘要）

| # | 一句话 |
|---|--------|
| 1 | 不动系统文件 / 密钥 |
| 3 | 不超出任务卡范围 |
| 6 | 执行体不互串（product 不写代码，reviewer 不写 plan） |
| 11 | Verdict 必须有文件 |
| 12 | 禁止 agent 自主启用 CCC |
| R-15 | 禁止 CCC 本体经看板自消费（平台改动用开发工具） |

全文：`references/red-lines.md`

---

## 关键资产

| 路径 | 说明 |
|------|------|
| `docs/VISION.md` | 产品叙事 SSOT |
| `docs/INDEX.md` | 文档索引（§0 重构决策 + 契约 v1 最高优先级） |
| `STARTUP-BRIEF.md` | 启动 SSOT |
| `docs/architecture.md` | 架构概览（新栈 `server/`） |
| `server/engine/` | 薄驱动核心：dispatch / main / scheduler / store / task / cluster |
| `server/board/` | 看板服务端：loader / queries / export / models / scheduler |
| `server/web/` | HTTP API + 静态页：server.py / brain.py（大脑 Agent 代理） |
| `server/config/executors.json` | 执行体注册表（契约 §7） |
| `docs/dispatch/` | ★ 任务卡文档（唯一事实源） |
| `references/red-lines.md` | 红线 |
| `references/board-task-schema.md` | 任务卡文档契约 |

当前版本见 `VERSION`。历史见 `CHANGELOG.md`。
