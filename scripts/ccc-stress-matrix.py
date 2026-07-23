#!/usr/bin/env python3
"""Dual-app Engine stress matrix (ccc-demo + qb).

Profiles:
  efficiency_v2 — 每仓 8 张有价值场景（默认；明日效率回顾）
  legacy10      — 历史 10 场景（含故意 FAIL / reopen）

Usage (Mac2017):
  python3 scripts/ccc-stress-matrix.py --profile efficiency_v2 baseline
  python3 scripts/ccc-stress-matrix.py --profile efficiency_v2 dispatch --batch 0
  python3 scripts/ccc-stress-matrix.py --profile efficiency_v2 watch --timeout 7200
  python3 scripts/ccc-stress-efficiency-report.py --run stress-mx-20260723
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HUB = "http://127.0.0.1:7777"
AUTH = base64.b64encode(b"ccc:ccc").decode()
APPS = ("ccc-demo", "qb")
# Defaults overridden by --run / --profile in main()
RUN_TAG = "stress-mx-20260722"
PROFILE = "legacy10"
RESULTS = Path.home() / ".ccc" / "stress-matrix" / f"{RUN_TAG}.json"


def _set_run(run: str, profile: str) -> None:
    global RUN_TAG, PROFILE, RESULTS
    RUN_TAG = run
    PROFILE = profile
    RESULTS = Path.home() / ".ccc" / "stress-matrix" / f"{RUN_TAG}.json"
    RESULTS.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Scenario:
    sid: str
    name: str
    kind: str  # transfer | gate_reject | post
    title: str
    goal: str
    acceptance: list[str]
    plan_md: str
    pipeline: str = "dev"
    executor_intent: str = "opencode"
    complexity: str = "small"
    expect_http: int = 200
    expect_error: str | None = None
    notes: str = ""


def _slug(app: str, sid: str) -> str:
    return f"{RUN_TAG}-{app}-{sid}"


def scenarios_for(app: str) -> list[Scenario]:
    """Dispatch scenarios for current PROFILE."""
    if PROFILE == "efficiency_six":
        # e05 看板卫生已剔除：板面卫生归 Cursor/Desktop，不靠 Engine 卫生 epic
        want = {"e01", "e02", "e03", "e04", "e08"}
        return [s for s in scenarios_efficiency_v2(app, stem_prefix="eff23r2") if s.sid in want]
    if PROFILE == "efficiency_v2":
        return scenarios_efficiency_v2(app)
    return scenarios_legacy10(app)


def scenarios_efficiency_v2(app: str, *, stem_prefix: str = "eff23") -> list[Scenario]:
    """有价值场景集。stem_prefix 区分压测批次产物路径。"""
    stem = f"{stem_prefix}_{app.replace('-', '_')}"
    probe = f"scripts/{stem}_feature_probe.py"
    # script_seed 固定写入 scripts/paper_intent_probe.py（勿用 stem 变体路径）
    paper = "scripts/paper_intent_probe.py"
    mod = f"scripts/{stem}_mod.py"
    suite_mod = f"scripts/{stem}_suite_mod.py"
    doc = f"docs/{stem.upper()}_NOTE.md"
    util_a = f"scripts/{stem}_util_a.py"
    util_b = f"scripts/{stem}_util_b.py"

    value_note = (
        "ccc-demo 验证产线路径；qb 留下可复用探针/小模块（非一次性垃圾名）。"
        if app == "qb"
        else "平台路径验收：短路径硬门 + 扇出 + 同仓串行。"
    )

    return [
        Scenario(
            sid="e01",
            name="小模块成功闭环",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 小模块 hello",
            goal=f"落地 {mod}：hello()→'ok'；{value_note}",
            acceptance=[
                f"test -f {mod}",
                f'DRY_RUN=true python3 -c "from pathlib import Path; assert Path(\'{mod}\').is_file()"',
            ],
            plan_md=(
                f"# Plan\n\n## 目标\n写 `{mod}`：`def hello(): return 'ok'`\n\n"
                f"## Phase 1 — module\n- `{mod}`\n\n"
                f"## 验收\n- test -f {mod}\n"
                f"- DRY_RUN=true python3 -c \"print(0)\"\n"
            ),
            complexity="small",
            notes="P1 queue+release; path=opencode",
        ),
        Scenario(
            sid="e02",
            name="依赖链 A→B",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} util A后B",
            goal=f"两 phase：先 {util_a} 再 {util_b}",
            acceptance=[
                f"test -f {util_a}",
                f"test -f {util_b}",
                'DRY_RUN=true python3 -c "print(0)"',
            ],
            plan_md=(
                f"# Plan\n\n## Phase 1 — A\n- `{util_a}` 含 `def a(): return 1`\n\n"
                f"## Phase 2 — B\n- `{util_b}` 含 `def b(): return 2`（依赖 A 已存在）\n\n"
                f"## 验收\n- test -f {util_a}\n- test -f {util_b}\n"
                f"- DRY_RUN=true python3 -c \"print(0)\"\n"
            ),
            complexity="medium",
            notes="P1 same-ws serial; no ghost slot",
        ),
        Scenario(
            sid="e03",
            name="纸面探针 script_seed",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} paper_intent_probe",
            goal=f"机械落地 {paper}，必须 script_seed 不进 OpenCode",
            acceptance=[
                f"test -f {paper}",
                f"DRY_RUN=true python3 {paper}",
            ],
            plan_md=(
                f"# Plan\n\n## 目标\nseed `{paper}`（paper_intent_probe）\n\n"
                f"## Phase 1\n- `{paper}`\n\n"
                f"## 验收\n- test -f {paper}\n- DRY_RUN=true python3 {paper}\n"
            ),
            executor_intent="python",
            complexity="small",
            notes="P5 path=script_seed",
        ),
        Scenario(
            sid="e04",
            name="功能探针禁劫持",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} feature DRY_RUN 探针",
            goal=f"写 {probe}，禁止写成 paper_intent_probe（feature_seed 确定性）",
            acceptance=[
                f"test -f {probe}",
                f"DRY_RUN=true python3 {probe}",
            ],
            plan_md=(
                f"# Plan\n\n## Phase 1 — feature probe\n- `{probe}`\n"
                f"禁止写 paper_intent_probe.py；须 DRY_RUN 可跑\n\n"
                f"## 验收\n- test -f {probe}\n- DRY_RUN=true python3 {probe}\n"
            ),
            executor_intent="python",
            complexity="small",
            notes="P5 path=feature_seed (deterministic; ban paper hijack)",
        ),
        Scenario(
            sid="e05",
            name="看板卫生短路径",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 看板卫生",
            goal="仅确认 .ccc/board 卫生可达，不改业务码",
            acceptance=["test -d .ccc/board"],
            plan_md=(
                "# Plan\n\n## 目标\n看板卫生\n\n"
                "## Phase 1\n- `.ccc/board`\n\n"
                "## 验收\n- test -d .ccc/board\n"
            ),
            pipeline="ops",
            executor_intent="python",
            complexity="small",
            notes="P5 path=board_ops|python",
        ),
        Scenario(
            sid="e06",
            name="缺探针拒单",
            kind="gate_reject",
            title=f"[{RUN_TAG}] {app} 无探针应拒",
            goal="故意不写可重放探针，验证 Hub Gate",
            acceptance=["写一个说明文档即可"],
            plan_md="# Plan\n\n## 目标\n无命令验收\n\n## 验收\n- 文档写好即可\n",
            expect_http=400,
            expect_error="missing_intent_probe",
            complexity="small",
            notes="gate only; no board card",
        ),
        Scenario(
            sid="e07",
            name="模块+文档双 phase",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 模块与说明",
            goal=f"扇出两张 work：{suite_mod} + {doc}",
            acceptance=[
                f"test -f {suite_mod}",
                f"test -f {doc}",
                'DRY_RUN=true python3 -c "print(0)"',
            ],
            plan_md=(
                f"# Plan\n\n## 目标\n模块+文档（与 e01 产物隔离）\n\n"
                f"## Phase 1 — 模块\n- `{suite_mod}`\n\n"
                f"## Phase 2 — 文档\n- `{doc}` 说明 hello API\n\n"
                f"## 验收\n- test -f {suite_mod}\n- test -f {doc}\n"
                f"- DRY_RUN=true python3 -c \"print(0)\"\n"
            ),
            complexity="medium",
            notes="medium fanout without 3-phase overload",
        ),
        Scenario(
            sid="e08",
            name="纸面路径复验",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 纸面探针复验",
            goal=f"再次确认 {paper} 短路径可重放",
            acceptance=[
                f"test -f {paper}",
                f"DRY_RUN=true python3 {paper}",
            ],
            plan_md=(
                f"# Plan\n\n## 目标\n`{paper}` 可重放\n\n"
                f"## Phase 1\n- `{paper}`\n\n"
                f"## 验收\n- test -f {paper}\n- DRY_RUN=true python3 {paper}\n"
            ),
            executor_intent="python",
            complexity="small",
            notes="P5 script_seed stability + duration_s fill",
        ),
    ]


def scenarios_legacy10(app: str) -> list[Scenario]:
    """10 scenarios; keep deliverables tiny to bound OpenCode cost."""
    stem = f"stress_{app.replace('-', '_')}"
    probe = f"scripts/{stem}_feature_probe.py"
    paper = "scripts/paper_intent_probe.py"
    mod = f"scripts/{stem}_mod.py"
    doc = f"docs/{stem.upper()}_NOTE.md"

    return [
        Scenario(
            sid="s01",
            name="单 phase 小功能成功",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 小模块可 import",
            goal=f"落地 {mod} 含 hello() 返回 ok",
            acceptance=[
                f'test -f {mod}',
                f'DRY_RUN=true python3 -c "print(0)"',
            ],
            plan_md=(
                f"# Plan\n\n## 目标\n写 `{mod}`：`hello()` → `'ok'`\n\n"
                f"## Phase 1 — module\n- `{mod}`\n\n"
                f"## 验收\n- test -f {mod}\n"
                f"- DRY_RUN=true python3 -c \"print(0)\"\n"
            ),
            complexity="small",
        ),
        Scenario(
            sid="s02",
            name="3-phase 中等扇出",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 三件套模块+文档+探针",
            goal="扇出三张 work：模块、文档、功能探针",
            acceptance=[
                f"test -f {mod}",
                f"test -f {doc}",
                f"DRY_RUN=true python3 {probe}",
            ],
            plan_md=(
                f"# Plan\n\n## 目标\n模块+文档+探针三 phase\n\n"
                f"## Phase 1 — 模块\n- `{mod}`\n\n"
                f"## Phase 2 — 文档\n- `{doc}`\n\n"
                f"## Phase 3 — 功能探针\n- `{probe}` DRY_RUN\n\n"
                f"## 验收\n- test -f {mod}\n- test -f {doc}\n"
                f"- DRY_RUN=true python3 {probe}\n"
            ),
            complexity="medium",
        ),
        Scenario(
            sid="s03",
            name="审测 FAIL 回滚路径可观察",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 故意空实现待审测",
            goal="写占位脚本供观察 FAIL→planned 重试（Engine 自愈）",
            acceptance=[
                f"test -f scripts/{stem}_s03_placeholder.py",
                f'DRY_RUN=true python3 -c "print(0)"',
            ],
            plan_md=(
                f"# Plan\n\n## Phase 1\n- `scripts/{stem}_s03_placeholder.py`\n"
                f"须含 def ready(): return True\n\n"
                f"## 验收\n- test -f scripts/{stem}_s03_placeholder.py\n"
                f"- DRY_RUN=true python3 -c \"print(0)\"\n"
            ),
            complexity="small",
            notes="expect possible FAIL→planned retry in engine log",
        ),
        Scenario(
            sid="s04",
            name="纯纸面探针 script_seed",
            kind="transfer",
            title=f"[{RUN_TAG}] 纸面意图探针 paper_intent_probe",
            goal=f"机械落地 {paper}，走 script_seed 不进 OpenCode",
            acceptance=[
                f"test -f {paper}",
                f"DRY_RUN=true python3 {paper}",
            ],
            plan_md=(
                f"# Plan\n\n## 目标\nseed `{paper}`\n\n"
                f"## Phase 1\n- `{paper}`\n\n"
                f"## 验收\n- test -f {paper}\n- DRY_RUN=true python3 {paper}\n"
            ),
            executor_intent="python",
            complexity="small",
        ),
        Scenario(
            sid="s05",
            name="功能探针禁止 script_seed 劫持",
            kind="transfer",
            title=f"[{RUN_TAG}] DRY_RUN 意图探针功能卡",
            goal=f"写 {probe}，禁止写成 paper_intent_probe",
            acceptance=[
                f"test -f {probe}",
                f"DRY_RUN=true python3 {probe}",
            ],
            plan_md=(
                f"# Plan\n\n## Phase 1 — feature probe\n- `{probe}`\n"
                f"禁止写 paper_intent_probe.py\n\n"
                f"## 验收\n- test -f {probe}\n- DRY_RUN=true python3 {probe}\n"
            ),
            complexity="small",
        ),
        Scenario(
            sid="s06",
            name="看板卫生 python/board_ops",
            kind="transfer",
            title=f"[{RUN_TAG}] 看板卫生 归档产物对齐",
            goal="仅整理 .ccc 产物卫生，不改业务码",
            acceptance=[
                "test -d .ccc/board",
            ],
            plan_md=(
                "# Plan\n\n## 目标\n看板卫生：确认 .ccc/board 存在\n\n"
                "## Phase 1\n- `.ccc/board`\n\n"
                "## 验收\n- test -d .ccc/board\n"
            ),
            pipeline="ops",
            executor_intent="python",
            complexity="small",
        ),
        Scenario(
            sid="s07",
            name="缺意图探针 transfer 拒单",
            kind="gate_reject",
            title=f"[{RUN_TAG}] 无探针业务卡应被拒",
            goal="故意不写可重放探针，验证 Gate",
            acceptance=["写一个说明文档即可"],
            plan_md="# Plan\n\n## 目标\n无命令验收\n\n## 验收\n- 文档写好即可\n",
            expect_http=400,
            expect_error="missing_intent_probe",
            complexity="small",
        ),
        Scenario(
            sid="s08",
            name="依赖链两 phase",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 依赖链 A后B",
            goal="两 phase：先 A 文件再 B 文件",
            acceptance=[
                f"test -f scripts/{stem}_dep_a.py",
                f"test -f scripts/{stem}_dep_b.py",
                f'DRY_RUN=true python3 -c "print(0)"',
            ],
            plan_md=(
                f"# Plan\n\n## Phase 1 — A\n- `scripts/{stem}_dep_a.py`\n\n"
                f"## Phase 2 — B\n- `scripts/{stem}_dep_b.py` 依赖 A\n\n"
                f"## 验收\n- test -f scripts/{stem}_dep_a.py\n"
                f"- test -f scripts/{stem}_dep_b.py\n"
                f"- DRY_RUN=true python3 -c \"print(0)\"\n"
            ),
            complexity="medium",
        ),
        Scenario(
            sid="s09",
            name="abnormal 重开再跑",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 重开用小卡",
            goal=f"落地 scripts/{stem}_reopen.py 后可被 reopen 流程消费",
            acceptance=[
                f"test -f scripts/{stem}_reopen.py",
                f'DRY_RUN=true python3 -c "print(0)"',
            ],
            plan_md=(
                f"# Plan\n\n## Phase 1\n- `scripts/{stem}_reopen.py`\n\n"
                f"## 验收\n- test -f scripts/{stem}_reopen.py\n"
                f"- DRY_RUN=true python3 -c \"print(0)\"\n"
            ),
            complexity="small",
            notes="watch path may quarantine then reopen_task",
        ),
        Scenario(
            sid="s10",
            name="路径约束纸面/探针不 hang",
            kind="transfer",
            title=f"[{RUN_TAG}] {app} 纸面探针路径约束",
            goal="短路径纸面探针，禁止长 hang",
            acceptance=[
                f"test -f {paper}",
                f"DRY_RUN=true python3 {paper}",
            ],
            plan_md=(
                f"# Plan\n\n## 目标\npaper_intent_probe 可重放\n\n"
                f"## Phase 1\n- `{paper}`\n\n"
                f"## 验收\n- test -f {paper}\n- DRY_RUN=true python3 {paper}\n"
            ),
            executor_intent="python",
            complexity="small",
        ),
    ]


def _http_json(method: str, url: str, body: dict | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {AUTH}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return e.code, payload


def transfer(app: str, sc: Scenario) -> dict[str, Any]:
    crid = _slug(app, sc.sid)
    body: dict[str, Any] = {
        "project_id": app,
        "title": sc.title[:80],
        "goal": sc.goal,
        "acceptance": sc.acceptance,
        "pipeline": sc.pipeline,
        "feasibility": "ok",
        "feasibility_reason": "",
        "executor_intent": sc.executor_intent,
        "complexity": sc.complexity,
        "bump_version": False,
        "plan_md": sc.plan_md,
        "thread_id": f"{app}::{RUN_TAG}",
        "client_request_id": crid,
        "supersede_goals": True,
    }
    code, resp = _http_json("POST", f"{HUB}/api/desktop/transfer", body)
    return {
        "app": app,
        "sid": sc.sid,
        "name": sc.name,
        "client_request_id": crid,
        "http": code,
        "expect_http": sc.expect_http,
        "expect_error": sc.expect_error,
        "ok": (
            code == sc.expect_http
            and (
                sc.expect_error is None
                or str(resp.get("error") or "") == sc.expect_error
                or any(
                    (e or {}).get("code") == sc.expect_error
                    for e in (resp.get("errors") or [])
                    if isinstance(e, dict)
                )
            )
        ),
        "epic_id": resp.get("epic_id"),
        "response": resp,
        "kind": sc.kind,
        "notes": sc.notes,
    }


def load_results() -> dict[str, Any]:
    if RESULTS.is_file():
        return json.loads(RESULTS.read_text(encoding="utf-8"))
    return {"run": RUN_TAG, "dispatches": [], "watch": {}}


def save_results(data: dict[str, Any]) -> None:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def cmd_dispatch(batch: int) -> None:
    """Dispatch by batch."""
    if PROFILE == "efficiency_six":
        ranges = {
            0: ("e01", "e02", "e03", "e04", "e08"),
            1: ("e01", "e02", "e03"),
            2: ("e04", "e08"),
        }
    elif PROFILE == "efficiency_v2":
        ranges = {
            0: ("e01", "e02", "e03", "e04", "e05", "e06", "e07", "e08"),
            1: ("e01", "e02", "e03", "e04"),
            2: ("e05", "e06", "e07", "e08"),
        }
    else:
        ranges = {
            1: ("s01", "s02", "s03", "s04"),
            2: ("s05", "s06", "s07"),
            3: ("s08", "s09", "s10"),
        }
    want = set(ranges.get(batch) or ())
    if not want:
        raise SystemExit(f"unknown batch {batch} for profile={PROFILE}")
    data = load_results()
    data["run"] = RUN_TAG
    data["profile"] = PROFILE
    data.setdefault("dispatches", [])
    done = {
        (d.get("app"), d.get("sid"))
        for d in data.get("dispatches") or []
        if d.get("http") in (200, 400) and d.get("ok")
    }
    for app in APPS:
        for sc in scenarios_for(app):
            if sc.sid not in want:
                continue
            if (app, sc.sid) in done:
                print(f"skip idempotent {app} {sc.sid}")
                continue
            print(f"dispatch {app} {sc.sid} {sc.name} ...")
            row = transfer(app, sc)
            row["dispatched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            row["profile"] = PROFILE
            data.setdefault("dispatches", []).append(row)
            save_results(data)
            status = "OK" if row["ok"] else "FAIL"
            print(
                f"  → {status} http={row['http']} epic={row.get('epic_id')} "
                f"err={row.get('response', {}).get('error')}"
            )
            time.sleep(1)
    print(f"dispatch done → {RESULTS} (profile={PROFILE})")


def cmd_baseline() -> None:
    """Write pre-run host/board baseline for tomorrow's efficiency retrospective."""
    import subprocess

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _board_store import FileBoardStore

    host = {}
    try:
        from _host_resources import summarize

        host = summarize(n=200)
    except Exception as exc:
        host = {"error": str(exc)}
    boards = {}
    for app in APPS:
        store = FileBoardStore(Path(f"/Users/fan/program/apps/{app}"))
        boards[app] = {
            c: len(store.list_tasks(c))
            for c in (
                "backlog",
                "planned",
                "in_progress",
                "testing",
                "abnormal",
                "verified",
                "released",
            )
        }
    payload = {
        "run": RUN_TAG,
        "profile": PROFILE,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": host,
        "boards": boards,
        "git_head": subprocess.check_output(
            ["git", "-C", "/Users/fan/program/CCC", "rev-parse", "--short", "HEAD"],
            text=True,
        ).strip(),
        "metrics_plan": [
            "queue_wait_s p50/p95",
            "dev_wall_s / gate_wall_s",
            "dev_path share",
            "duration_s fill_rate",
            "dirty_result_n",
            "ghost same-ws delay",
            "testing budget timeout kills",
            "revert abort clean",
        ],
    }
    out = Path.home() / ".ccc" / "stress-matrix" / f"{RUN_TAG}-baseline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("wrote", out)

