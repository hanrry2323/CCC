"""M1 repair-queue：编排异常自动 SOP 入队；Desktop/sidecar 冲刷注入 Agent。

kind:
  - board_repair — 可恢复 reopen / 清板
  - epic_optimize — 耗尽后改大卡再开（L3b）
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

KIND_BOARD_REPAIR = "board_repair"
KIND_EPIC_OPTIMIZE = "epic_optimize"
VALID_KINDS = frozenset({KIND_BOARD_REPAIR, KIND_EPIC_OPTIMIZE})

# Desktop/Hub 用 qxo；仓目录/Engine folder 常写 qx-observer — claim 须互通
_PROJECT_ALIASES: dict[str, frozenset[str]] = {
    "qxo": frozenset({"qxo", "qx-observer"}),
    "qx-observer": frozenset({"qxo", "qx-observer"}),
}


def canonical_project_id(project_id: str) -> str:
    """Normalize folder aliases to Desktop project_id (qx-observer → qxo)."""
    pid = (project_id or "").strip()
    if pid == "qx-observer":
        return "qxo"
    return pid


def project_id_match_set(project_id: str) -> frozenset[str]:
    pid = (project_id or "").strip()
    if not pid:
        return frozenset()
    return _PROJECT_ALIASES.get(pid, frozenset({pid}))


def queue_path() -> Path:
    raw = os.environ.get("CCC_REPAIR_QUEUE", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".ccc" / "repair-queue.jsonl"


def enqueue(
    *,
    project_id: str,
    epic_id: str,
    hint: str,
    thread_id: str = "",
    prompt: str = "",
    kind: str = KIND_BOARD_REPAIR,
    buckets: str = "",
) -> dict[str, Any]:
    """同一 project|epic|kind 去重：已有 pending 则跳过。"""
    pid = canonical_project_id(project_id)
    eid = (epic_id or "").strip()
    k = (kind or KIND_BOARD_REPAIR).strip() or KIND_BOARD_REPAIR
    if k not in VALID_KINDS:
        k = KIND_BOARD_REPAIR
    key = f"{pid}|{eid}|{k}"
    path = queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_pending()
    match_ids = project_id_match_set(pid)
    if any(
        str(x.get("project_id") or "") in match_ids
        and str(x.get("epic_id") or "") == eid
        and (x.get("kind") or KIND_BOARD_REPAIR) == k
        for x in existing
    ):
        return {"ok": True, "deduped": True, "key": key, "kind": k}
    if not prompt:
        if k == KIND_EPIC_OPTIMIZE:
            prompt = optimize_sop_prompt(
                project_id=pid, epic_id=eid, hint=hint, buckets=buckets
            )
        else:
            prompt = sop_prompt(project_id=pid, epic_id=eid, hint=hint)
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "status": "pending",
        "kind": k,
        "project_id": pid,
        "epic_id": eid,
        "thread_id": (thread_id or "").strip(),
        "hint": (hint or "")[:400],
        "buckets": (buckets or "")[:200],
        "prompt": (prompt or "")[:4500],
        "key": key,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "deduped": False, "key": key, "kind": k}


def enqueue_epic_optimize(
    *,
    project_id: str,
    epic_id: str,
    hint: str,
    thread_id: str = "",
    buckets: str = "",
) -> dict[str, Any]:
    return enqueue(
        project_id=project_id,
        epic_id=epic_id,
        hint=hint,
        thread_id=thread_id,
        kind=KIND_EPIC_OPTIMIZE,
        buckets=buckets,
    )


def load_pending() -> list[dict[str, Any]]:
    path = queue_path()
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and (row.get("status") or "pending") == "pending":
                out.append(row)
    except OSError:
        return []
    return out


def mark_status(key: str, status: str) -> None:
    """Update row status: pending | injected | done."""
    want = (status or "").strip() or "done"
    if want not in ("pending", "injected", "done"):
        want = "done"
    path = queue_path()
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    new_lines: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
        except json.JSONDecodeError:
            new_lines.append(ln)
            continue
        if isinstance(row, dict) and row.get("key") == key:
            row["status"] = want
            ts_key = "done_ts" if want == "done" else "injected_ts" if want == "injected" else "pending_ts"
            row[ts_key] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
            new_lines.append(json.dumps(row, ensure_ascii=False))
        else:
            new_lines.append(ln)
    try:
        path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
    except OSError as exc:
        import logging
        logging.getLogger("ccc.repair_queue").warning(
            "repair-queue rewrite failed: %s", exc
        )


def mark_done(key: str) -> None:
    mark_status(key, "done")


def pending_for_project(project_id: str, *, limit: int = 8) -> list[dict[str, Any]]:
    pid = canonical_project_id(project_id)
    if not pid:
        return []
    match_ids = project_id_match_set(pid)
    out = [x for x in load_pending() if str(x.get("project_id") or "") in match_ids]
    return out[: max(1, min(int(limit or 8), 20))]


def claim_for_inject(
    *,
    project_id: str,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """Claim pending repair items for sidecar/Agent inject; mark injected.

    Engine enqueues on Mac2017 ``~/.ccc/repair-queue.jsonl``; Hub serves claim
    so M1 sidecar (via tunnel) can inject L3b SOP. Does not invent / does not
    write backlog. ``qxo`` ↔ ``qx-observer`` alias so Desktop claim hits Engine rows.
    """
    pid = canonical_project_id(project_id)
    if not pid:
        return []
    n = max(1, min(int(limit or 1), 5))
    claimed: list[dict[str, Any]] = []
    for row in pending_for_project(pid, limit=n):
        key = str(row.get("key") or "")
        if not key:
            # legacy row may use folder name in key; rebuild from fields
            old_pid = str(row.get("project_id") or "")
            eid = str(row.get("epic_id") or "")
            k = str(row.get("kind") or KIND_BOARD_REPAIR)
            key = f"{old_pid}|{eid}|{k}" if old_pid and eid else ""
        if not key:
            continue
        mark_status(key, "injected")
        # surface canonical id to Agent inject block
        row = dict(row)
        row["project_id"] = pid
        claimed.append(row)
        if len(claimed) >= n:
            break
    return claimed


def format_inject_block(items: list[dict[str, Any]]) -> str:
    """Sidecar prompt block: force failure_pack → optimize chain → auto transfer."""
    if not items:
        return ""
    lines = [
        "【编排自愈 L3b · repair-queue 强制 · 勿问老板】",
        "清障 ≠ 解决问题。禁止只藏卡/只 reopen 当结案；禁止等人点「转意图卡」；禁止 invent。",
    ]
    for row in items[:5]:
        kind = str(row.get("kind") or KIND_BOARD_REPAIR)
        pid = str(row.get("project_id") or "")
        eid = str(row.get("epic_id") or "")
        buckets = str(row.get("buckets") or "")
        hint = str(row.get("hint") or "")[:200]
        lines.append(f"- kind={kind} project={pid} epic={eid} buckets={buckets}")
        lines.append(f"  摘要：{hint}")
        if kind == KIND_EPIC_OPTIMIZE:
            lines.append(
                "  必做：hub_repair(failure_pack) → 已绿结算否则 clear_blockers → "
                "按 optimize_hint 出优化意图链 ccc-transfer **并自动投链**（gate 绿进代办）。"
            )
        else:
            lines.append(
                "  必做：hub_repair(status) → 可恢复 reopen → clear 不可恢复 → "
                "exhausted 则 failure_pack + 优化意图链并自动投链。"
            )
        prompt = str(row.get("prompt") or "").strip()
        if prompt:
            lines.append("  SOP：")
            for pl in prompt.splitlines()[:12]:
                lines.append(f"  {pl}")
    lines.append("禁止甩锅复制给对话；修板后必须再投链或结算已绿。")
    return "\n".join(lines)


def optimize_sop_prompt(
    *,
    project_id: str,
    epic_id: str,
    hint: str,
    buckets: str = "",
) -> str:
    return (
        "【耗尽改大卡 · 自动 SOP · 勿问老板 · 定卡培养】\n"
        f"项目：{project_id}\n"
        f"失败大卡：{epic_id}\n"
        f"摘要：{hint}\n"
        f"失败桶：{buckets or '见 hub_repair failure_pack'}\n"
        "请严格按 references/abnormal-solve-sop.md + post-exhaust-epic-optimize-sop.md：\n"
        "1) hub_repair(failure_pack) — 读每条 exhausted 的 optimize_hint + prior_transfer\n"
        "2) 已绿则结算；否则 clear_blockers 归档旧卡\n"
        "3) **按 optimize_hint 改出优化意图链 ccc-transfer（可多卡）并自动投链**"
        "（title/goal 对齐原意图；缩小/修探针；gate 绿即进代办）\n"
        "禁止等人点「转意图卡」；禁止原样重下；禁止只藏卡结束；"
        "禁止 invent；禁止抬 Engine 重试；禁止写业务源码。\n"
        "dirty/commit：references/commit-folder-hygiene-sop.md。\n"
    )


def sop_prompt(*, project_id: str, epic_id: str, hint: str) -> str:
    return (
        "【编排自愈 · 自动 SOP · 勿问老板】\n"
        f"项目：{project_id}\n"
        f"大卡：{epic_id}\n"
        f"摘要：{hint}\n"
        "请严格按 references/abnormal-solve-sop.md + board-auto-repair-sop.md：\n"
        "取证定桶 → 已绿则结算；否则可恢复 reopen → clear_blockers（只归档不可恢复）"
        "→ exhausted 则 hub_repair(failure_pack) 按 optimize_hint **优化意图链并自动投链**。\n"
        "dirty_block/脏树：references/commit-folder-hygiene-sop.md（ccc_hygiene≠业务失败；禁 git add -A）。\n"
        "禁止只藏卡/只 reopen 当结案；禁止等人点按钮；禁止甩锅让老板复制/去运维页；"
        "禁止 invent；禁止写业务源码。\n"
    )
