# 平台生产交付 · 固定长任务轮次

> **更新（2026-07-28）**：**主轨暂停本清单 R3/R4**。当前主业 = **Relay Flash 单通道封印**（Cursor 独立；见 [`../briefs/2026-07-28-relay-flash-seal.md`](../briefs/2026-07-28-relay-flash-seal.md)）。  
> R1/R2 已合入；R3/R4 待 Relay 封印后由 **Cursor 自跑**收口（**不用** Claude `/loop`）。  
> **冻结**：Layer2 qb、飞轮自动、Ops UI 抛光、invent。

---

## 总闸（平台交付完成 = 全勾 · 次轨）

| # | 条件 |
|---|------|
| G1 | 四轮草稿包均已合入 main，双机 aligned |
| G2 | 平台单测相关套件绿；无未解释的 hard_red |
| G3 | production-readiness「平台生产交付」节勾完；下一开程才允许 Layer2 |
| G4 | 周刊金路径 checklist 仍有效（不新开 daemon） |

**前置主闸**：Relay Flash 封印（文档一致 · 2017 主机对齐 · 活体 PaidGuarantee/cache · vitest+热更）先完成。

---

## 轮次表

### R1 · 013 门禁诚实（**已合入**）

| 项 | 内容 |
|----|------|
| 包 | [`013-reviewer-verdict-kpi-honesty.md`](./013-reviewer-verdict-kpi-honesty.md) |
| 完成 | `work_abnormal_n` = MAX(cols, works)；quarantine 前写 FAIL verdict；测绿 |

### R2 · 014 reviewer/`--bg` 空转与超时收尸（**已合入**）

| 项 | 内容 |
|----|------|
| 包 | [`014-reviewer-bg-empty-verdict.md`](./014-reviewer-bg-empty-verdict.md) |
| 完成 | 空输出/早退→FAIL；`.timeout`→TIMEOUT；markers 清理含 timeout/exitcode；测绿 |

### R3 · 015 失败可收加固（**已合入** · Cursor 自跑）

| 项 | 内容 |
|----|------|
| 包 | [`015-failure-reopen-quarantine-harden.md`](./015-failure-reopen-quarantine-harden.md) |
| 完成 | `should_auto_refeed` 纯闸 + pid timeout 对称清理；机读码测绿；engine 早跳过 |

### R4 · 016 金路径回归包（**暂停 · 未写包**）

| 项 | 内容 |
|----|------|
| 包 | `016-golden-path-regression-seal.md`（Relay 封印后 Cursor 写并自跑） |
| 目标 | hub-probe + 薄回归；production-readiness「平台生产交付：完成」 |
| 完成 | G1–G4 可勾；**本清单结束** |

---

## 明确不做

- Layer2 qb / 飞轮自动化 / invent  
- Ops/SPA UI 大包、抬 `MAX_CONCURRENT` 当主修  
- 本开程用 Claude 草稿工堆 R3/R4（改由 Cursor）  
- 把 HK 出口轮换加回 flash / 重开 Pro/code 主业  
