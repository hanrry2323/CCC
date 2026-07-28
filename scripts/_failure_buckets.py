"""Failure reason buckets for post-exhaust epic optimize + board repair."""

from __future__ import annotations

from typing import Any


def classify_failure_bucket(reason: str) -> str:
    """Map abnormal/failure note → bucket for Agent optimize SOP."""
    low = (reason or "").lower()
    if "hang_detected" in low or "hang auto-restart" in low or "hang " in low:
        return "hang"
    if (
        "short_path" in low
        or "acceptance_cmd_failed" in low
        or "acceptance:" in low
        or "acceptance_gate" in low
    ):
        return "acceptance_fail"
    if (
        "unresolvable" in low
        or "phase graph" in low
        or "plan_lint" in low
        or "plan acceptance" in low
    ):
        return "phase_unresolvable"
    if "fail_loop_exhausted" in low or "重试耗尽" in low or "次全部失败" in low:
        return "fail_loop_exhausted"
    if "timeout" in low or "timed out" in low:
        return "timeout"
    if "滞留" in (reason or "") or "stale" in low:
        return "stale_inflight"
    return "other"


def is_exhaust_reason(reason: str) -> bool:
    """True when Engine same-card refeed should stop and Agent should reformulate epic."""
    low = (reason or "").lower()
    bucket = classify_failure_bucket(reason)
    if bucket in (
        "hang",
        "acceptance_fail",
        "phase_unresolvable",
        "fail_loop_exhausted",
        "stale_inflight",
    ):
        return True
    markers = (
        "hang auto-restart 耗尽",
        "short_path_fail_budget",
        "reviewer_fail_loop_exhausted",
        "tester_fail_loop_exhausted",
        "fail_loop_exhausted",
        "retry budget 耗尽",
        "max_retry",
    )
    return any(m.lower() in low for m in markers)


def bucket_optimize_hints(bucket: str) -> str:
    """Hard constraints for Agent new-epic transfer (zh)."""
    if bucket == "hang":
        return (
            "hang：新 epic 必须更小——优先 1 张 work、scope≤少数文件、单 phase；"
            "acceptance 仅短 pytest/python3 探针；禁 Step1–6 一次做完；complexity 诚实。"
        )
    if bucket == "acceptance_fail":
        return (
            "acceptance_fail：先修可重放探针，acceptance 与 scope 同向；"
            "executor_intent 与验收匹配；禁散文假绿。"
        )
    if bucket == "phase_unresolvable":
        return (
            "phase_unresolvable：重写可执行 phases/DAG；单卡单 phase 优先；"
            "禁止依赖 product regen 修子卡。"
        )
    if bucket == "fail_loop_exhausted":
        return (
            "fail_loop_exhausted：改 plan/验收拆法，勿原样重下；"
            "读 review_fail 与 verdict 后再定稿。"
        )
    if bucket == "stale_inflight":
        return (
            "stale_inflight：缩小卡面、优先短路径；避免长 OpenCode 空转。"
        )
    return "other：读 quarantine 证据后改任务拆解；意图对齐原 goal；禁 invent。"


def summarize_exhausted_tasks(
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build exhausted[] rows from abnormal task dicts."""
    out: list[dict[str, Any]] = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "").strip()
        if not tid:
            continue
        reason = str(t.get("note") or t.get("abnormal_reason") or "")
        if not is_exhaust_reason(reason) and str(t.get("status") or "") != "abnormal":
            # still classify if caller already filtered to abnormal
            pass
        bucket = classify_failure_bucket(reason)
        out.append(
            {
                "id": tid,
                "reason_bucket": bucket,
                "reason_head": reason[:200],
                "hint": bucket_optimize_hints(bucket),
            }
        )
    return out
