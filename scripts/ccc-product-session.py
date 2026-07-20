#!/usr/bin/env python3
"""ccc-product-session.py — async product Sessionful Contract Loop runner.

Replaces `claude -p` for Engine product_async. Writes markers:
  <task>.product.out / .product.err / .product.done / .product.exitcode
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


def _marker_stem(out_path: Path, task_id: str) -> Path:
    """Prefer sibling of out-file; fall back to out parent / task_id."""
    name = out_path.name
    if name.endswith(".product.out"):
        return out_path.with_name(name[: -len(".out")])
    return out_path.parent / f"{task_id}.product"


def _write_completion_markers(stem: Path, exit_code: int, *, ok: bool) -> None:
    """stem like ``.../tid.product`` → writes ``.done`` and ``.exitcode``."""
    try:
        stem.with_suffix(stem.suffix + ".exitcode").write_text(
            str(int(exit_code)), encoding="utf-8"
        )
    except OSError:
        try:
            Path(str(stem) + ".exitcode").write_text(
                str(int(exit_code)), encoding="utf-8"
            )
        except OSError:
            pass
    done_path = Path(str(stem) + ".done")
    try:
        done_path.write_text("ok\n" if ok else "fail\n", encoding="utf-8")
    except OSError:
        pass


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
    stem = _marker_stem(out_path, args.task_id)
    exit_code = 2
    ok = False

    try:
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
            ok_ph, errs, _warns = phase_lint.validate_phases_dict(phases)
            if not ok_ph:
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
        if result.get("ok") and result.get("output"):
            trailer = (
                f"\n\n<!-- ccc-product-session "
                f"loops={result.get('loops')} "
                f"sid={result.get('claude_session_id') or ''} -->\n"
            )
            out_path.write_text(
                (result.get("output") or "") + trailer, encoding="utf-8"
            )
            ok = True
            exit_code = 0
        else:
            if result.get("output") and not out_path.read_text(encoding="utf-8").strip():
                out_path.write_text(result.get("output") or "", encoding="utf-8")
            exit_code = 2
    except Exception as exc:
        try:
            err_path.write_text(
                json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        exit_code = 2
        ok = False
    finally:
        _write_completion_markers(stem, exit_code, ok=ok)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