def _board_snapshot(app: str) -> dict[str, Any]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _board_store import FileBoardStore

    ws = Path(f"/Users/fan/program/apps/{app}")
    store = FileBoardStore(ws)
    out: dict[str, Any] = {"columns": {}, "stress_epics": []}
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        tasks = store.list_tasks(col)
        out["columns"][col] = len(tasks)
        for t in tasks:
            tid = str(t.get("id") or "")
            title = str(t.get("title") or "")
            if RUN_TAG in title or RUN_TAG in tid:
                out["stress_epics"].append(
                    {
                        "col": col,
                        "id": tid,
                        "title": title[:80],
                        "split_status": t.get("split_status"),
                        "child_ids": t.get("child_ids"),
                        "card_kind": t.get("card_kind"),
                        "ui_hidden": t.get("ui_hidden"),
                    }
                )
    return out


def cmd_watch(timeout: int) -> None:
    data = load_results()
    deadline = time.time() + timeout
    while time.time() < deadline:
        snaps = {app: _board_snapshot(app) for app in APPS}
        data["watch"] = {"ts": time.time(), "apps": snaps}
        save_results(data)
        # progress print
        for app, snap in snaps.items():
            stress = snap.get("stress_epics") or []
            active = [
                x
                for x in stress
                if x.get("col") in ("planned", "in_progress", "testing", "verified")
                or (
                    x.get("card_kind") == "epic"
                    and x.get("split_status") in ("pending", "planned", "running")
                    and not x.get("ui_hidden")
                )
            ]
            print(
                f"[{app}] active={len(active)} cols={snap.get('columns')} "
                f"stress_cards={len(stress)}"
            )
        # stop if no active stress work
        still = False
        for snap in snaps.values():
            for x in snap.get("stress_epics") or []:
                if x.get("card_kind") == "work" and x.get("col") in (
                    "planned",
                    "in_progress",
                    "testing",
                    "verified",
                ):
                    still = True
                if (
                    x.get("card_kind") == "epic"
                    and x.get("split_status") in ("pending", "planned", "running")
                    and not x.get("ui_hidden")
                ):
                    # children may still be running
                    kids = x.get("child_ids") or []
                    if not kids or x.get("split_status") != "done":
                        still = True
        if not still and any(data.get("dispatches")):
            # give one more tick for kb
            time.sleep(15)
            break
        time.sleep(20)
    print("watch done →", RESULTS)


