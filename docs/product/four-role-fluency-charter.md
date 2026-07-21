# CCC 四面协作 · 流畅基线建档

> **状态**：架构定稿（2026-07-21）  
> **基线版本**：`VERSION` v0.52.2（能跑，未宣称流畅）  
> **目标签**：流畅基线（建议对外 bump 时再定 `v0.53.x`，以验收绿为准）  
> **冲突裁决**：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) > 本文协作约定

---

## 1. 收益裁决

| 做法 | 成本 | 收益 | 裁决 |
|------|------|------|------|
| 始终开满 4 窗闲聊 | 高 | 低 | **不推荐** |
| **4 角色 + brief 定稿 + 按需开窗** | 中 | 高 | **推荐** |
| 退回简单前端/后端两窗 | 低 | 低（跨面落空） | **不适用** |

**一句话**：四个角色值得设；四个对话框不必一直开满。收益来自「按面分工 + 书面 brief」，不来自「多开窗」。

---

## 2. 角色（按面 · 固定四个）

| 角色 | 负责面 | 开窗策略 | 目录白名单 |
|------|--------|----------|------------|
| **架构** | 意图门、契约、验收 | **常开** | brief / docs 契约 / 打回清单 |
| **壳** | 对话面 UI | 有 brief 才开 | `desktop/` · `src-tauri/` |
| **过桥** | Hub API / 信息流 | 有 brief 才开 | `scripts/chat_server/` |
| **编排** | Engine / Board | 有 brief 才开 | `scripts/engine/` · `scripts/board/roles/` |

并行规则：同一契约文件同时只一窗改；壳与过桥可并行（契约已冻结）；编排默认串行或并入过桥窗。

---

## 3. 「一轮」定义

**一轮 = 一笔 brief 从定稿到架构验收绿。**

1. 你 ↔ 架构：对齐 → 书面 brief（目标 / 非目标 / 契约 / 白名单 / 验收）  
2. 壳 / 过桥 / 编排：只认 brief  
3. 执行面回贴：改动摘要 + 自检结果  
4. 架构对照 brief：通过 / 打回  

口头说完但无 brief / 未验收 = **不计轮**。同轮多面并行仍计 **1 轮**。

---

## 4. 分波目标（主表）

| 波次 | 轮次 | 目标 | 预期结果 | 退出条件 |
|------|------|------|----------|----------|
| **F0 建制** | 1–2 | 协作基建 | brief 模板 + 四面白名单 + 验收口径 | 另三窗能按 brief 开工 |
| **F1 手感** | 5–7 | 日常路径不卡 | 冷启动 / 投递三态 / 右栏绑定 / 断线恢复无谎报 | 主路径手测清单全绿 |
| **F2 稳定** | 5–7 | 短时无人值守 | soak / hang·槽·orphan 达标；双机可核对 | `smoke-hub-shell-gate` full 绿；demo soak N≥5 且 `orphan_delta=0` |
| **F3 业务手感** | 3–5 | 真实仓像流水线 | qb/hp/xianyu 各 ≥1 笔业务 epic→released 少干预 | 人只在意图门与 abnormal；**宣称流畅基线** |

**合计：14–21 轮**（约每周 4–5 轮 → 3–5 周）。无 brief 纪律或冲突多 → 走向上沿。

---

## 5. 流畅基线 · 具体指标

| 指标 | 现在（约） | 目标结果 | 主责面 |
|------|------------|----------|--------|
| 主路径完成时间 | 能跑，偶发卡/重试 | 定稿→transfer 可见受理 ≤30s；右栏首事件 ≤10s | 壳+过桥 |
| 状态诚实度 | 偶有假离线/假完成 | 投递三态零谎报；`boundEpic` 不串轨 | 壳+过桥 |
| 冷启动手感 | 本地优先已绿，仍可磨 | 磁盘缓存首屏 ≤2s；Hub 后台同步不挡聊 | 壳 |
| 编排稳定性 | Phase13 门禁在，长跑仍紧 | soak N=5 `orphan_delta=0`；无槽泄漏/失控进程 | 编排 |
| 双机对齐 | 靠人工记版本 | M1 Desktop 与 2017 Hub/Engine commit 可核对 | 架构验收 |
| 返工率 | 跨面口头易漂移 | 验收打回率 ≤20%；契约变更 100% 先改 docs | 架构 |
| 人干预面 | 仍会盯流水线 | 默认只审意图门 + abnormal；中途不加人批 | 全员 |

---

## 6. 架构每轮验收口令

1. brief 白名单外无改动  
2. 契约若变：先改 docs（transfer / flow / hub-api-v1）  
3. 自检已跑：相关 `py_compile` / pytest / 约定 smoke  
4. 边界未破：对话面不写编排；不对 CCC orch 投 backlog（R-15）  
5. 退出条件对应该波次表格一行  

---

## 7. Brief 落盘（文件夹卫生）

| 规则 | 说明 |
|------|------|
| 唯一目录 | `docs/briefs/`（在已有 `docs/` 下，不新建项目根杂目录） |
| 模板 | [`../briefs/_TEMPLATE.md`](../briefs/_TEMPLATE.md) |
| 命名 | `YYYY-MM-DD-<slug>.md` |
| 禁止 | 散落到 `~/`、桌面、或项目根下临时二级目录 |

F0 已闭环：[`../briefs/2026-07-21-f0-four-role-charter.md`](../briefs/2026-07-21-f0-four-role-charter.md)。  
F1 断线恢复：done `eeaf388` — [`../briefs/2026-07-21-f1-disconnect-recovery.md`](../briefs/2026-07-21-f1-disconnect-recovery.md)。  
F1-2 投递三态：done `578e7fe` — [`../briefs/2026-07-21-f1-transfer-delivery-honesty.md`](../briefs/2026-07-21-f1-transfer-delivery-honesty.md)。  
F2-1 soak N=5：done `9af1fb4` — [`../briefs/2026-07-21-f2-soak-orphan-zero.md`](../briefs/2026-07-21-f2-soak-orphan-zero.md)。  
F2-2 双机核对：done `555b9bc` — [`../briefs/2026-07-21-f2-dual-host-version-check.md`](../briefs/2026-07-21-f2-dual-host-version-check.md)。  
F3-1 qb 业务向：done `327fd86`（流畅基线第一档）— [`../briefs/2026-07-21-f3-qb-business-closure.md`](../briefs/2026-07-21-f3-qb-business-closure.md)。  
F3-2 hp 业务向：done `6523330`（流畅基线第二档）— [`../briefs/2026-07-21-f3-hp-business-closure.md`](../briefs/2026-07-21-f3-hp-business-closure.md)。  
F3-3 xianyu 业务向：done `1526ca1`（流畅基线第三档）— [`../briefs/2026-07-21-f3-xianyu-business-closure.md`](../briefs/2026-07-21-f3-xianyu-business-closure.md)。  
**✅ 流畅基线达成** — [`fluency-baseline-achieved.md`](fluency-baseline-achieved.md)。  
派单档案：[`../briefs/PASTE-OPS.md`](../briefs/PASTE-OPS.md)。

---

## 8. 关联

- 北星：[`hub-shell-roadmap.md`](hub-shell-roadmap.md)  
- 阶段板：[`hub-shell-phase-status.md`](hub-shell-phase-status.md)  
- 开发通道：[`dev-channel.md`](dev-channel.md)  
- 可视化副本：[four-role-fluency-charter canvas](/Users/apple/.cursor/projects/Users-apple-program-CCC/canvases/four-role-fluency-charter.canvas.tsx)
