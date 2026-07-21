# Brief F3-2 · hp 业务仓 1 笔 small epic → released 少干预

| 字段 | 值 |
|------|-----|
| brief_id | `F3-20260721-hp-business-closure` |
| 波次 | F3 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | F3-1 已合入（qb 样本绿） |
| 模型提示 | **编排窗用 Auto**；若需改 Engine 主循环或契约 → 停手升级高级并回架构 |

## 1. 目标

在真实业务仓 `hp` 跑 **1 笔 small 业务向 epic**（非 flow-smoke），定稿 → transfer → product 扇出 → dev → kb → released，**全程无中途人批**，回贴证据链。F3 第二档。

## 2. 非目标

- 不让 xianyu 同步跑（先 hp 绿，再 xianyu）  
- 不改 Engine 主循环 / 不改 transfer·flow 契约  
- 不修 F3-1 发现的 `epic_done` 流事件缺口（候选 hotfix，另开）  
- 不强制 reviewer/tester（small 可跳）  
- 不把 flow-smoke 当业务向  

## 3. 契约变更

无。

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| Phase8 hp flow-smoke 绿（xianyu 脏跳过） | hp 业务向 epic 少干预闭环未最近验证 |
| F3-1 qb 样本 + 证据链模板 | hp 同口径证据链 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `apps/hp/`（业务仓；按需读/写业务文档）· `scripts/smoke-hp-biz-small.sh`（若需新增/调整；可仿 qb 模板）· `docs/product/hub-shell-phase8-hp.md`（追加证据链段，不动既有结论）· `docs/product/hub-shell-phase-status.md`（仅新增 F3-2 行）· 本 brief §8 | 改 Engine 主循环、改 Hub API、改 Desktop、改 transfer·flow 契约 |
| 过桥 / 壳 | 否 | — | |
| 架构 | 验收 | 本 brief | 代写实现 |

## 6. 行为规格

1. 选 `hp` 一笔真实业务向 small epic（README 补段 / 文档对齐 / 小修复）。  
2. 经定稿 → transfer → hp backlog → Engine 自动 product→dev→kb→released，**中途不点批准**。  
3. 若遇 abnormal：回贴现象，不改 Engine；架构开 hotfix。  
4. 证据链回贴 §8（仿 F3-1 qb 模板）：epic_id / split_status / works / 关键 flow 事件 / 双机核对输出 / 人批次数 / abnormal / hp commits / README stamp。  
5. 通过后回写 `phase-status.md` 新增 `F3-2 hp 业务向闭环 green` 行；`phase8-hp.md` 追加证据链段。  

## 7. 验收清单

- [ ] hp 1 笔业务向 epic 全程无中途人批 → released
- [ ] 证据链完整（仿 F3-1 模板）
- [ ] abnormal 数 = 0（若有则回贴现象，不修 Engine）
- [ ] `phase-status.md` 新增 F3-2 行
- [ ] `phase8-hp.md` 追加证据链段（不动既有结论）
- [ ] 白名单外无改动
- [ ] 未改 Engine 主循环 / 契约

## 8. 执行回贴（执行面填）

| 项 | 值 |
|----|-----|
| epic_id | |
| split_status 终态 | |
| works（tid → 终态） | |
| 关键 flow 事件 | |
| 双机核对输出 | |
| 人批次数 | 0 |
| abnormal | 无 / 现象 |
| hp commits | |
| README stamp | |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | （待填） |
| 缺口 | |
| 验收日 | |
