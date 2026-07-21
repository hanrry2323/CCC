# Hub-Shell Phase11 — 第三笔真实业务仓 xianyu

> 日期：2026-07-21 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) Wave4 · 依赖 Phase10 卫生

## 选择

| 项 | 值 |
|----|-----|
| 仓 | **xianyu**（doctor OK；Phase10 已空板） |
| 意图 | small 烟测：写入并提交 `.ccc/flow-smoke.md` |
| epic | `phase11-xianyu-1784564802-dfa6` |
| 结果 | `user_stage=done`，work **released** |

## 验收对照

| 断言 | 结果 |
|------|------|
| epic 进 backlog + flow | 绿 |
| 扇出 work | 绿 |
| 无人值守至 released | 绿 |
| 未对 CCC orch 误投 | 绿 |

## 结论

第三笔真实仓路径与 qb / hp / ccc-demo **同形**；Phase8 欠账已补。

---

## F3-3 证据链（2026-07-21 · 业务向闭环 · 流畅基线末笔）

> 追加；**不改**上文既有结论。路径：`scripts/smoke-xianyu-biz-small.sh`（README stamp，非 flow-smoke）。

| 项 | 值 |
|----|-----|
| epic_id | `xianyu-biz-small-1784632947-6393` |
| split_status 终态 | `done`（epic 留 backlog） |
| work | `xianyu-biz-small-1784632947-6393-w1` → **released** |
| snapshot | `user_stage=done` · `board_status=ok` · abnormal=0 |
| 人批 | **0** |
| 耗时 | ~279s（pending → running → testing → done） |
| xianyu commits | `7c36391`（DoD gate）· `a072128`（README）· `b5d658d`（version bump） |
| README stamp | `xianyu-biz-1784632947` |

### 关键事件（时间升序）

| ts (+08) | 来源 | 事件 |
|----------|------|------|
| 19:22:25 | flow-events | `epic_created` |
| 19:25:41 | flow-events | `fanout` → w1 planned |
| 19:25:41 | flow-events | `work_status` planned |
| 19:25:41 | board events | w1 planned → in_progress |
| 19:26:46 | board events | in_progress → testing |
| 19:26:58 | board events | testing → verified |
| 19:27:06 | board events | verified → **released** |
| 19:27:06 | smoke | `user_stage=done` PASS |

> 同 F3-1/F3-2：`flow-events.jsonl` 仅见 created/fanout/planned；后续以 board events + snapshot 为据（`epic_done` 缺口 = hotfix H-1）。

### 双机核对

```
M1: v0.52.2 202bd31
2017: v0.52.2 202bd31 v1
aligned: yes
```
