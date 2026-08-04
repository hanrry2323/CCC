# P2-2 cluster-doctor.sh — Implementation Report

> 2026-07-06 | phase: 6 (P2-2)

## 交付

- File: `tools/cluster-doctor.sh` (~95 lines)
- 5-section diagnostic output
- 4 exit codes (0/1/2/3 — healthy/unreachable/empty/stale)

## Output Sections

[1/5] bus liveness  — OK or FAIL
[2/5] node list     — registered nodes
[3/5] heartbeat freshness (< 90s = healthy)
[4/5] capability matrix  — node × capability table
[5/5] verdict       — colored summary + exit code

## Validation (2/2 smoke)

| Test | Setup | Exit | Output |
|------|-------|------|--------|
| 1: healthy | 2 nodes registered (m1, feiniu) | 0 | OK + matrix 4 caps visible |
| 2: bus down | kill BUS_PID | 1 | "FAIL bus unreachable at ..." |

## Exit Code Semantics

- 0 = healthy (all nodes fresh, ≥1 active)
- 1 = bus unreachable (curl fails)
- 2 = no active nodes (cluster offline)
- 3 = some nodes stale (heartbeat > 90s but bus alive)

## v3 Portability Compliance

- Uses $BUS_URL double-quoted (Lesson 29 compliant)
- Set -euo pipefail on
- No bash -c single-quote nesting
- Uses heredoc with python3 for inline JSON parsing
