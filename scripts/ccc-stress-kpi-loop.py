#!/usr/bin/env python3
"""CCC stress KPI loop — dispatch → wait → gate → (Cursor optimize) → redispatch.

State: ~/.ccc/stress-matrix/kpi-loop-state.json
Scorecard: references/stress-kpi-scorecard.json

Typical (Mac2017 measure + M1 Cursor optimize):

  python3 scripts/ccc-stress-kpi-loop.py init --apps ccc-demo,qb --max-rounds 5
  python3 scripts/ccc-stress-kpi-loop.py dispatch          # baseline + transfer
  python3 scripts/ccc-stress-kpi-loop.py arm-wake --seconds 3600
  # Cursor loop wakes → evaluate → optimize allowlist → continue|pass

  python3 scripts/ccc-stress-kpi-loop.py evaluate
  python3 scripts/ccc-stress-kpi-loop.py status
  python3 scripts/ccc-stress-kpi-loop.py continue          # next round if FAIL + budget

Autopilot policy: measure/gate/redispatch can be scripted; **code change only via Cursor**
with scorecard allowlist (see references/stress-kpi-scorecard.json autopilot).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent

import importlib.util


def _load_gate_mod():
    path = SCRIPTS / "ccc-stress-kpi-gate.py"
    spec = importlib.util.spec_from_file_location("ccc_stress_kpi_gate", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _load_gate_mod()

STATE_DIR = Path.home() / ".ccc" / "stress-matrix"
STATE_PATH = STATE_DIR / "kpi-loop-state.json"
MATRIX = SCRIPTS / "ccc-stress-matrix.py"
EFF_REPORT = SCRIPTS / "ccc-stress-efficiency-report.py"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _run_tag(round_n: int) -> str:
    day = datetime.now().strftime("%Y%m%d")
    return f"stress-mx-{day}-kpi-r{round_n}"


def load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        raise SystemExit(f"no state at {STATE_PATH}; run init first")
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_init(apps: list[str], max_rounds: int, profile: str) -> int:
    sc = GATE.load_scorecard()
    rec = int((sc.get("rounds") or {}).get("recommended") or 4)
    mx = max_rounds or int((sc.get("rounds") or {}).get("max") or 5)
    state = {
        "schema_version": "1.0",
        "loop_id": f"kpi-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "profile": profile,
        "apps": apps,
        "scorecard_id": sc.get("id"),
        "max_rounds": mx,
        "recommended_rounds": rec,
        "round": 0,
        "status": "ready",
        "current_run": None,
        "runs": [],
        "created_at": _now(),
        "policy": sc.get("autopilot") or {},
        "note": "code_change=cursor_agent_only; measure/gate/redispatch scriptable",
    }
    save_state(state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    print(f"wrote {STATE_PATH}")
    print(f"recommended_rounds={rec} max_rounds={mx}")
    return 0


def _py(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(REPO))
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def cmd_dispatch(state: dict[str, Any]) -> int:
    if state["status"] in ("passed",):
        print("already PASSED; init a new loop to restart")
        return 0
    if state["round"] >= state["max_rounds"] and state.get("current_run"):
        # allow dispatch only when advancing via continue
        pass
    nxt = int(state["round"]) + 1
    if nxt > int(state["max_rounds"]):
        state["status"] = "failed_budget"
        save_state(state)
        print(f"round budget exhausted ({state['max_rounds']})")
        return 1
    run = _run_tag(nxt)
    profile = state["profile"]
    # baseline + dispatch via matrix
    _py(
        [
            sys.executable,
            str(MATRIX),
            "--run",
            run,
            "--profile",
            profile,
            "baseline",
        ]
    )
    _py(
        [
            sys.executable,
            str(MATRIX),
            "--run",
            run,
            "--profile",
            profile,
            "dispatch",
            "--batch",
            "0",
        ]
    )
    state["round"] = nxt
    state["current_run"] = run
    state["status"] = "running"
    state["dispatched_at"] = _now()
    state["wake_due_at"] = None
    save_state(state)
    print(f"dispatched round={nxt} run={run}")
    return 0


def cmd_evaluate(state: dict[str, Any], run: str | None) -> int:
    run = run or state.get("current_run")
    if not run:
        raise SystemExit("no current_run; pass --run")
    apps = ",".join(state.get("apps") or ["ccc-demo", "qb"])
    _py(
        [
            sys.executable,
            str(EFF_REPORT),
            "--run",
            run,
            "--apps",
            apps,
        ]
    )
    eff = STATE_DIR / f"{run}-efficiency.json"
    report = json.loads(eff.read_text(encoding="utf-8"))
    sc = GATE.load_scorecard()
    result = GATE.evaluate(report, sc)
    # write gate artifacts
    jp = STATE_DIR / f"{run}-kpi-gate.json"
    mp = STATE_DIR / f"{run}-kpi-gate.md"
    jp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(GATE.render_md(result), encoding="utf-8")
    print(f"wrote {jp}")
    print(f"wrote {mp}")

    entry = {
        "round": state.get("round"),
        "run": run,
        "verdict": result["verdict"],
        "primary_fail": result.get("primary_fail"),
        "computed": result.get("computed"),
        "evaluated_at": _now(),
    }
    # upsert run history
    runs = [r for r in state.get("runs") or [] if r.get("run") != run]
    runs.append(entry)
    state["runs"] = runs
    state["last_gate"] = entry
    if result["verdict"] == "PASS":
        state["status"] = "passed"
        state["passed_at"] = _now()
    elif state.get("round", 0) >= state.get("max_rounds", 5):
        state["status"] = "failed_budget"
    else:
        state["status"] = "gate_fail"
    save_state(state)
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    if result["verdict"] == "PASS":
        return 0
    if result["verdict"] == "INVALID":
        return 2
    return 1


def cmd_continue(state: dict[str, Any]) -> int:
    """After Cursor optimize+deploy: start next dispatch if budget left."""
    if state.get("status") == "passed":
        print("PASS — nothing to continue")
        return 0
    if int(state.get("round") or 0) >= int(state.get("max_rounds") or 5):
        state["status"] = "failed_budget"
        save_state(state)
        print("failed_budget")
        return 1
    if state.get("status") not in ("gate_fail", "ready", "optimized", "running"):
        # allow from optimized
        pass
    state["status"] = "ready"
    save_state(state)
    return cmd_dispatch(state)


def cmd_status(state: dict[str, Any]) -> int:
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def wake_prompt(state: dict[str, Any], seconds: int) -> str:
    run = state.get("current_run") or "<current_run>"
    allow = (state.get("policy") or {}).get("code_change_allowlist") or []
    return (
        "CCC stress KPI loop wake。严格按 references/stress-kpi-scorecard.json。\n"
        f"1) 在 Mac2017 对 run={run} 执行: "
        f"python3 scripts/ccc-stress-kpi-loop.py evaluate\n"
        "2) 读 *-kpi-gate.json；写 docs/briefs/ 本轮对照报告（vs 上轮 runs[]）。\n"
        "3) 若 verdict=PASS：更新 state，停止 loop，摘要给人。\n"
        "4) 若 FAIL/INVALID：只改 scorecard.autopilot.code_change_allowlist 内项"
        f"（{allow}）；每轮主攻≤2 个 primary_fail；改完 py_compile+相关测，"
        "部署 2017（reset --hard origin/main 仅在已 push 后），再 "
        "python3 scripts/ccc-stress-kpi-loop.py continue 并 arm-wake 下一小时。\n"
        "5) 禁止: 加 MAX_CONCURRENT 当主药；Ollama/第二写码 CLI；invent CCC orch；"
        "未核账乱 reopen。未过门禁则 rounds 用尽前继续。\n"
        f"state={STATE_PATH} wait_was={seconds}s"
    )


def cmd_arm_wake(state: dict[str, Any], seconds: int) -> int:
    """Print a one-shot shell the Cursor agent should background with notify_on_output."""
    prompt = wake_prompt(state, seconds)
    payload = json.dumps({"prompt": prompt}, ensure_ascii=False)
    # Escape for embedding in single-quoted shell is painful; write prompt file instead
    prompt_path = STATE_DIR / "kpi-loop-wake-prompt.txt"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    sentinel = "AGENT_LOOP_WAKE_stress_kpi"
    shell = f"""sleep {int(seconds)}
