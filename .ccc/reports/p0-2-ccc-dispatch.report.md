# P0-2 ccc-dispatch.py — Implementation Report

> 2026-07-06 | phase: 2 (P0-2)

## 交付

- File: `scripts/ccc-dispatch.py` (~270 lines)
- Capability inference from plan.md (keyword + marker)
- Cluster-bus client (urllib)
- Triple output: `[node_id, target, model_tier]`
- Hard-gate: human must type 'yes' on stdin (no auto-dispatch)
- Dispatch artifact: `.ccc/dispatches/dispatch-<name>.json`

## 设计原则

1. **No auto-dispatch (PoC 阶段硬要求)**
   Triple 输出后 wait for stdin 'yes'. 否则 ABORT.
2. **Lenient capability matching (PoC 阶段)**
   any-capability-overlap > 0 = eligible. 0 matches = ABORT.
   红线 18 未来加 strict [REQUIRES]...[/REQUIRES] markers
3. **Load-balanced + capability-aware**
   score = (matched/needed) - (load/200). Higher = first pick.
4. **Model tier inference** 
   opus/security/critical => opus
   flash/minimax/trivial => flash
   else => sonnet (default Executor)

## Validation (smoke 4 tests)

| Test | Setup | Result |
|------|-------|--------|
| 1: confirm yes | 2 nodes registered (m1 load=2.5, mac2017 load=1.0) | mac2017 picked (score=0.595, lower load) — PASS |
| 2: dispatch artifact exists | follow-up | `.ccc/dispatches/dispatch-v1.0-automation.plan.json` written — PASS |
| 3: confirm no | std input "no" | ABORT exit=4 (or 0 with second-bus-unreachable logic) — PASS |
| 4: cluster-bus dead | bus killed | candidates=NONE → VERDICT: ABORT exit=2 — PASS |

## Bug fix history

1. Initial: `plan_path.lower()` — PosixPath has no `.lower()`. Fixed to `plan_path.read_text(errors="ignore").lower()`.
2. Initial match: strict (matched < len(needed) => reject). Loosened to lenient (matched == 0 => reject, otherwise eligible) for v1.0 PoC.

## Borrowed

- clawmed-ai heartbeat + heartbeat callback design
- agentmesh 6 projects: capability-based routing
- red line 18 enforcement planned (not yet implemented)
