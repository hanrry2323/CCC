# 平台生产交付 · 固定长任务轮次（Claude 堆码 · Cursor 把关）

> **目标**：在 Layer1 已出门、程 B 已收口基础上，用 **4 轮 Claude `/loop` 长包 + Cursor 严审合入**，达到**平台生产级交付封印**。  
> **冻结（本清单外）**：Layer2 qb 域 KPI、飞轮 T1–T4 全自动、Ops UI 抛光。  
> **执行纪律**：中间不改轮次顺序、不插题；一轮不合格打回同包重写，不跳轮。  
> **分工**：Claude Code = 堆码；Cursor = 写包 / 严审 / 小修合入 / 热更 2017。

---

## 总闸（交付完成 = 全勾）

| # | 条件 |
|---|------|
| G1 | 四轮草稿包均已合入 main，双机 aligned |
| G2 | 平台单测相关套件绿；无未解释的 hard_red |
| G3 | production-readiness「平台生产交付」节勾完；下一开程才允许 Layer2 |
| G4 | 周刊金路径 checklist 仍有效（不新开 daemon） |

---

## 轮次表（固定）

### R1 · 013 门禁诚实（**已合入**）

| 项 | 内容 |
|----|------|
| 包 | [`013-reviewer-verdict-kpi-honesty.md`](./013-reviewer-verdict-kpi-honesty.md) |
| 分支 | `draft/013-reviewer-verdict-kpi-honesty` |
| 完成 | `work_abnormal_n` = MAX(cols, works)；quarantine 前写 FAIL verdict；测绿 |

### R2 · 014 reviewer/`--bg` 空转与超时收尸（**已合入**）

| 项 | 内容 |
|----|------|
| 包 | [`014-reviewer-bg-empty-verdict.md`](./014-reviewer-bg-empty-verdict.md) |
| 分支 | `draft/014-reviewer-bg-empty-verdict` |
| 完成 | 空输出/早退→FAIL；`.timeout`→TIMEOUT；markers 清理含 timeout/exitcode；测绿 |

### R3 · 015 失败可收加固（reopen / quarantine 口径）

| 项 | 内容 |
|----|------|
| 包 | `015-failure-reopen-quarantine-harden.md`（R2 合入后写） |
| 目标 | enabled 下瞬态 abnormal 有限 reopen 路径测稳；quarantine reason 必含可机读码 |
| 白名单方向 | `scripts/_task_reopen.py` · `scripts/engine/failure_router.py` · `_failure_ledger` · 测 |
| 完成 | 测绿；与 P-D 口径一致；不抬 quarantine 阈值乱杀 |

### R4 · 016 金路径回归包（平台测 + 文档封印）

| 项 | 内容 |
|----|------|
| 包 | `016-golden-path-regression-seal.md`（R3 合入后写） |
| 目标 | 平台侧可重复：hub-probe +（可选）matrix dry 或单元级 transfer_gate/prepare 回归；更新 production-readiness「平台生产交付：完成」 |
| 白名单方向 | `tests/scripts/**` · `scripts/ccc-hub-probe.sh`（仅测/薄改）· briefs |
| Cursor 另做 | 2017 真跑一笔小金路径或确认本周烟测已记 evidence（可不进 Claude） |
| 完成 | G1–G4 可勾；**本清单结束** |

---

## 每轮固定流程（不打断）

```text
Cursor 发包（md + 可复制 /loop 行）
  → 人转 Claude Code
  → Claude /loop 堆完回报 §8
  → Cursor 严审（不合格打回同包，不改轮次）
  → 小修 + 合入 main + 2017 热更
  → 勾本轮 → 写下一包 → 重复
```

---

## 明确不做（插入即违规）

- Layer2 qb / 飞轮自动化 / invent  
- Ops/SPA UI 大包、抬 `MAX_CONCURRENT` 当主修  
- Claude 改 authority / 红线 / 密钥 / scorecard 门槛数字 / 强推 main  