echo '{sentinel} {{"prompt_file":"{prompt_path}"}}'
date '+wake_at=%Y-%m-%dT%H:%M:%S%z'
"""
    sh_path = STATE_DIR / "kpi-loop-arm-wake.sh"
    sh_path.write_text(shell, encoding="utf-8")
    state["wake_due_s"] = seconds
    state["wake_armed_at"] = _now()
    state["status"] = "waiting_wake"
    save_state(state)
    print(f"wrote {prompt_path}")
    print(f"wrote {sh_path}")
    print("--- Cursor agent: run this in background with notify_on_output ---")
    print(f"bash {sh_path}")
    print(f"notify pattern: ^{sentinel}")
    print("--- prompt preview ---")
    print(prompt[:800])
    return 0


def main() -> int:
    sc = GATE.load_scorecard()
    default_apps = sc.get("apps_default") or ["ccc-demo", "qb"]
    default_max = int((sc.get("rounds") or {}).get("max") or 5)
    wait_s = int((sc.get("snapshot") or {}).get("wait_s") or 3600)

    ap = argparse.ArgumentParser(description="CCC stress KPI loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--apps", default=",".join(default_apps))
    p_init.add_argument("--max-rounds", type=int, default=default_max)
    p_init.add_argument("--profile", default=sc.get("profile") or "efficiency_six")

    sub.add_parser("dispatch")
    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--run", default="")
    sub.add_parser("continue")
    sub.add_parser("status")
    p_wake = sub.add_parser("arm-wake")
    p_wake.add_argument("--seconds", type=int, default=wait_s)

    args = ap.parse_args()
    if args.cmd == "init":
        apps = [a.strip() for a in args.apps.split(",") if a.strip()]
        return cmd_init(apps, args.max_rounds, args.profile)

    state = load_state()
    if args.cmd == "dispatch":
        return cmd_dispatch(state)
    if args.cmd == "evaluate":
        return cmd_evaluate(state, args.run or None)
    if args.cmd == "continue":
        return cmd_continue(state)
    if args.cmd == "status":
        return cmd_status(state)
    if args.cmd == "arm-wake":
        return cmd_arm_wake(state, args.seconds)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
