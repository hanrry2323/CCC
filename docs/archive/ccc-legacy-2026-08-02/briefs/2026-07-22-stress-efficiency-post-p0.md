# Efficiency report `stress-mx-20260722`

generated: `2026-07-23T00:31:41+08:00`

## 1. Executive summary

- Dispatches: **20/20** ok
- Works by column: `{'in_progress': 2, 'released': 16, 'abnormal': 2, 'planned': 3, 'verified': 1}`
- Epics split_status: `{'running': 2, 'failed': 2, 'planned': 2}`
- queue_wait_s p50/p95: **2092.0** / **7319.0** (n=23)
- dev_wall_s p50/p95: **76.0** / **1610.35** (n=22)
- gate_wall_s p50/p95: **1042.0** / **3328.5** (n=23)
- e2e_work_s p50/p95/max: **7291.0** / **10653.0** / **10653.0**

### Bottlenecks

- 排队主导：queue_wait p95=7319s ≫ dev p95=1610s（同仓互斥/幽灵槽）
- 审测偏慢：gate p95=3328s > dev p95=1610s
- abnormal=2 张 work 未闭环
- epic failed=2

## 2. Scenario dispatches

| app | sid | name | http | ok | epic |
|-----|-----|------|------|----|------|
| ccc-demo | s01 | 单 phase 小功能成功 | 200 | True | `stress-mx-20260722-ccc-demo-import-fa530d64` |
| ccc-demo | s02 | 3-phase 中等扇出 | 200 | True | `stress-mx-20260722-ccc-demo-72d95700` |
| ccc-demo | s03 | 审测 FAIL 回滚路径可观察 | 200 | True | `stress-mx-20260722-ccc-demo-623a4a09` |
| ccc-demo | s04 | 纯纸面探针 script_seed | 200 | True | `stress-mx-20260722-paper-intent-probe-487bb12e` |
| qb | s01 | 单 phase 小功能成功 | 200 | True | `stress-mx-20260722-qb-import-16410dce` |
| qb | s02 | 3-phase 中等扇出 | 200 | True | `stress-mx-20260722-qb-ab4dac4d` |
| qb | s03 | 审测 FAIL 回滚路径可观察 | 200 | True | `stress-mx-20260722-qb-dbe5c553` |
| qb | s04 | 纯纸面探针 script_seed | 200 | True | `stress-mx-20260722-paper-intent-probe-93ed1edd` |
| ccc-demo | s05 | 功能探针禁止 script_seed 劫持 | 200 | True | `stress-mx-20260722-dry-run-e80fd42a` |
| ccc-demo | s06 | 看板卫生 python/board_ops | 200 | True | `stress-mx-20260722-16cd286c` |
| ccc-demo | s07 | 缺意图探针 transfer 拒单 | 400 | True | `` |
| qb | s05 | 功能探针禁止 script_seed 劫持 | 200 | True | `stress-mx-20260722-dry-run-5488df58` |
| qb | s06 | 看板卫生 python/board_ops | 200 | True | `stress-mx-20260722-dbf935cd` |
| qb | s07 | 缺意图探针 transfer 拒单 | 400 | True | `` |
| ccc-demo | s08 | 依赖链两 phase | 200 | True | `stress-mx-20260722-ccc-demo-a-b-54f9915f` |
| ccc-demo | s09 | abnormal 重开再跑 | 200 | True | `stress-mx-20260722-ccc-demo-d791a69a` |
| ccc-demo | s10 | 路径约束纸面/探针不 hang | 200 | True | `stress-mx-20260722-ccc-demo-0e181b42` |
| qb | s08 | 依赖链两 phase | 200 | True | `stress-mx-20260722-qb-a-b-ac6b4b8f` |
| qb | s09 | abnormal 重开再跑 | 200 | True | `stress-mx-20260722-qb-10a0a6cc` |
| qb | s10 | 路径约束纸面/探针不 hang | 200 | True | `stress-mx-20260722-qb-872e2ceb` |

## 3. Work timing table

