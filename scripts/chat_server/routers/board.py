"""Chat ↔ CCC Board proxy — create/move/status + optional plan/phases seed."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from ..auth import check_auth
from ..services.board_client import board_proxy
from .projects import PROJECTS, PROJECT_TO_WORKSPACE, reload_projects

router = APIRouter()

# Phase 2.3: /runtime-status 30s 内存缓存（key=workspace）
_runtime_status_cache: dict[str, tuple[float, dict]] = {}


def _resolve_workspace(body: dict | None, request: Request) -> str:
    body = body or {}
    ws = (
        body.get("workspace")
        or request.query_params.get("workspace")
        or "CCC"
    )
    return _sanitize_workspace(str(ws).strip() or "CCC")


def _sanitize_workspace(workspace: str) -> str:
    """Hub 侧拒路径穿越/过长 workspace，再透传 Board Server。"""
    w = (workspace or "CCC").strip() or "CCC"
    if (
        ".." in w
        or "/" in w
        or "\\" in w
        or len(w) > 64
        or not all(c.isalnum() or c in "-_." for c in w)
    ):
        raise HTTPException(status_code=400, detail=f"invalid workspace: {workspace!r}")
    return w


def _workspace_root(workspace: str) -> Path | None:
    """Map board workspace id → filesystem root."""
    if not PROJECTS:
        reload_projects()
    for pid, ws in PROJECT_TO_WORKSPACE.items():
        if ws == workspace and pid in PROJECTS:
            return Path(PROJECTS[pid]["path"])
    # Fallback: case-insensitive match on project id
    key = workspace.lower().replace(" ", "-")
    if key in PROJECTS:
        return Path(PROJECTS[key]["path"])
    return None


def _write_seed_artifacts(
    workspace: str,
    task_id: str,
    plan_md: str | None,
    phases_jsonl: str | None,
) -> dict:
    """Write optional plan/phases so Engine can skip product and go planned→dev.

    Desktop transfer 常只带 plan_md。若缺 phases，从 plan 合成（保留 .ccc 白名单
    scope），避免误领养历史 plan 或 Claude 扇出漂移后才有 phases。
    """
    written = {}
    if not plan_md and not phases_jsonl:
        return written
    root = _workspace_root(workspace)
    if root is None:
        raise HTTPException(
            status_code=400,
            detail=f"cannot resolve workspace path for seed artifacts: {workspace}",
        )
    if plan_md:
        plans = root / ".ccc" / "plans"
        plans.mkdir(parents=True, exist_ok=True)
        path = plans / f"{task_id}.plan.md"
        path.write_text(plan_md, encoding="utf-8")
        written["plan"] = str(path)
    if not phases_jsonl and plan_md:
        try:
            import sys

            scripts = Path(__file__).resolve().parents[3] / "scripts"
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            from _plan_adopt import phases_jsonl_from_plan

            phases_jsonl = phases_jsonl_from_plan(plan_md)
            written["phases_synthesized"] = True
        except Exception as exc:
            written["phases_synthesize_error"] = str(exc)[:200]
            phases_jsonl = None
    if phases_jsonl:
        phases = root / ".ccc" / "phases"
        phases.mkdir(parents=True, exist_ok=True)
        path = phases / f"{task_id}.phases.json"
        path.write_text(phases_jsonl.rstrip() + "\n", encoding="utf-8")
        written["phases"] = str(path)
    return written


def _assert_dispatchable_workspace(workspace: str) -> Path:
    """v0.51: refuse creating Engine-consumable tasks on orch (CCC) workspace."""
    import sys

    scripts = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    root = _workspace_root(workspace)
    if root is None:
        # Still allow board-server to resolve unknown names; Hub may 404 later
        return Path()
    try:
        from _workspace_registry import entry_engine_eligible, is_orch_path, lookup_entry

        if is_orch_path(root):
            raise HTTPException(
                status_code=400,
                detail=(
                    "CCC 编排仓不可下达看板任务（v0.51）。"
                    "平台改动请用 Cursor 打开 CCC 仓；业务请选登记项目。"
                ),
            )
        entry = lookup_entry(root)
        if entry and not entry_engine_eligible(entry):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"workspace {workspace} engine=false / role=orch，"
                    "不可下达；请改用业务项目。"
                ),
            )
    except HTTPException:
        raise
    except Exception:
        if workspace.strip().upper() in ("CCC",) or workspace.strip().lower() == "ccc":
            raise HTTPException(
                status_code=400,
                detail="CCC 编排仓不可下达看板任务（v0.51）。请用 Cursor 改 CCC。",
            )
    return root


def _hub_ensure_engine(workspace: str, task_id: str | None) -> dict:
    """v0.42.1 Hub 双保险：即使 Board 旧进程无 wake，Hub 也强制 enabled+登记+wake。

    幂等；与 Board 侧 ensure 重复调用安全。
    v0.51: orch 仍可 wake/控制面，但登记为 role=orch engine=false。
    返回附带 workspace_eligible / human message，供 Desktop 未扇出可解释。
    """
    import sys

    scripts = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from _engine_wake import ensure_engine_for_task, is_engine_running
        from _workspace_registry import (
            entry_engine_eligible,
            is_orch_path,
            lookup_entry,
        )

        root = _workspace_root(workspace)
        result = ensure_engine_for_task(
            reason="task_dispatch",
            task_id=task_id,
            workspace=root,
            workspace_name=workspace,
        )
        eligible = True
        if root is not None and is_orch_path(root):
            eligible = False
        else:
            try:
                ent = lookup_entry(workspace) if workspace else None
                if ent is None and root is not None:
                    ent = lookup_entry(root)
                if ent is not None:
                    eligible = entry_engine_eligible(ent)
            except Exception:
                pass
        result["workspace_eligible"] = bool(eligible)
        result["workspace"] = workspace
        running = bool(result.get("engine_running"))
        if not result.get("ok"):
            result["block_reason"] = str(result.get("error") or "wake_failed")[:200]
        elif not eligible:
            result["block_reason"] = "workspace_not_engine_eligible"
            result["message"] = (
                result.get("message")
                or "epic queued but workspace is not Engine-consumable (orch/engine=false)"
            )
        elif not running:
            result["block_reason"] = "engine_not_running"
            result["message"] = result.get("message") or (
                f"queued; Engine not running ({result.get('launch_note')})"
            )
            # refresh once
            result["engine_running"] = is_engine_running()
            if result["engine_running"]:
                result.pop("block_reason", None)
                result["message"] = None
        else:
            result.setdefault("block_reason", None)
        return result
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:200],
            "engine_running": False,
            "workspace_eligible": None,
            "block_reason": "wake_exception",
            "message": str(exc)[:200],
        }


def _hub_try_adopt_plan(workspace: str, task_id: str, task_body: dict) -> dict | None:
    """下达后若 description 引用现成 plan，立即收养，避免 product 白烧。"""
    import sys

    scripts = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    root = _workspace_root(workspace)
    if root is None or not task_id:
        return None
    try:
        from _plan_adopt import try_adopt_referenced_plan

        return try_adopt_referenced_plan(root, task_id, task_body)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def _merge_create_payload(
    resp_body: bytes | str | bytearray,
    *,
    workspace: str,
    fallback_tid: str | None,
    task_body: dict | None = None,
) -> dict:
    """Parse board create JSON and attach Hub-side engine_wake (+ optional plan adopt)."""
    import json

    try:
        payload = json.loads(
            resp_body.decode() if isinstance(resp_body, (bytes, bytearray)) else resp_body
        )
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    tid = payload.get("task_id") or fallback_tid
    hub_wake = _hub_ensure_engine(workspace, tid)
    board_wake = payload.get("engine_wake")
    payload["engine_wake"] = hub_wake
    if board_wake is not None:
        payload["engine_wake_board"] = board_wake
    if tid and task_body:
        adopted = _hub_try_adopt_plan(workspace, str(tid), task_body)
        if adopted:
            payload["plan_adopt"] = adopted
    return payload


@router.get("/api/board/proxy/board")
async def board_proxy_board(request: Request, workspace: str = "CCC"):
    check_auth(request)
    workspace = _sanitize_workspace(workspace)
    return await board_proxy("GET", "/api/board", params={"workspace": workspace})


@router.get("/api/board/proxy/dashboard")
async def board_proxy_dashboard(request: Request, workspace: str = "CCC"):
    check_auth(request)
    workspace = _sanitize_workspace(workspace)
    return await board_proxy("GET", "/api/dashboard", params={"workspace": workspace})


@router.get("/api/board/proxy/roles")
async def board_proxy_roles(request: Request):
    check_auth(request)
    return await board_proxy("GET", "/api/roles")


@router.get("/api/board/proxy/timeline")
async def board_proxy_timeline(request: Request, workspace: str = "CCC"):
    check_auth(request)
    workspace = _sanitize_workspace(workspace)
    return await board_proxy("GET", "/api/timeline", params={"workspace": workspace})


@router.get("/api/board/proxy/tasks/{task_id}")
async def board_proxy_get_task(request: Request, task_id: str, workspace: str = "CCC"):
    check_auth(request)
    workspace = _sanitize_workspace(workspace)
    return await board_proxy(
        "GET", f"/api/tasks/{task_id}", params={"workspace": workspace}
    )


@router.get("/api/board/proxy/tasks/{task_id}/events")
async def board_proxy_task_events(request: Request, task_id: str, workspace: str = "CCC"):
    check_auth(request)
    workspace = _sanitize_workspace(workspace)
    return await board_proxy(
        "GET", f"/api/tasks/{task_id}/events", params={"workspace": workspace}
    )


def _enforce_epic_only_create(body: dict) -> None:
    """安全：Hub/API 创建 backlog 任务只能是 epic（禁止直写 work 绕过 transfer）。"""
    kind = str(body.get("card_kind") or "").strip().lower()
    if kind == "work":
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": "role_lock_violation",
                "message": "API 禁止创建 card_kind=work；请走 /api/desktop/transfer（epic）由 product 扇出",
            },
        )
    body["card_kind"] = "epic"
    # 禁止附带 phases 跳过 product（除非显式运维开关）
    import os

    if os.environ.get("CCC_ALLOW_SEED_PHASES") != "1":
        if body.get("phases_jsonl") or body.get("phases"):
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "error": "seed_phases_forbidden",
                    "message": "禁止 API 附带 phases 跳过 product；设 CCC_ALLOW_SEED_PHASES=1 仅运维调试",
                },
            )


@router.post("/api/board/proxy/tasks")
async def board_proxy_create_task(request: Request):
    """Create backlog epic；默认禁止 phases 跳过 product（安全对齐 2026-07-19）。"""
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")

    workspace = _resolve_workspace(body, request)
    body["workspace"] = workspace
    _assert_dispatchable_workspace(workspace)
    if not body.get("status"):
        body["status"] = "backlog"
    _enforce_epic_only_create(body)

    plan_md = body.pop("plan_md", None)
    phases_jsonl = body.pop("phases_jsonl", None)
    if plan_md is not None and not isinstance(plan_md, str):
        raise HTTPException(status_code=400, detail="plan_md must be string")
    if phases_jsonl is not None and not isinstance(phases_jsonl, str):
        raise HTTPException(status_code=400, detail="phases_jsonl must be string")
    # 双保险：即便开关打开，也只在 CCC_ALLOW_SEED_PHASES=1 时写 seed
    import os

    if os.environ.get("CCC_ALLOW_SEED_PHASES") != "1":
        plan_md = None
        phases_jsonl = None

    resp = await board_proxy("POST", "/api/tasks", json_body=body)

    # Attach seed artifacts only on successful create
    if resp.status_code in (200, 201):
        payload = _merge_create_payload(
            resp.body,
            workspace=workspace,
            fallback_tid=body.get("id"),
            task_body=body,
        )
        tid = payload.get("task_id") or body.get("id")
        if tid and (plan_md or phases_jsonl):
            try:
                written = _write_seed_artifacts(workspace, tid, plan_md, phases_jsonl)
                payload["seeded"] = written
                payload["skip_product"] = bool(written.get("plan") and written.get("phases"))
            except HTTPException:
                raise
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"seed artifacts failed: {exc}") from exc
        return JSONResponse(content=payload, status_code=resp.status_code)
    return resp


@router.post("/api/board/proxy/tasks/move")
async def board_proxy_move_task(request: Request):
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    body["workspace"] = _resolve_workspace(body, request)
    return await board_proxy("POST", "/api/tasks/move", json_body=body)


# --- Native board paths (Hub same-origin for board/console pages) ---

@router.get("/api/board")
async def native_board(
    request: Request,
    workspace: str = "CCC",
    fields: str | None = None,
    include_hidden: str | None = None,
):
    check_auth(request)
    workspace = _sanitize_workspace(workspace)
    params: dict = {"workspace": workspace}
    if fields:
        params["fields"] = fields
    if include_hidden:
        params["include_hidden"] = include_hidden
    return await board_proxy("GET", "/api/board", params=params)


@router.get("/api/board/summaries")
async def board_summaries(request: Request, workspaces: str = ""):
    """Phase 3.1: 聚合端点 — 一次返回多 workspace 的 summary，替代前端 N 次 GET。"""
    check_auth(request)
    import asyncio
    import json as _json

    names = [w.strip() for w in (workspaces or "").split(",") if w.strip()]
    if not names:
        return {"summaries": {}}

    async def _one(name: str) -> tuple[str, dict]:
        try:
            # 不含 ui_hidden：Desktop 项目灯 / 编排态只看可见活；已完成沉底卡不计入
            resp = await board_proxy(
                "GET",
                "/api/board",
                params={"workspace": name, "fields": "summary"},
            )
            if resp.status_code >= 400:
                return name, {"error": f"board {resp.status_code}"}
            body = resp.body
            data = _json.loads(
                body.decode() if isinstance(body, (bytes, bytearray)) else body
            )
            return name, data
        except Exception as exc:
            return name, {"error": str(exc)[:120]}

    results = await asyncio.gather(*[_one(n) for n in names])
    return {"summaries": dict(results)}


@router.get("/api/config")
async def native_config(request: Request):
    check_auth(request)
    return await board_proxy("GET", "/api/config")


@router.get("/api/dashboard")
async def native_dashboard(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy("GET", "/api/dashboard", params={"workspace": workspace})


@router.get("/api/roles")
async def native_roles(request: Request):
    check_auth(request)
    return await board_proxy("GET", "/api/roles")


@router.get("/api/timeline")
async def native_timeline(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy("GET", "/api/timeline", params={"workspace": workspace})


@router.get("/api/logs")
async def native_logs(request: Request, lines: int = 50, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy(
        "GET", "/api/logs", params={"lines": lines, "workspace": workspace}
    )


@router.get("/api/failures")
async def native_failures(
    request: Request, last: int = 20, workspace: str = "CCC"
):
    """v0.40: 统一失败账本 .ccc/stats/failures.jsonl"""
    check_auth(request)
    import sys

    root = Path(__file__).resolve().parents[3]
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from _failure_ledger import read_failures

    ws_path = _workspace_root(workspace) or root
    rows = read_failures(ws_path, last=max(1, min(int(last), 100)))
    return {
        "workspace": workspace,
        "path": str(ws_path / ".ccc" / "stats" / "failures.jsonl"),
        "failures": rows,
    }


@router.get("/api/task-cost/{task_id}")
async def native_task_cost(request: Request, task_id: str):
    """按 task_id 汇总真实 LLM 调用（cost-telemetry.jsonl）。"""
    check_auth(request)
    import sys

    root = Path(__file__).resolve().parents[3]
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from _cost_telemetry import summarize_task_calls

    return summarize_task_calls(task_id)


@router.get("/api/tasks/{task_id}")
async def native_get_task(request: Request, task_id: str, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy(
        "GET", f"/api/tasks/{task_id}", params={"workspace": workspace}
    )


@router.get("/api/tasks/{task_id}/events")
async def native_task_events(request: Request, task_id: str, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy(
        "GET", f"/api/tasks/{task_id}/events", params={"workspace": workspace}
    )


@router.post("/api/tasks")
async def native_create_task(request: Request):
    """Thin proxy；仅允许创建 epic（禁止 work 绕过 transfer）。"""
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    body["workspace"] = _resolve_workspace(body, request)
    _assert_dispatchable_workspace(body["workspace"])
    if not body.get("status"):
        body["status"] = "backlog"
    _enforce_epic_only_create(body)
    workspace = body["workspace"]
    resp = await board_proxy("POST", "/api/tasks", json_body=body)
    if resp.status_code in (200, 201):
        payload = _merge_create_payload(
            resp.body,
            workspace=workspace,
            fallback_tid=body.get("id"),
            task_body=body,
        )
        return JSONResponse(content=payload, status_code=resp.status_code)
    return resp


@router.post("/api/tasks/move")
async def native_move_task(request: Request):
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    body["workspace"] = _resolve_workspace(body, request)
    return await board_proxy("POST", "/api/tasks/move", json_body=body)


@router.post("/api/tasks/hide-completed-epics")
async def hide_completed_epics(request: Request):
    """隐藏待办中已完成（split_status=done）的大卡；数据保留。"""
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        body = {}
    body["workspace"] = _resolve_workspace(body, request)
    return await board_proxy(
        "POST", "/api/tasks/hide-completed-epics", json_body=body
    )


@router.post("/api/tasks/reopen")
async def native_reopen_task(request: Request):
    """v0.42: 从 abnormal/testing 重开到 planned/in_progress + wake Engine。"""
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    workspace = _resolve_workspace(body, request)
    tid = str(body.get("id") or body.get("task_id") or "").strip()
    to_col = str(body.get("to") or "planned")
    if not tid:
        raise HTTPException(status_code=400, detail="missing id")
    root = _workspace_root(workspace)
    if root is None:
        # fallback: proxy board-server（discover_workspaces）
        body["workspace"] = workspace
        body["id"] = tid
        body["to"] = to_col
        return await board_proxy("POST", "/api/tasks/reopen", json_body=body)
    import sys

    scripts = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from _task_reopen import reopen_task

    result = reopen_task(root, tid, to_col=to_col, wake=True)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "reopen failed")
    return result


@router.get("/api/runtime-status")
async def runtime_status(request: Request, workspace: str = "CCC"):
    """v0.42: Hub 状态条 — control · wake · 队列计数。

    Phase 2.3: 30s 内存缓存（key=workspace）；git subprocess 走 to_thread 不阻塞事件循环。
    """
    check_auth(request)
    import sys

    cached = _runtime_status_cache.get(workspace)
    if cached is not None and (time.time() - cached[0]) < 30.0:
        return cached[1]

    scripts = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from _ccc_control import status_dict
    from _engine_wake import WAKE_FILE, is_engine_running

    control = status_dict()
    wake_exists = WAKE_FILE.is_file()
    wake_payload = None
    if wake_exists:
        try:
            import json

            wake_payload = json.loads(WAKE_FILE.read_text(encoding="utf-8"))
        except Exception:
            wake_payload = {"raw": True}

    counts = {
        "backlog": 0,
        "planned": 0,
        "in_progress": 0,
        "testing": 0,
        "abnormal": 0,
    }
    root = _workspace_root(workspace)
    if root is not None:
        try:
            from _board_store import FileBoardStore

            store = FileBoardStore(root)
            for k in counts:
                counts[k] = len(store.list_tasks(k))
        except Exception:
            pass
    else:
        try:
            board = await board_proxy(
                "GET", "/api/board", params={"workspace": workspace, "fields": "summary"}
            )
            import json as _json

            if board.status_code < 400:
                payload = _json.loads(
                    board.body.decode()
                    if isinstance(board.body, (bytes, bytearray))
                    else board.body
                )
                raw_counts = payload.get("counts") or {}
                for k in counts:
                    if k in raw_counts:
                        counts[k] = int(raw_counts[k])
        except Exception:
            pass

    engine_running = False
    try:
        engine_running = is_engine_running()
    except Exception:
        engine_running = False

    git_info: dict = {"dirty": 0, "ahead": 0, "behind": 0, "branch": None}
    if root is not None:
        try:
            import asyncio
            import subprocess

            async def _run_git(args: list[str]) -> str:
                proc = await asyncio.to_thread(
                    subprocess.run,
                    args,
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
                return proc.stdout if proc.returncode == 0 else ""

            br_out, st_out, ab_out = await asyncio.gather(
                _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
                _run_git(["git", "status", "--porcelain"]),
                _run_git(["git", "rev-list", "--left-right", "--count", "@{u}...HEAD"]),
            )
            git_info["branch"] = br_out.strip() or None
            git_info["dirty"] = len([ln for ln in st_out.splitlines() if ln.strip()])
            parts = ab_out.split()
            if len(parts) >= 2:
                try:
                    git_info["behind"] = int(parts[0])
                    git_info["ahead"] = int(parts[1])
                except ValueError:
                    pass
        except Exception:
            pass

    result = {
        "workspace": workspace,
        "control": control,
        "mode": control.get("mode"),
        "engine_allowed": bool(control.get("engine_allowed")),
        "engine_running": bool(engine_running),
        "wake_file": str(WAKE_FILE),
        "wake_pending": wake_exists,
        "wake": wake_payload,
        "counts": counts,
        "git": git_info,
    }
    _runtime_status_cache[workspace] = (time.time(), result)
    return result


@router.post("/api/engine/start")
async def engine_start(request: Request):
    """Hub 手动启动 Engine（enabled + launchd）。"""
    check_auth(request)
    import sys

    scripts = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from _engine_wake import start_engine

    return start_engine(reason="hub_manual_start", source="hub")


@router.post("/api/engine/stop")
async def engine_stop(request: Request):
    """Hub 手动停止 Engine（ui + bootout）。"""
    check_auth(request)
    import sys

    scripts = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from _engine_wake import stop_engine

    return stop_engine(reason="hub_manual_stop", source="hub")
