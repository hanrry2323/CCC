# Brief F3-3 · xianyu 业务仓 1 笔 small epic → released 少干预

| 字段 | 值 |
|------|-----|
| brief_id | `F3-20260721-xianyu-business-closure` |
| 波次 | F3 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | F3-1 / F3-2 已合入 |
| 模型提示 | **编排窗用 Auto**；若需改 Engine 主循环或契约 → 停手升级高级并回架构 |

## 1. 目标

在真实业务仓 `xianyu` 跑 **1 笔 small 业务向 epic**（非 flow-smoke），定稿 → transfer → product 扇出 → dev → kb → released，**全程无中途人批**，回贴证据链。**F3 第三档 · 流畅基线宣告的最后一笔。**

## 2. 非目标

- 不修 F3-1/F3-2 发现的 `epic_done` 流事件缺口（候选 hotfix H-1，另开）  
- 不改 Engine 主循环 / 不改 transfer·flow 契约  
- 不强制 reviewer/tester（small 可跳）  
- 不把 flow-smoke 当业务向  
- 不处理 xianyu 历史「脏跳过」遗留（Phase8 已记；本轮只跑新业务向）  

## 3. 契约变更

无。

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| Phase10–11 xianyu 卫生 + flow-smoke 绿 | xianyu 业务向 epic 少干预闭环未最近验证 |
| F3-1 qb / F3-2 hp 同口径证据链 | xianyu 同口径证据链 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `apps/xianyu/`（业务仓；按需读/写业务文档）· `scripts/smoke-xianyu-biz-small.sh`（若需新增/调整；可仿 qb/hp 模板）· `docs/product/hub-shell-phase10-xianyu-hygiene.md` 或 `phase11-xianyu.md`（追加证据链段，不动既有结论）· `docs/product/hub-shell-phase-status.md`（仅新增 F3-3 行）· 本 brief §8 | 改 Engine 主循环、改 Hub API、改 Desktop、改 transfer·flow 契约 |
| 过桥 / 壳 | 否 | — | |
| 架构 | 验收 + 宣告 | 本 brief · 流畅基线宣告 | 代写实现 |

## 6. 行为规格

1. 选 `xianyu` 一笔真实业务向 small epic（README 补段 / 文档对齐 / 小修复）。  
2. 经定稿 → transfer → xianyu backlog → Engine 自动 product→dev→kb→released，**中途不点批准**。  
3. 若遇 abnormal：回贴现象，不改 Engine；架构开 hotfix。  
4. 证据链回贴 §8（仿 F3-1/F3-2 模板）：epic_id / split_status / works / 关键 flow 事件 / 双机核对输出 / 人批次数 / abnormal / xianyu commits / README stamp。  
5. 通过后回写 `phase-status.md` 新增 `F3-3 xianyu 业务向闭环 green` 行；对应 phase 文追加证据链段。  

## 7. 验收清单

- [x] xianyu 1 笔业务向 epic 全程无中途人批 → released
- [x] 证据链完整（仿 F3-1/F3-2 模板）
- [x] abnormal 数 = 0（若有则回贴现象，不修 Engine）
- [x] `phase-status.md` 新增 F3-3 行
- [x] 对应 phase 文追加证据链段（不动既有结论）
- [x] 白名单外无改动
- [x] 未改 Engine 主循环 / 契约

## 8. 执行回贴（执行面填）

| 项 | 值 |
|----|-----|
| epic_id | `xianyu-biz-small-1784632947-6393` |
| split_status 终态 | `done` |
| works（tid → 终态） | `xianyu-biz-small-1784632947-6393-w1` → `released` |
| 关键 flow 事件 | `epic_created` → `fanout` → `work_status=planned`；board：planned→in_progress→testing→verified→released；snapshot `user_stage=done` |
| 双机核对输出 | `M1: v0.52.2 202bd31` / `2017: v0.52.2 202bd31 v1` / `aligned: yes` |
| 人批次数 | 0 |
| abnormal | 无 |
| xianyu commits | `7c36391` · `a072128` · `b5d658d` |
| README stamp | `xianyu-biz-1784632947` |
| 补充 | 新 `scripts/smoke-xianyu-biz-small.sh`；证据链追加于 `hub-shell-phase11-xianyu.md`；全程 ~279s；smoke PASS |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | **通过** `1526ca1` · xianyu 样本绿 · **流畅基线达成**（qb/hp/xianyu 三仓全绿） |
| 缺口 | 同 F3-1/F3-2：`epic_done` 流事件未补 → hotfix H-1（F3 后开） |
| 验收日 | 2026-07-21 |

**审阅：** epic_id + split_status=done + w1→released + snapshot user_stage=done + abnormal=0 + 人批 0 + 双机 aligned:yes + xianyu 3 commits + README stamp；phase-status F3-3 行已加；phase11 证据链追加（不动既有结论）；新 `smoke-xianyu-biz-small.sh`；无 Engine/契约改动。
