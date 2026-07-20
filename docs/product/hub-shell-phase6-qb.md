# Hub-Shell Phase6 — 第一笔真实业务仓

> 日期：2026-07-20 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) §8「通过后再覆盖真实仓」

## 选择

| 项 | 值 |
|----|-----|
| 仓 | **qb**（doctor OK，engine eligible） |
| 意图 | small 烟测：写入并提交 `.ccc/flow-smoke.md` |
| epic | `phase6-qb-1784559818` |
| 结果 | `user_stage=done`，1 work **released**（约 5.5 min） |

## 验收对照

| 断言 | 结果 |
|------|------|
| epic 进 backlog + flow `epic_created`/snapshot | 绿 |
| 扇出 work | 绿（`*-w1`） |
| 无人值守至 released | 绿 |
| 未对 CCC orch 误投 | 绿 |

## 差异 / 注意

- 首次 transfer 遇 Hub 空响应时需重试（与 Phase5a 相同）；不要用空 `epic_id` 前缀做 `ui_hidden`（会误匹配全板）。
- qb 上既有业务 epic（如 V5-V6）与本烟测并存；烟测卡已 `ui_hidden`。
- 真实业务意图（非 flow-smoke）下一刀再铺；本阶段只证明 **真实仓路径 = demo 同形**。

## 下一步（本长任务外）

- 第二笔真实仓（如 `xianyu` / `hp`）用业务向 small 意图
- 保持 soak / released / outbox 烟测在 CI 或周检
