"""Failure learning loop — R1 回灌 + R2 窄版 repair（不含 Ollama/新 CLI）。

R1: FAIL 打回前写 review_fail.md；revert 后 phases 对齐；dev prompt 注入。
R2: review_fail_loops≥2 或 plan_gap 类失败 → 修订 work plan（不 epic product regen）。
R3: ≥3 → 仍由 gates quarantine（本模块不替代）。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.failure_learning")

_PLAN_GAP_MARKERS = (
    "wrong_acceptance",
    "wrong_scope",
    "plan_gap",
    "验收写错",
    "范围写错",
    "plan 缺口",
    "验收无法满足",
    "scope 不合理",
    "验收命令无效",
)


def review_fail_path(ws: Path, tid: str) -> Path:
    return Path(ws) / ".ccc" / "pids" / f"{tid}.review_fail.md"


def write_review_fail_pack(
    ws: Path,
    tid: str,
    *,
    status: str,
    verdict_text: str = "",
    review_md: str = "",
    extra: str = "",
) -> Path:
    """Persist failure pack before verdict is cleared (R1)."""
    ws = Path(ws)
    pids = ws / ".ccc" / "pids"
    pids.mkdir(parents=True, exist_ok=True)
    out = review_fail_path(ws, tid)

    findings_snip = ""
    report = ws / ".ccc" / "reports" / f"{tid}.review.md"
    body = review_md
    if not body and report.is_file():
        try:
            body = report.read_text(encoding="utf-8", errors="replace")
        except OSError:
            body = ""
    if body:
        m = re.search(r"```json\s*(\{.*?\})\s*```", body, re.DOTALL)
        if m:
            findings_snip = m.group(1)[:2500]
        else:
            findings_snip = body[-2000:]

    vtxt = verdict_text
    if not vtxt:
        vf = ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"
        if vf.is_file():
            try:
                vtxt = vf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                vtxt = ""

    category = classify_failure_category(findings_snip + "\n" + vtxt + "\n" + extra)
    text = (
        f"# review_fail {tid}\n\n"
        f"- status: {status}\n"
        f"- category: {category}\n"
        f"- ts_note: failure learning R1 pack (do not delete until next PASS)\n\n"
        f"## Verdict (truncated)\n\n```\n{(vtxt or '')[-2000:]}\n```\n\n"
        f"## Findings / review (truncated)\n\n```\n{findings_snip[-2500:]}\n```\n"
    )
    if extra.strip():
        text += f"\n## Extra\n\n```\n{extra.strip()[-1500:]}\n```\n"
    out.write_text(text, encoding="utf-8")
    _log.info("wrote review_fail pack %s category=%s", tid, category)
    return out


def read_review_fail_pack(ws: Path, tid: str, *, limit: int = 4000) -> str:
    p = review_fail_path(ws, tid)
    try:
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        pass
    return ""


def classify_failure_category(blob: str) -> str:
    low = (blob or "").lower()
    for m in _PLAN_GAP_MARKERS:
        if m.lower() in low:
            if "scope" in m.lower() or "范围" in m:
                return "wrong_scope"
            if "acceptance" in m.lower() or "验收" in m:
                return "wrong_acceptance"
            return "plan_gap"
    if "hollow" in low or "external_directory" in low:
        return "hollow"
    if "pytest" in low or "self-check" in low:
        return "test_fail"
    return "fixable"


def needs_plan_repair(
    *,
    fail_loops: int,
    fail_pack_text: str = "",
    category: str | None = None,
) -> bool:
    """R2 trigger: loops≥2 or plan_gap-class category."""
    cat = category or classify_failure_category(fail_pack_text)
    if cat in ("wrong_acceptance", "wrong_scope", "plan_gap"):
        return True
    if fail_loops >= 2:
        return True
    return False


def align_phases_after_revert(ws: Path, tid: str) -> dict[str, Any]:
    """After git revert: mark last done phase pending; clear commit; reset iter."""
    ws = Path(ws)
    pf = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    if not pf.is_file():
        return {"ok": False, "reason": "no_phases"}

    lines_out: list[str] = []
    changed = 0
    last_done_idx = -1
    phase_rows: list[tuple[int, dict]] = []

    raw_lines = pf.read_text(encoding="utf-8", errors="replace").splitlines()
    for ln in raw_lines:
        raw = ln.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            lines_out.append(ln)
            continue
        if not isinstance(obj, dict):
            lines_out.append(ln)
            continue
        if "engine_iter" in obj and "phase" not in obj:
            obj["engine_iter"] = 0
            obj.pop("unresolvable", None)
            changed += 1
            lines_out.append(json.dumps(obj, ensure_ascii=False))
            continue
        if "phase" in obj:
            phase_rows.append((len(lines_out), obj))
            lines_out.append("")  # placeholder
            continue
        lines_out.append(json.dumps(obj, ensure_ascii=False))

    for idx, (_pos, obj) in enumerate(phase_rows):
        st = str(obj.get("status") or "")
        if st in ("done", "verified") and obj.get("commit"):
            last_done_idx = idx

    for idx, (pos, obj) in enumerate(phase_rows):
        if idx == last_done_idx:
            obj = dict(obj)
            obj["status"] = "pending"
            if obj.get("commit"):
                obj["reverted_commit"] = obj.get("commit")
                obj["commit"] = ""
            changed += 1
        lines_out[pos] = json.dumps(obj, ensure_ascii=False)

    cleaned = [x for x in lines_out if x.strip()]
    pf.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
    try:
        from board.phase import _write_engine_iter

        _write_engine_iter(tid, 0)
    except Exception as exc:
        _log.debug("engine_iter reset: %s", exc)
    return {"ok": True, "changed": changed, "reset_phase_idx": last_done_idx}


def write_acceptance_fail_pack(
    ws: Path, tid: str, *, cmd: str, output: str
) -> Path:
    """Tester acceptance cmd fail → same review_fail channel for R1."""
    return write_review_fail_pack(
        ws,
        tid,
        status="ACCEPTANCE_FAIL",
        verdict_text="**Verdict:** FAIL\n\nTester acceptance command failed.\n",
        extra=f"cmd: {cmd}\n\n{output[-1500:]}",
    )


def heuristic_repair_plan(plan_text: str, fail_pack: str, *, reason: str) -> str:
    """Deterministic plan patch when LLM unavailable."""
    header = (
        f"<!-- repair_of: failure_learning R2 -->\n"
        f"<!-- repair_reason: {reason[:200]} -->\n\n"
    )
    note = (
        "## Repair notes（平台 R2 · 按失败原因修订指令）\n\n"
        "上次执行/审测失败。本轮 **按下列失败摘要调整步骤与验收**，"
        "保留原意图与可重放探针精神；禁止空转重复同一错误路径。\n\n"
        f"```\n{(fail_pack or '')[-2000:]}\n```\n\n"
    )
    body = plan_text or ""
    body = re.sub(
        r"\n## Repair notes（平台 R2[^\n]*\n.*?(?=\n## |\Z)",
        "\n",
        body,
        flags=re.DOTALL,
    )
    if "## 验收" in body or "## 验证" in body:
        if "test -f" not in body and "DRY_RUN" not in body and "py_compile" not in body:
            body = body.rstrip() + "\n- DRY_RUN=true python3 -c \"print(0)\"\n"
    else:
        body = (
            body.rstrip()
            + "\n\n## 验收\n"
            + "- DRY_RUN=true python3 -c \"print(0)\"\n"
            + "- test -d .ccc/board\n"
        )
    if body.lstrip().startswith("<!-- repair_of:"):
        body = re.sub(
            r"^<!-- repair_of:.*?-->\n<!-- repair_reason:.*?-->\n\n", "", body
        )
    return header + note + body.lstrip()


def repair_work_plan(
    ws: Path,
    tid: str,
    *,
    fail_loops: int = 0,
    use_llm: bool = False,
) -> dict[str, Any]:
    """R2: rewrite work plan.md from failure pack. Never epic product regen."""
    ws = Path(ws)
    fail_pack = read_review_fail_pack(ws, tid)
    if not fail_pack:
        return {"ok": False, "reason": "no_fail_pack"}
    cat = classify_failure_category(fail_pack)
    if not needs_plan_repair(
        fail_loops=fail_loops, fail_pack_text=fail_pack, category=cat
    ):
        return {"ok": False, "reason": "r2_not_triggered", "category": cat}

    plan_path = ws / ".ccc" / "plans" / f"{tid}.plan.md"
    old = ""
    if plan_path.is_file():
        old = plan_path.read_text(encoding="utf-8", errors="replace")

    reason = f"category={cat}; loops={fail_loops}"
    new_plan = None
    via = "heuristic"
    if use_llm:
        try:
            new_plan = _llm_repair_plan(ws, tid, old, fail_pack, reason=reason)
            if new_plan:
                via = "llm"
        except Exception as exc:
            _log.warning("llm repair failed, heuristic: %s", exc)
            new_plan = None
    if not new_plan:
        new_plan = heuristic_repair_plan(old, fail_pack, reason=reason)

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(new_plan, encoding="utf-8")

    try:
        from _board_store import FileBoardStore

        store = FileBoardStore(ws)
        store.patch_task(
            tid,
            {
                "note": f"R2 repair: {reason}",
                "repair_of": tid,
                "repair_reason": reason[:240],
            },
        )
    except Exception as exc:
        _log.debug("patch_task repair meta: %s", exc)

    return {
        "ok": True,
        "category": cat,
        "reason": reason,
        "path": str(plan_path),
        "via": via,
    }


def _llm_repair_plan(
    ws: Path, tid: str, old_plan: str, fail_pack: str, *, reason: str
) -> str | None:
    """Short Claude CLI rewrite; returns None on failure."""
    import subprocess

    from _claude_cli import resolve_claude_cli
    from _executor import _claude_env

    prompt = (
        "你是 CCC repair。根据失败摘要修订 work plan。\n"
        "规则：保留意图与可重放验收探针；修正错误步骤/scope/验收命令；"
        "输出完整 markdown plan，不要解释。\n\n"
        f"task_id: {tid}\nreason: {reason}\n\n"
        f"## 失败摘要\n{fail_pack[-3000:]}\n\n"
        f"## 原 plan\n{old_plan[:6000]}\n"
    )
    cli = resolve_claude_cli()
    env = _claude_env()
    r = subprocess.run(
        [cli, "-p", "--model", "flash"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ws),
        env=env,
    )
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None
    out = (r.stdout or "").strip()
    if len(out) < 40 or "##" not in out:
        return None
    if not out.lstrip().startswith("<!--"):
        out = (
            f"<!-- repair_of: failure_learning R2 -->\n"
            f"<!-- repair_reason: {reason[:200]} -->\n\n" + out
        )
    return out


def clear_review_fail_state(ws: Path, tid: str) -> dict[str, Any]:
    """PASS/verified 后清 failure-learning 残留，避免下轮误注入。"""
    ws = Path(ws)
    cleared: list[str] = []
    p = review_fail_path(ws, tid)
    try:
        if p.is_file():
            p.unlink()
            cleared.append(p.name)
    except OSError:
        pass
    for name in (f"{tid}.pytest_fails", f"{tid}.pytest_fail.md"):
        fp = ws / ".ccc" / "pids" / name
        try:
            if fp.is_file():
                fp.unlink()
                cleared.append(fp.name)
        except OSError:
            pass
    try:
        from _board_store import FileBoardStore

        FileBoardStore(ws).patch_task(tid, {"review_fail_loops": 0})
    except Exception:
        pass
    return {"ok": True, "cleared": cleared}
