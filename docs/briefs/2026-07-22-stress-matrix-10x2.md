# Stress matrix findings — stress-mx-20260722

Dual-app 10-scenario run on `ccc-demo` + `qb` (20 transfers). Harness:
`scripts/ccc-stress-matrix.py`. Results JSON/MD: `~/.ccc/stress-matrix/`.

## Dispatch

All 20 dispatches OK (18 HTTP 200 + 2× `missing_intent_probe` 400 as designed).

## Scenario outcomes (orchestration proofs)

| # | Scenario | Proven? | Notes |
|---|----------|---------|-------|
| 1 | Single-phase success | Yes (qb released; demo had FAIL→planned retry) | OpenCode path works |
| 2 | 3-phase fanout | Yes (demo w1 released, w2/w3 dependency waits) | `depends_on_tasks` honored |
| 3 | Review FAIL → planned retry | Yes | Logs: `触发回滚（先于 tester）` + `testing → planned` |
| 4 | Paper `script_seed` | Partial | demo eventually released; qb flapped FAIL/abnormal (reviewer LLM) |
| 5 | Feature probe ≠ script_seed | Yes | `should_use_script_seed=False` for feature probe titles |
| 6 | Hygiene / board_ops | Yes (both apps released after `test -d` fix) | Was blocked by `test -f .ccc/board` |
| 7 | Missing probe gate | Yes | 400 `missing_intent_probe` (retested) |
| 8 | Dependency chain | Yes | Engine logs wait until prior released |
| 9 | Abnormal reopen | Yes | intentional quarantine → `reopen_task` → planned |
| 10 | Path-constrained probe | Partial | queued behind OpenCode serialization |

## Bugs found and fixed (platform)

1. **FAIL verdict treated as ok before tester** → tester could race to verified → kb released while FAIL pending. Fixed in `scripts/engine/gates.py` (FAIL handled before tester; tester skips verified on FAIL).
2. **Unsafe git revert** of unrelated commits. Fixed: ancestor + message must mention task id.
3. **tester `shlex.split(DRY_RUN=true …)`** → `Errno 2`. Fixed: `shell=True`.
4. **Fanout `test -f` on directories** (`.ccc/board`). Fixed: `test -d` for dir scopes.
5. **Zombie OpenCode** (hours/days) blocked same-ws launches. Added `kill_orphan_opencode` in `scripts/engine/hang.py`.

## Residual risks

- Reviewer LLM JSON parse → FALLBACK quarantine (feature probe / paper) — intermittent upstream.
- Multi-copy board files (same tid in two columns) under recover races — dedupe manually once.
- Dumping 20 medium OpenCode cards at once saturates slots; prefer batches of 2–4.
- kb sometimes lagged on verified (nudged manually during run).

## Commands

```bash
python3 scripts/ccc-stress-matrix.py dispatch --batch 1  # s01-s04 × 2 apps
python3 scripts/ccc-stress-matrix.py watch --timeout 2400
python3 scripts/ccc-stress-matrix.py report
python3 scripts/ccc-stress-matrix.py reopen-s09
```
