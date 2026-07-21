# Brief F3-1 · qb 业务仓 1 笔 small epic → released 少干预

| 字段 | 值 |
|------|-----|
| brief_id | `F3-20260721-qb-business-closure` |
| 波次 | F3 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | F2-1 / F2-2 已合入；2017 已拉至 `555b9bc`（含 version 端点） |
| 模型提示 | **编排窗用 Auto**；若需改 Engine 主循环或契约 → 停手升级高级并回架构 |

## 1. 目标

在真实业务仓 `qb` 跑 **1 笔 small 业务向 epic**（非 flow-smoke 脚本路径），从定稿 → transfer → product 扇出 → dev → reviewer/tester（small 可跳）→ kb → released，**全程无中途人批**，并回贴证据链。这是「流畅基线」宣告的最后一档。

## 2. 非目标

- 不让 hp / xianyu 同步跑（先 qb 一笔绿，再扩）  
- 不改 Engine 主循环 / 不改 transfer·flow 契约  
- 不强制 reviewer/tester（small 可跳；以 `complexity=small` 为准）  
- 不接入 CI / 不自动部署  
- 不把 flow-smoke 当业务向（Phase12 已区分）  

## 3. 契约变更

无。若证据链发现 board/flow 字段缺失，先回架构开 hotfix brief，不在本 brief 内改契约。

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| Phase6 qb flow-smoke 绿（脚本路径） | 业务向 epic（README/真实业务文档）少干预闭环未最近验证 |
| Phase12 qb README 双机路径 | 全程无中途人批的端到端证据链未沉淀 |
| F2-1 soak / F2-2 双机核对 | 缺「人只在意图门 + abnormal」的实战样本 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `apps/qb/`（业务仓；按需读 / 写业务文档）· `scripts/smoke-qb-biz-small.sh`（若需新增/调整）· `docs/product/hub-shell-phase12-business-intent.md`（追加证据链段，不动既有结论）· 本 brief §8 | 改 Engine 主循环、改 Hub API、改 Desktop、改 transfer·flow 契约 |
| 过桥 | 否 | — | |
| 壳 | 否 | — | |
| 架构 | 验收 | 本 brief · 宣告「流畅基线」 | 代写实现 |

## 6. 行为规格

1. 选 `qb` 一笔真实业务向 small epic（如 README 补段、文档对齐、小修复）；**非** flow-smoke 模板。  
2. 经 Desktop 定稿 → transfer（或等价 CLI 投递）→ 入 qb backlog。  
3. Engine 自动：product 扇出 → dev → (small 跳 reviewer/tester) → kb → released。**中途不点批准**。  
4. 若遇 abnormal：按止损口径（Phase9）记录，**不在本 brief 内改 Engine**；回贴现象，架构开 hotfix。  
5. 证据链回贴 §8：  
   - epic_id + split_status 终态  
   - 各 work tid + 终态  
   - 关键 flow 事件（fanout / work_status / epic_done）  
   - `bash scripts/ccc-dual-host-check.sh` 输出（确认双机对齐）  
   - 是否出现人批（应为 0）  
6. 通过后回写 `docs/product/hub-shell-phase-status.md` 新增 `F3-1 qb 业务向闭环 green` 行。  

## 7. 验收清单

- [x] qb 1 笔业务向 epic 全程无中途人批 → released
- [x] 证据链完整（epic_id / works / flow 事件 / 双机核对输出）
- [x] abnormal 数 = 0（若有则回贴现象，不修 Engine）
- [x] `phase-status.md` 新增 F3-1 行
- [x] 白名单外无改动
- [x] 未改 Engine 主循环 / 契约

## 8. 执行回贴（执行面填）

| 项 | 值 |
|----|-----|
| epic_id | `qb-biz-small-1784631027-3784` |
| split_status 终态 | `done` |
| works（tid → 终态） | `qb-biz-small-1784631027-3784-w1` → `released` |
| 关键 flow 事件 | `epic_created` → `fanout` → `work_status=planned`；其后 board：planned→in_progress→testing→verified→released；snapshot `user_stage=done`（flow 日志未落后续 `epic_done`，见 phase12 文注） |
| 双机核对输出 | `M1: v0.52.2 6b62220` / `2017: v0.52.2 6b62220 v1` / `aligned: yes` |
| 人批次数 | 0 |
| abnormal | 无 |
| 补充 | smoke `scripts/smoke-qb-biz-small.sh` PASS；qb commits `a61508fd` `83a1fd9d` `3cf86058`；README 含 `stamp=qb-biz-1784631027`；全程 ~277s |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | （待填：通过 → 宣告流畅基线 / 打回） |
| 缺口 | |
| 验收日 | |
