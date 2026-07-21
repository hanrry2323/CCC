# Hub-Shell Phase12 — 首笔业务向意图（非 flow-smoke）

> 日期：2026-07-21 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) Wave4

## 选择

| 项 | 值 |
|----|-----|
| 仓 | **qb** |
| 意图 | 在已跟踪文档补「双机路径」小节（真实文档债，非 `.ccc/flow-smoke.md`） |
| 首轮 epic | `phase12-qb-biz-1784565344-e7c6` → 写了 `AGENTS.md` 但 **被 gitignore**（`/agents.md` 在 macOS 大小写不敏感下命中）→ salvage 无真实入库 |
| 自修 epic | `phase12-qb-readme-1784566074-edb4` → **README.md** |
| 结果 | `user_stage=done`，work **released**；commit `3a867ae1`（README）+ `a740b091`（version bump） |

## 验收对照

| 断言 | 结果 |
|------|------|
| 非 flow-smoke 路径 | 绿（README.md） |
| git log 含 epic/work id | 绿 |
| README 含双机路径表 | 绿 |
| 无人值守至 released | 绿（自修轮） |

## 差异 / 注意

- 业务仓若忽略 `AGENTS.md`/`agents.md`，定稿白名单须避开；优先改已跟踪文件。
- 首轮板态曾到 `verified` 即被烟测接受；自修轮以 **released + 真实 commit** 关门。

## 结论

业务向 small 路径可用；Wave4 Phase10–12 收口。

---

## F3-1 证据链（2026-07-21 · 流畅基线样本）

> 追加；**不改**上文既有结论。路径：`scripts/smoke-qb-biz-small.sh`（业务向 README stamp，非 flow-smoke）。

| 项 | 值 |
|----|-----|
| epic_id | `qb-biz-small-1784631027-3784` |
| split_status 终态 | `done`（epic 留 backlog） |
| work | `qb-biz-small-1784631027-3784-w1` → **released** |
| snapshot | `user_stage=done` · `board_status=ok` · abnormal=0 |
| 人批 | **0**（transfer 后无人值守至 done） |
| 耗时 | ~277s（pending → running → done） |
| qb commits | `a61508fd`（DoD gate）· `83a1fd9d`（README stamp）· `3cf86058`（version bump） |
| README | 含 `stamp=qb-biz-1784631027` 小节 |

### 关键事件（时间升序）

| ts (+08) | 来源 | 事件 |
|----------|------|------|
| 18:50:28 | flow-events | `epic_created` |
| 18:53:08 | flow-events | `fanout` → w1 planned |
| 18:53:08 | flow-events | `work_status` planned |
| 18:53:08 | board events | w1 planned → in_progress |
| 18:54:54 | board events | in_progress → testing → verified（small 门禁） |
| 18:54:57 | board events | verified → **released** |
| 18:55:04 | smoke | `user_stage=done` PASS |

> 注：`~/.ccc/flow-events.jsonl` 对本 epic 仅见 `epic_created` / `fanout` / `work_status=planned`；后续阶段以 **board events + snapshot** 为据。若需强制补齐 `epic_done` 流事件，另开 hotfix brief（本波次不改 Engine）。

### 双机核对

```
M1: v0.52.2 6b62220
2017: v0.52.2 6b62220 v1
aligned: yes
```
