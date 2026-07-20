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
