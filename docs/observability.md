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
| `.ccc/stats/events.jsonl` | move / product_* / hang / **opencode_start·opencode_done** |
| `.ccc/stats/summary.json` | 聚合（累计噪声大，不适合「上一笔」） |
| `~/.ccc/stats/opencode-timings.jsonl` | 跨仓 OpenCode 耗时 SSOT（小卡分钟数） |
| `~/.ccc/stats/host-resources.jsonl` | Mac2017 CPU/内存曲线（并行容量） |
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

- 同仓 OpenCode 互斥与残留收尸 → [`product/loop-engineer-authority.md`](product/loop-engineer-authority.md)「OpenCode 生命周期」

---

## 4. 回答「上一笔为何挂」

```bash
python3 scripts/ccc-failure-report.py --last 1
# 或
tail -1 .ccc/stats/failures.jsonl | python3 -m json.tool
```

---

## 5. OpenCode 耗时（小卡分钟数）

```bash
# 最近 20 条跨仓耗时
tail -20 ~/.ccc/stats/opencode-timings.jsonl | python3 -m json.tool --no-ensure-ascii
# 或按仓
grep opencode_done <workspace>/.ccc/stats/events.jsonl | tail -20
```

字段：`complexity`, `duration_s`（exec 内）, `wall_s`（launch→done）, `duration_min` / `wall_min`, `status`, `exit_code`, `killed`。

---

## 6. Mac2017 主机资源曲线（能否加并行）

```bash
python3 scripts/ccc-host-resources.py sample    # 立刻采一点
python3 scripts/ccc-host-resources.py tail      # sparkline
python3 scripts/ccc-host-resources.py summary   # p50/p95 + verdict
# Hub
curl -u ccc:ccc 'http://127.0.0.1:7777/api/ops/resources/history?n=120'
```

| verdict | 含义 |
|---------|------|
| `headroom` | load_ratio_p95&lt;0.55 且 mem_p95&lt;70% → 可试 `MAX_CONCURRENT+1` |
| `borderline` | 维持现状 |
| `saturated` | 勿加并行；先收尸/降负载 |
| `insufficient_data` | 采样不足（约需 12 分钟） |

主指标：`load_ratio = load1/ncpu`；关联字段 `active_dev` / `opencode_n`。同仓仍 1 路 OpenCode。

---

## 7. Ops 运维面旁路（供弹 / 心跳 / 喂灯）

> 权威：[`product/loop-engineer-authority.md`](product/loop-engineer-authority.md)「Ops 运维面」。Engine 不跑日审 tick。Desktop 总灯由旁路探针喂绿/橙/红。

| 项 | 路径 / 命令 |
|----|-------------|
| 日 diff 审 | `scripts/ccc-daily-diff-review.py --all-apps [--apply]` → `<app>/.ccc/reports/daily-review-YYYY-MM-DD.md` + watermark `.ccc/stats/daily-review-watermark.json` |
| 文档债 | `scripts/ccc-daily-docs-review.py --all-apps [--apply]` → 报告常写在 CCC `.ccc/reports/docs-review-*.md`；卡只进业务仓 |
| 定时 | `bash scripts/install-ops-plist.sh install --enable --apply-ammo` → `com.ccc.ops-daily-diff` / `com.ccc.ops-docs-review` |
| 回归 | `deploy/launchd/com.ccc.regress.plist.example`（**WorkingDirectory=业务仓**）；`ccc-board.py regress` |
| Hub 心跳 | `GET /api/ops/summary` → `logistics`（plist loaded、今日 decision、ops-auto 数） |

**禁止**往 CCC orch 建 `ops-auto`（`ops-ammo-orch-forbidden`）。`--apply` 仅 C/E/F（日审）与 docs medium+。
