# Hub-Shell Phase8 — 第二笔真实业务仓

> 日期：2026-07-20 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) Wave3 · 对齐 Phase6 同形烟测

## 选择

| 项 | 值 |
|----|-----|
| 原定仓 | **xianyu**（doctor OK，但 2017 工作区脏 ~338 条，未强开） |
| 实际仓 | **hp**（doctor OK，engine eligible，脏面可控） |
| 意图 | small 烟测：写入并提交 `.ccc/flow-smoke.md` |
| epic | `phase8-hp-1784562154-c275` |
| 结果 | `user_stage=done`，1 work **released**（约 9.5 min，含模板缺失自修） |

## 验收对照

| 断言 | 结果 |
|------|------|
| epic 进 backlog + flow | 绿 |
| 扇出 work | 绿（`*-w1`） |
| 无人值守至 released | 绿 |
| 未对 CCC orch 误投 | 绿 |

## 差异 / 注意

- **xianyu 跳过原因**：2017 仓大量 board/phases 删除未提交；按方案改切 `hp`。
- 首轮 product 卡住：2017 缺 `CCC/templates/plan.plan.md`（rsync 未带 templates）。已补齐 templates 并 kickstart Engine 后扇出成功。
- 同期 ccc-demo 上 Phase7 烟测 epic（`inbox-adopt` / `hub-api-v1`）曾占 product 槽并因缺模板刷错；已 `ui_hidden`。
- hide 纪律：仅 `epic` 与 `epic-*` 子卡。

## 结论

第二笔真实仓路径与 qb / ccc-demo **同形**；qb 非特例。

---

## F3-2 证据链（2026-07-21 · 业务向闭环）

> 追加；**不改**上文既有结论。路径：`scripts/smoke-hp-biz-small.sh`（新建 README stamp，非 flow-smoke）。

| 项 | 值 |
|----|-----|
| epic_id | `hp-biz-small-1784631864-4ce2` |
| split_status 终态 | `done`（epic 留 backlog） |
| work | `hp-biz-small-1784631864-4ce2-w1` → **released** |
| snapshot | `user_stage=done` · `board_status=ok` · abnormal=0 |
| 人批 | **0** |
| 耗时 | ~352s（pending → running → done） |
| hp commits | `db5b92a`（DoD gate）· `bc6280f`（README）· `20e3f2f`（version bump） |
| README stamp | `hp-biz-1784631864`（根 README 新建） |

### 关键事件（时间升序）

| ts (+08) | 来源 | 事件 |
|----------|------|------|
| 19:04:21 | flow-events | `epic_created` |
| 19:09:04 | flow-events | `fanout` → w1 planned |
| 19:09:04 | flow-events | `work_status` planned |
| 19:09:04 | board events | w1 planned → in_progress |
| 19:10:05 | board events | in_progress → testing → verified（small 门禁） |
| 19:10:12 | board events | verified → **released** |
| 19:10:16 | smoke | `user_stage=done` PASS |

> 同 F3-1：`flow-events.jsonl` 对本 epic 仅见 created/fanout/planned；后续以 board events + snapshot 为据（`epic_done` 缺口另开 hotfix）。

### 双机核对

```
M1: v0.52.2 6fa64b3
2017: v0.52.2 6fa64b3 v1
aligned: yes
```
