#!/usr/bin/env python3
"""ccc-product-session.py — async product Sessionful Contract Loop runner.

Replaces `claude -p` for Engine product_async. Writes the same markers:
  <task>.product.out / .product.err / exit via process code
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="CCC product sessionful contract loop")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--mode", choices=("work", "epic"), default="work")
    ap.add_argument("--model", default="flash")
    ap.add_argument("--out-file", required=True)
    ap.add_argument("--err-file", default="")
    args = ap.parse_args()

    workspace = Path(args.workspace).resolve()
    prompt = Path(args.prompt_file).read_text(encoding="utf-8", errors="replace")
    out_path = Path(args.out_file)
    err_path = Path(args.err_file) if args.err_file else out_path.with_suffix(".err")

    import phase_lint
    from _product_session import (
        format_work_artifacts,
        parse_work_artifacts,
        run_contract_loop_sync,
    )

    def validate_work(text: str) -> None:
        parse_work_artifacts(text)

    def gate_work(text: str):
        plan, phases = parse_work_artifacts(text)
        ok, errs, _warns = phase_lint.validate_phases_dict(phases)
        if not ok:
            raise RuntimeError(f"phase_lint failed: {'; '.join(errs)}")
        dep_ok, dep_errs = phase_lint.suggest_fix_no_missing_dependencies(phases)
        if not dep_ok:
            raise RuntimeError(f"phase_lint orphan-dep: {'; '.join(dep_errs)}")
        cyc_ok, cyc_errs = phase_lint.validate_no_cycle_dependencies(phases)
        if not cyc_ok:
            raise RuntimeError(f"phase_lint cycle: {'; '.join(cyc_errs)}")
        plan = phase_lint.normalize_plan_acceptance_headers(plan)
        plan_ok, plan_errs = phase_lint.validate_plan_acceptance(plan)
        if not plan_ok:
            raise RuntimeError(f"plan_lint failed: {'; '.join(plan_errs)}")
        return format_work_artifacts(plan, phases), (plan, phases)

    def validate_epic(text: str) -> None:
        from _product_fanout import parse_fanout_output

        parse_fanout_output(text)

    def gate_epic(text: str):
        from _product_fanout import parse_fanout_output

        brief, children = parse_fanout_output(text)
        # Soft re-emit: keep original text if parse works; prefer CHILDREN block intact
        return text, (brief, children)

    if args.mode == "epic":
        result = run_contract_loop_sync(
            prompt=prompt,
            workspace=workspace,
            task_id=args.task_id,
            mode="epic",
            model=args.model,
            validate_fn=validate_epic,
            gate_fn=gate_epic,
        )
    else:
        result = run_contract_loop_sync(
            prompt=prompt,
            workspace=workspace,
            task_id=args.task_id,
            mode="work",
            model=args.model,
            validate_fn=validate_work,
            gate_fn=gate_work,
        )

    meta = {
        "ok": result.get("ok"),
        "loops": result.get("loops"),
        "claude_session_id": result.get("claude_session_id"),
        "error": result.get("error"),
    }
    out_path.write_text(result.get("output") or "", encoding="utf-8")
    err_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # Also append a machine trailer so finalize can see session meta
    if result.get("ok") and result.get("output"):
        trailer = (
            f"\n\n<!-- ccc-product-session "
            f"loops={result.get('loops')} "
            f"sid={result.get('claude_session_id') or ''} -->\n"
        )
        out_path.write_text(
            (result.get("output") or "") + trailer, encoding="utf-8"
        )
        return 0

    # Failed: still write raw output for fallback inspection
    if result.get("output") and not out_path.read_text(encoding="utf-8").strip():
        out_path.write_text(result.get("output") or "", encoding="utf-8")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
