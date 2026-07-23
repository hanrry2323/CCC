# 运维信心包（2026-07-24）

## 目标

老板在 **Desktop → 运维** 不问 Cursor，也能判断敢不敢对业务仓定稿 transfer。  
`invent` **继续硬关**；本阶段不开发无人自造。

权威：`docs/product/loop-engineer-authority.md`「invent 硬关」「运维信心」。

---

## 已落地

| 层 | 内容 |
|----|------|
| A | invent 延后口径落盘；efficiency `works[].dev_path`；abnormal→planned reopen 单测 |
| B1 | `/api/ops/summary`：`control`、`ready_to_dispatch`、`recent_failures`、`abnormal_cards`；`workspaces` 含活跃列计数 |
| B2 | Desktop OpsView：就绪条、mode/invent/Hub/资源 pills、异常 reopen、舰队 abnormal chip |
| SPA | `#/ops` 同口径小补（不抢 Desktop 主入口） |

---

## Desktop 绿灯验收清单

在 M1 Desktop「运维」页（Hub 经 `127.0.0.1:17777` 隧道）：

1. **红灯不敢乱下达**  
   - `ready_to_dispatch.ok=false` 顶部红条可读（Engine 停 / mode≠enabled / Hub 未听 / 红灯 / abnormal / saturated）。  
   - blockers 人话可见。

2. **绿灯敢定稿**  
   - Engine 在跑、mode=`enabled`、invent 关、无红灯、舰队 abnormal=0 → 绿条「可下达」。  
   - 对业务仓走对话定稿 → transfer（不经运维页派工）。

3. **abnormal 可处理**  
   - 「失败与异常」列出卡标题/仓/原因摘要。  
   - 「重开」→ planned（Hub `POST /api/tasks/reopen`）。  
   - 「看板」深链该仓看板。  
   - **不**自动归档；清场仍须人确认。

4. **invent 仍关**  
   - 状态条显示「invent 关」。  
   - 运维页**无**「自造任务」入口。

5. **舰队计数有数**  
   - 工作区 chips：planned / in_progress / testing / **abnormal** 非全空（有卡时）。

6. **资源一句话**  
   - 状态条或资源区可见 `headroom` / `saturated` / `collecting` 等 verdict。

---

## 明确不做

- 启用 invent / ops-auto 弹药当主业  
- Engine 卫生 epic 清板当运维健康  
- 用加 `MAX_CONCURRENT` 伪装运维绿灯  
- 把运维做成第二块派工看板
