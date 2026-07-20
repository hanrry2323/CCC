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
