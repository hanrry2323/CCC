# CCC 可观测性 / 埋点（v0.40 权威）

> 运维一句话：`python3 scripts/ccc-failure-report.py --last 20`  
> Hub：控制台 →「最近失败」→ `GET /api/failures`

---

## 1. 失败账本（主 SSOT）

| 项 | 值 |
|----|-----|
| 路径 | `<workspace>/.ccc/stats/failures.jsonl` |
| 写入 | `_failure_ledger.record_failure`（quarantine / product_fail / …） |
| 模块 | [`scripts/_failure_ledger.py`](../scripts/_failure_ledger.py) |
| CLI | [`scripts/ccc-failure-report.py`](../scripts/ccc-failure-report.py) |

每行字段：`ts, task_id, workspace, role, phase, from_col, to_col, exit_code, reason, stderr_path, stderr_tail, related_stats_event`。

**禁止**对 ledger 写失败 `except: pass`。

---

## 2. 已有半套（仍保留）

| 表面 | 用途 |
|------|------|
| `.ccc/stats/events.jsonl` | move / product_* / hang 事件流 |
| `.ccc/stats/summary.json` | 聚合（累计噪声大，不适合「上一笔」） |
| `.ccc/quarantines/<id>/` | 归档包 + `reason.txt` |
| `.ccc/board/events/<id>.events.jsonl` | 列移动时间线 |
| `~/.ccc/logs/engine.log` | 叙事日志 |
| `:7776/api/stats` | Engine 瞬时快照（仅进程在跑时） |

---

## 3. 控制面与可观测性的关系

见 [`CONTROL.md`](CONTROL.md)：

- `enabled`：只消费队列 → 失败应来自真实任务，而非自造 evolve
- `invent`：允许自造 → 失败账本仍必写
- `disabled`：无 Engine → 无新 ledger（除非测试/手工）

---

## 4. 回答「上一笔为何挂」

```bash
python3 scripts/ccc-failure-report.py --last 1
# 或
tail -1 .ccc/stats/failures.jsonl | python3 -m json.tool
```
