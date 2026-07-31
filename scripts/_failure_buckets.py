"""Failure reason buckets for post-exhaust epic optimize + board repair.

Field-backed (Mac2017 2026-07-30): acceptance-gate hyphen, empty_bullets,
dirty_block Author:, reviewer 未产出 verdict, product async timeout, hang 耗尽.
"""

from __future__ import annotations

from typing import Any


def classify_failure_bucket(reason: str) -> str:
    """Map abnormal/failure note → bucket for Agent optimize SOP."""
    text = reason or ""
    low = text.lower()

    # Specific buckets first (order matters)
    if "dirty_block" in low or "ccc_hygiene" in low:
        return "dirty_block"
    if (
        "未产出 verdict" in text
        or "reviewer_bg_timeout" in low
        or "verdict:** timeout" in low
        or "**verdict:** timeout" in low
    ):
        return "reviewer_timeout"
    if "product async timeout" in low or (
        "product_fail" in low and "timeout" in low
    ):
        return "product_timeout"
    if "hang_detected" in low or "hang auto-restart" in low or "hang " in low:
        return "hang"
    if (
        "short_path" in low
        or "acceptance_cmd_failed" in low
        or "acceptance_empty" in low
        or "acceptance_uncommitted" in low
        or "acceptance_gate" in low
        or "acceptance-gate" in low
        or "acceptance:" in low
    ):
        return "acceptance_fail"
    if (
        "unresolvable" in low
        or "phase graph" in low
        or "plan_lint" in low
        or "plan acceptance" in low
    ):
        return "phase_unresolvable"
    if "fail_loop_exhausted" in low or "重试耗尽" in text or "次全部失败" in text:
        return "fail_loop_exhausted"
    if "滞留" in text or "stale" in low:
        return "stale_inflight"
    if "timeout" in low or "timed out" in low:
        return "timeout"
    return "other"


def is_exhaust_reason(reason: str) -> bool:
    """True when Engine same-card refeed should stop and Agent should reformulate epic.

    Align with ``engine.failure_router.should_auto_refeed`` exhaust keywords —
    NOT every hang/acceptance_fail hit. First-time acceptance / TIMEOUT / product
    timeout stay recoverable for board_repair reopen.
    """
    text = reason or ""
    low = text.lower()
    markers = (
        "hang auto-restart 耗尽",
        "short_path_fail_budget",
        "acceptance_fail_budget",
        "reviewer_fail_loop_exhausted",
        "tester_fail_loop_exhausted",
        "fail_loop_exhausted",
        "retry budget 耗尽",
        "max_retry",
        "重试耗尽",
        "次全部失败",
        "phase graph unresolvable",
        "unresolvable",
        "plan_lint",
        "missing plan",
        "缺 plan",
        "缺 phases",
        "滞留",
        "stale_inflight",
    )
    return any(m.lower() in low or m in text for m in markers)


def bucket_optimize_hints(bucket: str) -> str:
    """Hard constraints for Agent new-epic transfer (zh)."""
    if bucket == "hang":
        return (
            "hang：新 epic 必须更小——优先 1 张 work、scope≤少数文件、单 phase；"
            "acceptance 仅短 pytest/python3 探针；禁 Step1–6 一次做完；complexity 诚实。"
        )
    if bucket == "acceptance_fail":
        return (
            "acceptance_fail：先修可重放探针（禁空 bullets / existence-only）；"
            "acceptance 与 scope 同向；skill_ref 与验收匹配；禁散文假绿；"
            "认 ### 验收 与 acceptance-gate 同权威。"
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
    if bucket == "dirty_block":
        return (
            "dirty_block：多为卫生/噪音（Author: 空文件、docs/reports、.ccc/lessons）非意图失败；"
            "先认噪音门禁再同卡 reopen；禁止当业务失败改意图；禁卫生 epic 主业；禁 invent。"
        )
    if bucket == "reviewer_timeout":
        return (
            "reviewer_timeout：瞬态审测未出 verdict/TIMEOUT——优先同卡 reopen 或短路径确定性审；"
            "勿抬预算；反复超时再缩小卡面；禁 invent。"
        )
    if bucket == "product_timeout":
        return (
            "product_timeout：扇出/product 异步超时——缩小 epic、单 work、明确 CHILDREN；"
            "禁巨型扇出；禁 invent。"
        )
    if bucket == "timeout":
        return (
            "timeout：先当瞬态 reopen；反复出现则缩小卡面与验收；禁 invent。"
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