def cmd_reopen_s09() -> None:
    """If s09 work is abnormal, reopen to planned."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _board_store import FileBoardStore
    from _task_reopen import reopen_task

    data = load_results()
    for row in data.get("dispatches") or []:
        if row.get("sid") != "s09" or not row.get("epic_id"):
            continue
        app = row["app"]
        ws = Path(f"/Users/fan/program/apps/{app}")
        store = FileBoardStore(ws)
        epic_id = row["epic_id"]
        _, epic = store.find_task(epic_id)
        kids = list((epic or {}).get("child_ids") or [])
        for kid in kids:
            col, _ = store.find_task(kid)
            if col == "abnormal":
                r = reopen_task(ws, kid, to_col="planned", wake=True)
                print(app, kid, "reopen", r)
            else:
                print(app, kid, "col", col)


def cmd_report() -> None:
    data = load_results()
    lines = [
        f"# Stress matrix report `{RUN_TAG}`",
        "",
        "## Dispatches",
        "",
        "| app | sid | name | http | ok | epic |",
        "|-----|-----|------|------|----|------|",
    ]
    for d in data.get("dispatches") or []:
        lines.append(
            f"| {d.get('app')} | {d.get('sid')} | {d.get('name')} | "
            f"{d.get('http')} | {d.get('ok')} | `{d.get('epic_id') or ''}` |"
        )
    lines += ["", "## Board snapshot", ""]
    watch = data.get("watch") or {}
    for app, snap in (watch.get("apps") or {}).items():
        lines.append(f"### {app}")
        lines.append(f"columns: `{snap.get('columns')}`")
        for x in snap.get("stress_epics") or []:
            lines.append(
                f"- `{x.get('col')}` `{x.get('id')}` ss={x.get('split_status')} "
                f"kind={x.get('card_kind')}"
            )
        lines.append("")
    out = Path.home() / ".ccc" / "stress-matrix" / f"{RUN_TAG}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text())
    print("wrote", out)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="CCC stress matrix (legacy10 or efficiency_v2)"
    )
    ap.add_argument(
        "--run",
        default="",
        help="run tag (default: stress-mx-YYYYMMDD for efficiency_v2)",
    )
    ap.add_argument(
        "--profile",
        choices=("legacy10", "efficiency_v2", "efficiency_six"),
        default="efficiency_v2",
        help="scenario set (efficiency_six = 6/app valuable)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dispatch")
    d.add_argument(
        "--batch",
        type=int,
        required=True,
        help="efficiency_six/v2: 0=all; legacy: 1/2/3",
    )
    w = sub.add_parser("watch")
    w.add_argument("--timeout", type=int, default=1800)
    sub.add_parser("report")
    sub.add_parser("reopen-s09")
    sub.add_parser("baseline")
    args = ap.parse_args()
    run = args.run.strip()
    if not run:
        if args.profile == "efficiency_six":
            run = "stress-mx-20260723r2"
        elif args.profile == "efficiency_v2":
            run = "stress-mx-20260723"
        else:
            run = "stress-mx-20260722"
    _set_run(run, args.profile)
    if args.cmd == "dispatch":
        cmd_dispatch(args.batch)
    elif args.cmd == "watch":
        cmd_watch(args.timeout)
    elif args.cmd == "report":
        cmd_report()
    elif args.cmd == "reopen-s09":
        cmd_reopen_s09()
    elif args.cmd == "baseline":
        cmd_baseline()


if __name__ == "__main__":
    main()