| app | work | col | queue_s | dev_s | gate_s | e2e_s | fail_loops |
|-----|------|-----|--------|-------|--------|-------|------------|
| ccc-demo | `stress-mx-20260722-16cd286c-w1` | released | 516.0 | 1522.0 | 129.0 | 2839.0 | 0 |
| ccc-demo | `ess-mx-20260722-ccc-demo-0e181b42-w1` | released | 2092.0 | 0.0 | 2632.0 | 4778.0 | 2 |
| ccc-demo | `ess-mx-20260722-ccc-demo-623a4a09-w1` | released | 107.0 | 20.0 | 275.0 | 2858.0 | 0 |
| ccc-demo | `ess-mx-20260722-ccc-demo-72d95700-w1` | released | 127.0 | 256.0 | 115.0 | 2857.0 | 0 |
| ccc-demo | `ess-mx-20260722-ccc-demo-72d95700-w2` | released | 2991.0 | 129.0 | 227.0 | 4882.0 | 0 |
| ccc-demo | `ess-mx-20260722-ccc-demo-72d95700-w3` | in_progress | 6604.0 | 15.0 | 1608.0 | 8227.0 | 7 |
| ccc-demo | `mx-20260722-ccc-demo-a-b-54f9915f-w1` | released | 2092.0 | 44.0 | 1230.0 | 4778.0 | 1 |
| ccc-demo | `mx-20260722-ccc-demo-a-b-54f9915f-w2` | abnormal | 6515.0 | 238.0 | 1106.0 | 7859.0 | 3 |
| ccc-demo | `ess-mx-20260722-ccc-demo-d791a69a-w1` | abnormal | 3055.0 | 1615.0 | 0.0 | 7302.0 | 2 |
| ccc-demo | `20260722-ccc-demo-import-fa530d64-w1` | released | 0.0 | 36.0 | 3279.0 | 4885.0 | 6 |
| ccc-demo | `ress-mx-20260722-dry-run-e80fd42a-w1` | released | 516.0 | 590.0 | 975.0 | 4864.0 | 0 |
| ccc-demo | `60722-paper-intent-probe-487bb12e-w1` | released | 127.0 | 1.0 | 1945.0 | 2858.0 | 1 |
| qb | `stress-mx-20260722-dbf935cd-w1` | released | 131.0 | 6895.0 | 149.0 | 7366.0 | 0 |
| qb | `ress-mx-20260722-dry-run-5488df58-w1` | released | 131.0 | 369.0 | 2698.0 | 7366.0 | 0 |
| qb | `60722-paper-intent-probe-93ed1edd-w1` | released | 98.0 | 0.0 | 4845.0 | 7376.0 | 1 |
| qb | `stress-mx-20260722-qb-10a0a6cc-w1` | in_progress | 7149.0 | 133.0 | 0.0 | 394.0 | 4 |
| qb | `stress-mx-20260722-qb-872e2ceb-w1` | released | None | None | None | 7280.0 | 0 |
| qb | `tress-mx-20260722-qb-a-b-ac6b4b8f-w1` | released | 4671.0 | None | 1042.0 | 7090.0 | 0 |
| qb | `tress-mx-20260722-qb-a-b-ac6b4b8f-w2` | verified | 7281.0 | 37.0 | 1040.0 | 8358.0 | 1 |
| qb | `stress-mx-20260722-qb-ab4dac4d-w1` | planned | 7319.0 | 0.0 | 3334.0 | 10653.0 | 2 |
| qb | `stress-mx-20260722-qb-ab4dac4d-w2` | planned | 7319.0 | 225.0 | 3109.0 | 10653.0 | 2 |
| qb | `stress-mx-20260722-qb-ab4dac4d-w3` | planned | 8018.0 | 10.0 | 2625.0 | 10653.0 | 1 |
| qb | `stress-mx-20260722-qb-dbe5c553-w1` | released | 98.0 | 43.0 | 208.0 | 7376.0 | 0 |
| qb | `ss-mx-20260722-qb-import-16410dce-w1` | released | 0.0 | 108.0 | 108.0 | 7387.0 | 0 |

## 4. OpenCode timings

- starts=21 dones=24
- wall_s: `{'n': 22, 'p50': 11.95, 'p95': 137.59, 'max': 209.44, 'mean': 39.2}`
- duration_s: `{'n': 0, 'p50': None, 'p95': None, 'max': None, 'mean': None}`

- **medium**: `{'n': 18, 'status': {'success': 12, 'failed': 3, 'not_found': 2, 'quarantined': 1}, 'wall_s': {'n': 16, 'p50': 11.95, 'p95': 126.62, 'max': 138.03, 'mean': 28.41}, 'duration_s': {'n': 0, 'p50': None, 'p95': None, 'max': None, 'mean': None}}`
- **small**: `{'n': 6, 'status': {'success': 4, 'quarantined': 1, 'failed': 1}, 'wall_s': {'n': 6, 'p50': 26.48, 'p95': 189.39, 'max': 209.44, 'mean': 67.98}, 'duration_s': {'n': 0, 'p50': None, 'p95': None, 'max': None, 'mean': None}}`

## 5. Host resources

```json
{
  "samples": 15,
  "ncpu": 8,
  "max_concurrent": 4,
  "load_ratio": {
    "p50": 0.3,
    "p95": 0.39399999999999985
  },
  "mem_used_pct": {
    "p50": 59.8,
    "p95": 62.48
  },
  "active_dev": {
    "avg": 0.5,
    "max": 2.0
  },
  "opencode_n": {
    "avg": 0.0,
    "max": 0.0
  },
  "verdict": "headroom",
  "reason": "load_ratio_p95=0.39<0.55 and mem_p95=62%<70% — try MAX_CONCURRENT+1 (watch same-ws mutex)",
  "path": "/Users/fan/.ccc/stats/host-resources.jsonl",
  "generated_at": "2026-07-23T00:31:41+08:00"
}
```

## 6. Epics

| app | epic | split_status | col |
|-----|------|--------------|-----|
| ccc-demo | `stress-mx-20260722-ccc-demo-72d95700` | running | backlog |
| ccc-demo | `stress-mx-20260722-ccc-demo-a-b-54f9915f` | failed | backlog |
| ccc-demo | `stress-mx-20260722-ccc-demo-d791a69a` | failed | backlog |
| qb | `stress-mx-20260722-qb-10a0a6cc` | planned | backlog |
| qb | `stress-mx-20260722-qb-a-b-ac6b4b8f` | running | backlog |
| qb | `stress-mx-20260722-qb-ab4dac4d` | planned | backlog |

## 7. Next-dev mapping

Map findings → `docs/briefs/2026-07-22-opencode-lifecycle-stall.md` A–F and efficiency brief.

- If queue_wait ≫ dev_wall → lifecycle/slot (A) + same-ws serialization
- If duration_s missing → dirty result.json (B)
- If hygiene in opencode timings → short-path (C)
- If gate_wall high / engine idle CPU 0 → testing blocks tick (D)
- Host headroom only after busy-hour samples

