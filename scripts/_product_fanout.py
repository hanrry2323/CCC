"""Epic → work 扇出：Claude 拆大卡为 N 张可消费小卡（直入 planned）。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import phase_lint
from _board_store import (
    FileBoardStore,
    assign_color_group,
    normalize_task_view,
    sanitize_id,
)
from _config import get_logger

_log = get_logger("product.fanout")

MAX_CHILDREN = int(os.environ.get("CCC_MAX_CHILDREN_PER_EPIC", "8") or "8")


def _project_id_for_workspace(workspace: Path | str | None) -> str | None:
    """workspace 路径 → Desktop project_id（供 flow-events 过滤）。"""
    if not workspace:
        return None
    try:
        name = Path(workspace).resolve().name
    except OSError:
        name = Path(str(workspace)).name
    if not name:
        return None
    try:
        from chat_server.routers.projects import PROJECT_TO_WORKSPACE

        for pid, ws in (PROJECT_TO_WORKSPACE or {}).items():
            if str(ws) == name or Path(str(ws)).name == name:
                return str(pid)
    except Exception:
        pass
    return name


def max_children() -> int:
    return max(1, min(MAX_CHILDREN, 16))


_COMMIT_ONLY_RE = re.compile(
    r"(仅?\s*提交|单独\s*commit|git\s*commit|提交\s*git|commit\s*message|含任务\s*id)",
    re.I,
)
_WRITE_ONLY_RE = re.compile(
    r"(写入|覆写|创建|更新).{0,40}(flow-smoke|\.md|文件)|写\s*\.ccc/",
    re.I,
)


def _is_multi_step_regression(epic: dict) -> bool:
    """多步回归/三件套冒烟：即使标了 small 也不强制单卡。"""
    blob = f"{epic.get('title', '')} {epic.get('description', '')}"
    markers = (
        "startup_check",
        "pytest",
        "data_engine",
        "order_gateway",
        "三件套",
        "回归冒烟",
        "回归烟测",
    )
    return sum(1 for m in markers if m in blob) >= 3


def detect_write_commit_oversplit(children_raw: list[dict], *, epic: dict | None = None) -> str | None:
    """Detect write-file vs commit-only split. Return error message or None."""
    if not children_raw or len(children_raw) < 2:
        return None
    epic = epic or {}
    complexity = str(epic.get("complexity") or "").lower()
    epic_blob = f"{epic.get('title', '')} {epic.get('description', '')}"
    # small / 单文件「写入并提交」烟测强制 1 卡；多步回归除外
    force_single = (
        not _is_multi_step_regression(epic)
        and (
            complexity in ("small", "sm")
            or "flow-smoke" in epic_blob
            or "flow-green" in epic_blob
            or "写入并提交" in epic_blob
        )
    )
    if force_single and len(children_raw) > 1:
        return (
            f"oversplit: complexity/smoke epic requires exactly 1 work card, "
            f"got {len(children_raw)}"
        )

    write_ish = 0
    commit_ish = 0
    for ch in children_raw:
        if not isinstance(ch, dict):
            continue
        blob = " ".join(
            str(ch.get(k) or "")
            for k in ("title", "description", "plan_md")
        )
        is_commit = bool(_COMMIT_ONLY_RE.search(blob)) and "写入并提交" not in blob
        is_write = bool(_WRITE_ONLY_RE.search(blob)) and not (
            "commit" in blob.lower() and "写入并提交" in blob
        )
        # title like 「提交 git commit」
        title = str(ch.get("title") or "")
        if re.search(r"^提交|commit", title, re.I) and "写入" not in title:
            is_commit = True
        if is_commit:
            commit_ish += 1
        elif is_write:
            write_ish += 1
    if write_ish >= 1 and commit_ish >= 1:
        return (
            "oversplit: refuse write-file + commit-only child pair; "
            "merge into one work card that writes and commits"
        )
    return None


def build_fanout_prompt(
    *,
    epic: dict,
    workspace: Path,
    profile: str,
    code_ctx: str,
    template_plan: str,
    ref_plans: str,
    max_phases: int,
) -> str:
    eid = epic["id"]
    return (
        f"你是 CCC 产品经理。待办里的是**大卡 epic**，你必须把它拆成多张**小卡 work**，"
        f"供低质量开发模型直接执行。\n"
        f"**禁止**只给原卡写一个巨大 plan 后原样推进；必须扇出子卡。\n"
        f"**工作目录硬门**：workspace=`{workspace.resolve()}`；"
        f"所有 scope 路径必须落在该目录下。\n"
        f"硬门：每个子卡 plan 必须含 `## 验收` 或 `## 验证`；"
        f"每个 phase 必须非空 scope + description。\n\n"
        f"## 项目概况\n{profile[:1500]}\n\n"
        f"## 当前代码状态\n{code_ctx[:3000] if code_ctx else '（无）'}\n\n"
        f"## 大卡 Epic\n"
        f"- id: {eid}\n"
        f"- title: {epic.get('title', '')}\n"
        f"- complexity: {epic.get('complexity') or 'medium'}\n"
        f"- description: {epic.get('description', '')}\n\n"
        f"## 子卡约束（低端模型可执行 · 反过拆）\n"
        f"- **默认恰好 1 张**子卡；仅当验收含 ≥2 个独立可交付物时才允许多卡（最多 {max_children()}）\n"
        f"- **禁止**把「写文件」与「单独 git commit」拆成两张卡；写入并提交必须在同一张 work 内完成\n"
        f"- complexity=small / 单文件「写入并提交」烟测：强制 1 张；"
        f"**多步回归（startup_check+pytest+三件套等）除外，应拆 2～N 张**\n"
        f"- medium：优先 1–2 张；禁止为「好看」拆出无独立验收的空卡\n"
        f"- 每张子卡最多 {max_phases} 个 phase（优先 1 个）\n"
        f"- 子卡 id：kebab-case，建议前缀 `{eid}-`\n"
        f"- 每张子卡必须可独立被开发模型消费（目标清晰、scope 明确、验收可执行）\n"
        f"- scope 路径必须可被 git 跟踪：勿选被 .gitignore 忽略的文件"
        f"（如业务仓忽略 AGENTS.md/agents.md 时改 README.md 或已跟踪文档）\n"
        f"- plan_md 内**禁止英文双引号**（用「」或 '）；JSON 必须可被标准解析器加载\n\n"
        f"## 单卡 Plan 结构参考\n{template_plan[:2500]}\n\n"
        f"## 参考历史\n{ref_plans[:2000] if ref_plans else '（无）'}\n\n"
        f"## 输出格式（严格）\n\n"
        f"---EPIC_BRIEF---\n"
        f"（可选：大卡总览 markdown，给人类看）\n"
        f"---END_EPIC_BRIEF---\n\n"
        f"---CHILDREN---\n"
        f"[\n"
        f"  {{\n"
        f'    "id": "{eid}-w1",\n'
        f'    "title": "短标题",\n'
        f'    "description": "一句话",\n'
        f'    "plan_md": "# ...\\n\\n## 验收\\n- ...",\n'
        f'    "phases": [\n'
        f'      {{"phase": 1, "status": "pending", "description": "...", '
        f'"scope": ["path/to/file.py"], "subtasks": {{"1.1": "pending"}}, '
        f'"timeout": 1800, "commit": null, "notes": ""}}\n'
        f"    ]\n"
        f"  }}\n"
        f"]\n"
        f"---END_CHILDREN---\n"
    )


def _repair_json_strings(s: str) -> str:
    """Escape bare quotes / control chars inside JSON string values (LLM 常见脏 JSON)."""
    out: list[str] = []
    i = 0
    n = len(s)
    in_string = False
    while i < n:
        c = s[i]
        if not in_string:
            out.append(c)
            if c == '"':
                in_string = True
            i += 1
            continue
        if c == "\\":
            if i + 1 >= n:
                out.append("\\\\")
                i += 1
                continue
            nxt = s[i + 1]
            # 合法 JSON escape；其余（如 \. \c）→ 转成 \\X 避免 Invalid \escape
            if nxt in '"\\/bfnrt':
                out.append(c)
                out.append(nxt)
                i += 2
                continue
            if nxt == "u" and i + 5 < n and all(
                ch in "0123456789abcdefABCDEF" for ch in s[i + 2 : i + 6]
            ):
                out.append(s[i : i + 6])
                i += 6
                continue
            out.append("\\\\")
            out.append(nxt)
            i += 2
            continue
        if c == '"':
            j = i + 1
            while j < n and s[j] in " \t\r\n":
                j += 1
            if j >= n or s[j] in ",:}]:":
                out.append(c)
                in_string = False
                i += 1
                continue
            out.append('\\"')
            i += 1
            continue
        if c == "\n":
            out.append("\\n")
            i += 1
            continue
        if c == "\r":
            i += 1
            continue
        if c == "\t":
            out.append("\\t")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _loads_children_json(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        children = json.loads(raw)
    except json.JSONDecodeError:
        children = json.loads(_repair_json_strings(raw))
    if not isinstance(children, list) or not children:
        raise ValueError("CHILDREN must be non-empty list")
    if len(children) > max_children():
        raise ValueError(f"too many children: {len(children)} > {max_children()}")
    return children


def parse_fanout_output(output: str) -> tuple[str, list[dict]]:
    """解析 EPIC_BRIEF + CHILDREN。失败 raise ValueError。

    兼容：模型偶发仍输出 ---PLAN---/---PHASES--- 时，折叠为 1 张 work 子卡。
    """
    brief = ""
    bm = re.search(
        r"---EPIC_BRIEF---\s*\n?(.*?)\n?---END_EPIC_BRIEF---", output, re.DOTALL
    )
    if bm:
        brief = bm.group(1).strip()

    cm = re.search(
        r"---CHILDREN---\s*\n?(.*?)\n?---END_CHILDREN---", output, re.DOTALL
    )
    if cm:
        children = _loads_children_json(cm.group(1))
        return brief, children

    # 兼容回退：单卡 PLAN+PHASES → 一张 work
    plan_m = re.search(
        r"---PLAN---\s*\n?(.*?)\n?---END_PLAN---", output, re.DOTALL
    )
    phases_m = re.search(
        r"---PHASES---\s*\n?(.*?)\n?---END_PHASES---", output, re.DOTALL
    )
    if plan_m and phases_m:
        plan_md = plan_m.group(1).strip()
        phases_raw = phases_m.group(1).strip()
        phases: list[dict] = []
        if phases_raw.startswith("["):
            try:
                phases = json.loads(_repair_json_strings(phases_raw))
            except json.JSONDecodeError:
                phases = []
        if not phases:
            for line in phases_raw.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    phases.append(json.loads(line))
                except json.JSONDecodeError:
                    try:
                        phases.append(json.loads(_repair_json_strings(line)))
                    except json.JSONDecodeError:
                        continue
        if not phases:
            raise ValueError("PLAN/PHASES fallback: no valid phases")
        return brief or plan_md[:500], [
            {
                "id": "auto-w1",
                "title": "执行原卡 plan（兼容单卡扇出）",
                "description": "Claude 未输出 CHILDREN，已折叠为单张 work",
                "plan_md": plan_md,
                "phases": phases[:2],
            }
        ]

    raise ValueError("CHILDREN section not found")


def _normalize_child(
    raw: dict,
    *,
    epic_id: str,
    idx: int,
    max_phases: int,
    workspace: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"child[{idx}] not object")
    cid = sanitize_id(str(raw.get("id") or f"{epic_id}-w{idx + 1}"))
    if cid == "invalid":
        raise ValueError(f"child[{idx}] bad id")
    title = str(raw.get("title") or cid).strip()
    if not title:
        raise ValueError(f"child[{idx}] empty title")
    plan_md = str(raw.get("plan_md") or raw.get("plan") or "").strip()
    if not plan_md:
        raise ValueError(f"child[{idx}] missing plan_md")
    phases = raw.get("phases")
    if phases is None and raw.get("phases_jsonl"):
        phases = []
        for line in str(raw["phases_jsonl"]).splitlines():
            line = line.strip()
            if line:
                phases.append(json.loads(line))
    if not isinstance(phases, list) or not phases:
        raise ValueError(f"child[{idx}] missing phases")
    if len(phases) > max_phases:
        raise ValueError(f"child[{idx}] phases > {max_phases}")
    plan_md = phase_lint.normalize_plan_acceptance_headers(plan_md)
    ok, errs, _ = phase_lint.validate_phases_dict(phases, workspace=workspace)
    if not ok:
        raise ValueError(f"child[{idx}] phase_lint: {'; '.join(errs)}")
    dep_ok, dep_errs = phase_lint.suggest_fix_no_missing_dependencies(phases)
    if not dep_ok:
        raise ValueError(f"child[{idx}] orphan-dep: {'; '.join(dep_errs)}")
    pok, perrs = phase_lint.validate_plan_acceptance(
        plan_md,
        require_probe=not any(
            k in plan_md.lower()
            for k in ("board_ops", "看板卫生", "pipeline: ops", "pipeline: hygiene")
        ),
    )
    if not pok:
        raise ValueError(f"child[{idx}] plan_lint: {'; '.join(perrs)}")
    deps_tasks: list[str] = []
    raw_deps = raw.get("depends_on_tasks")
    if isinstance(raw_deps, str) and raw_deps.strip():
        deps_tasks = [raw_deps.strip()]
    elif isinstance(raw_deps, list):
        for d in raw_deps:
            s = str(d or "").strip()
            if s and s not in deps_tasks:
                deps_tasks.append(s)
    executor = str(raw.get("executor") or "").strip().lower() or None
    executor_spec = raw.get("executor_spec")
    if executor_spec is not None and not isinstance(executor_spec, dict):
        executor_spec = None
    return {
        "id": cid,
        "title": title[:500],
        "description": str(raw.get("description") or "")[:10000],
        "plan_md": plan_md,
        "phases": phases,
        "depends_on_tasks": deps_tasks,
        "executor": executor,
        "executor_spec": executor_spec,
    }


def _epic_default_executor(epic: dict) -> str:
    """从 epic tags/note/description 推断默认 executor（Desktop transfer 写入）。"""
    tags = epic.get("tags") or []
    for t in tags:
        s = str(t or "")
        if s.startswith("exec:"):
            return s.split(":", 1)[1].strip().lower() or "opencode"
    note = epic.get("note")
    if isinstance(note, str) and note.strip().startswith("{"):
        try:
            data = json.loads(note)
            intent = (
                (data.get("transfer_gate") or {}).get("executor_intent")
                if isinstance(data, dict)
                else None
            )
            if intent:
                return str(intent).strip().lower()
        except json.JSONDecodeError:
            pass
    desc = str(epic.get("description") or "")
    m = re.search(r"executor_intent:\s*(\w+)", desc)
    if m:
        return m.group(1).strip().lower()
    return "opencode"


def apply_fanout(
    store: FileBoardStore,
    epic: dict,
    *,
    children_raw: list[dict],
    epic_brief: str = "",
    max_phases: int = 2,
    default_executor: str | None = None,
) -> dict:
    """校验并落盘子卡；更新 epic。成功返回 {ok, child_ids, color_group}。"""
    epic = normalize_task_view(epic, column="backlog")
    epic_id = epic["id"]
    if epic.get("card_kind") != "epic":
        return {"ok": False, "error": "not an epic"}
    ss = epic.get("split_status") or "pending"
    kids_existing = list(epic.get("child_ids") or [])
    # pending / failed（无子卡）可扇出；已有子卡则拒（含存量 active→running）
    if kids_existing and ss in ("planned", "running", "done", "failed"):
        return {"ok": False, "error": f"epic already split ({ss})"}

    oversplit = detect_write_commit_oversplit(children_raw, epic=epic)
    if oversplit:
        _log.error("[fanout] %s %s", epic_id, oversplit)
        return {"ok": False, "error": oversplit}

    try:
        from executors.registry import normalize_executor
    except Exception:  # pragma: no cover
        def normalize_executor(eid, *, pipeline=""):  # type: ignore
            return (eid or "opencode").strip().lower() or "opencode"

    fallback_exec = normalize_executor(
        default_executor or _epic_default_executor(epic)
    )

    children: list[dict] = []
    seen: set[str] = set()
    for i, raw in enumerate(children_raw):
        ch = _normalize_child(
            raw,
            epic_id=epic_id,
            idx=i,
            max_phases=max_phases,
            workspace=store.workspace,
        )
        if ch["id"] == epic_id:
            raise ValueError("child id must differ from epic")
        if ch["id"] in seen:
            raise ValueError(f"duplicate child id {ch['id']}")
        seen.add(ch["id"])
        children.append(ch)

    color_group = epic.get("color_group") or assign_color_group(
        store.workspace, parent_group=None
    )
    ws = store.workspace
    plan_dir = ws / ".ccc" / "plans"
    phases_dir = ws / ".ccc" / "phases"
    plan_dir.mkdir(parents=True, exist_ok=True)
    phases_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    try:
        for ch in children:
            # 冲突：已存在则改后缀
            cid = ch["id"]
            col_exist, _ = store.find_task(cid)
            if col_exist:
                cid = sanitize_id(f"{cid}-{len(created)+1}")
                ch["id"] = cid
            exec_id = normalize_executor(ch.get("executor") or fallback_exec)
            # complexity 继承 epic（缺省 medium）；禁止因 1 phase 自动标 small（会假绿跳过审测）
            epic_cx = str(epic.get("complexity") or "").strip().lower()
            child_cx = epic_cx if epic_cx in ("small", "sm", "medium", "large") else "medium"
            if child_cx == "sm":
                child_cx = "small"
            task_body: dict[str, Any] = {
                "id": ch["id"],
                "title": ch["title"],
                "description": ch["description"],
                "card_kind": "work",
                "parent_id": epic_id,
                "color_group": color_group,
                "color_depth": 1,
                "complexity": child_cx,
                "executor": exec_id,
            }
            # propagate tags (incl. bump-version) from epic for kb opt-in
            tags = epic.get("tags")
            if isinstance(tags, list) and tags:
                task_body["tags"] = list(tags)
            if ch.get("executor_spec"):
                task_body["executor_spec"] = ch["executor_spec"]
            deps = ch.get("depends_on_tasks") or []
            if deps:
                task_body["depends_on_tasks"] = deps
            ok = store.create_task(task_body, column="planned")
            if not ok:
                raise RuntimeError(f"create_task failed for {ch['id']}")
            created.append(ch["id"])
            (plan_dir / f"{ch['id']}.plan.md").write_text(
                ch["plan_md"], encoding="utf-8"
            )
            phases_body = (
                json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
                + "\n"
                + "\n".join(json.dumps(p, ensure_ascii=False) for p in ch["phases"])
                + "\n"
            )
            (phases_dir / f"{ch['id']}.phases.json").write_text(
                phases_body, encoding="utf-8"
            )
            _log.info(
                "[fanout] %s → child %s (%d phases)%s",
                epic_id,
                ch["id"],
                len(ch["phases"]),
                f" deps={deps}" if deps else "",
            )

        if epic_brief:
            (plan_dir / f"{epic_id}.plan.md").write_text(
                epic_brief, encoding="utf-8"
            )

        if not store.patch_task(
            epic_id,
            {
                "card_kind": "epic",
                "split_status": "planned",
                "color_group": color_group,
                "color_depth": 0,
                "child_ids": created,
                "ui_hidden": False,
            },
        ):
            raise RuntimeError("patch epic failed")
    except Exception:
        # 尽力回滚已创建子卡
        for cid in created:
            for col in ("planned", "backlog", "in_progress"):
                p = ws / ".ccc" / "board" / col / f"{cid}.jsonl"
                if p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            for p in (
                plan_dir / f"{cid}.plan.md",
                phases_dir / f"{cid}.phases.json",
            ):
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
        raise

    # Desktop 右栏：尽力写 fanout 事件（Hub 未启动时静默）
    try:
        from chat_server.services import flow_events as _fe

        works_meta = []
        for cid in created:
            _col, t = store.find_task(cid)
            if t:
                works_meta.append(
                    {
                        "id": cid,
                        "title": t.get("title"),
                        "executor": t.get("executor") or "opencode",
                        "depends_on": t.get("depends_on_tasks") or [],
                        "status": _col or "planned",
                    }
                )
        project_id = _project_id_for_workspace(store.workspace)
        payload = {
            "epic_id": epic_id,
            "works": works_meta,
        }
        if project_id:
            payload["project_id"] = project_id
        _fe.append_event("fanout", payload)
        for w in works_meta:
            ws_payload = {
                "epic_id": epic_id,
                "work_id": w.get("id"),
                "status": w.get("status") or "planned",
                "executor": w.get("executor"),
            }
            if project_id:
                ws_payload["project_id"] = project_id
            _fe.append_event("work_status", ws_payload)
    except Exception:
        pass

    return {"ok": True, "child_ids": created, "color_group": color_group}


_FLOW_PAST_PLANNED = frozenset(
    {"in_progress", "testing", "verified", "released"}
)


def _title_for_seeded_phase(epic: dict, phase: dict, idx: int) -> str:
    desc = str(phase.get("description") or "").strip()
    if desc:
        return desc[:80]
    base = str(epic.get("title") or epic.get("id") or "work").strip()
    return f"{base} · P{idx + 1}"[:80]


def _append_epic_intent_probes(work_plan: str, epic_plan: str) -> str:
    """Phase 切片常丢掉 epic 级 ## 验收探针；补回以免 plan_lint 拒扇出。"""
    try:
        from _intent_probe import extract_probe_commands
    except ImportError:
        return work_plan
    if extract_probe_commands(work_plan or ""):
        return work_plan
    probes = extract_probe_commands(epic_plan or "")
    if not probes:
        return work_plan
    block = "\n".join(f"- {c}" for c in probes)
    text = (work_plan or "").rstrip()
    if re.search(r"^##\s*(验收|验证)\s*$", text, re.M):
        return text + "\n" + block + "\n"
    return text + "\n\n## 验收\n" + block + "\n"


def _plan_md_for_seeded_phase(
    plan_md: str, phase: dict, *, phase_num: int, title: str
) -> str:
    """从 epic plan 切出对应 Phase 段。

    切不到时：**整份 epic plan 下发给 work**（保留原验收/步骤），禁止合成
    「完成本 phase / scope 符合目标」空话——否则 OpenCode 拒写 → SELF-CHECKS 门挂。
    """
    src = plan_md or ""
    # Match ## Phase N / ## Phase N: / ## 阶段 N
    pat = re.compile(
        rf"(^|\n)##\s*(?:Phase|阶段)\s*{re.escape(str(phase_num))}\b[^\n]*\n"
        rf"(.*?)(?=\n##\s*(?:Phase|阶段)\s*\d+\b|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    m = pat.search(src)
    body = ""
    if m:
        body = m.group(2).strip()
    scope = phase.get("scope") or []
    scope_s = ", ".join(str(s) for s in scope if s) or "(见 phase.scope)"
    desc = str(phase.get("description") or title).strip()
    if body:
        # Ensure acceptance section exists
        if not re.search(r"^##\s*(验收|验证)\s*$", body, re.M):
            body = (
                body.rstrip()
                + "\n\n## 验收\n"
                + f"- 完成「{desc}」且 scope 内变更可验证\n"
            )
        return _append_epic_intent_probes(
            f"# Plan: {title}\n\n## 目标\n- {desc}\n\n{body}\n", src
        )

    # 无 ## Phase N：下发完整 epic plan（去掉仅顶层重复标题）
    epic_body = src.strip()
    if epic_body:
        if not re.search(r"^##\s*(验收|验证)\s*$", epic_body, re.M):
            epic_body = (
                epic_body.rstrip()
                + "\n\n## 验收\n"
                + f"- 完成「{desc}」且 scope 内变更可验证\n"
            )
        # 保留 epic 全文；加 work 标题方便定位
        if epic_body.lstrip().startswith("#"):
            return epic_body + "\n"
        return f"# Plan: {title}\n\n{epic_body}\n"

    # 最后兜底（无 epic plan 文本时才合成）
    return (
        f"# Plan: {title}\n\n"
        f"## 目标\n- {desc}\n\n"
        f"## 范围\n- **只改文件**: {scope_s}\n\n"
        f"## 验收\n"
        f"- 完成本 phase：{desc}\n"
        f"- scope 内文件变更符合目标\n"
    )


def _children_from_seeded_phases(
    *,
    epic: dict,
    plan_md: str,
    phases: list[dict],
) -> list[dict]:
    """定稿 seed：每个 phase → 一张 work；后续卡 depends_on_tasks 上一张。"""
    epic_id = epic["id"]
    capped = phases[: max_children()]
    children: list[dict] = []
    prev_id: str | None = None
    for i, ph in enumerate(capped):
        if not isinstance(ph, dict):
            continue
        raw_num = ph.get("phase", i + 1)
        try:
            pnum = int(raw_num)
        except (TypeError, ValueError):
            pnum = i + 1
        wid = f"{epic_id}-w{i + 1}"
        title = _title_for_seeded_phase(epic, ph, i)
        plan_slice = _plan_md_for_seeded_phase(
            plan_md, ph, phase_num=pnum, title=title
        )
        new_ph = {
            k: v
            for k, v in ph.items()
            if k not in ("retry", "commit", "engine_iter", "engine_iter_phase")
        }
        new_ph["phase"] = 1
        new_ph["status"] = "pending"
        new_ph["depends_on"] = []
        if "timeout" not in new_ph:
            new_ph["timeout"] = 1800
        if "subtasks" not in new_ph or not isinstance(new_ph.get("subtasks"), dict):
            new_ph["subtasks"] = {"1.1": "pending"}
        if "scope" not in new_ph or not new_ph["scope"]:
            new_ph["scope"] = ["."]
        child: dict[str, Any] = {
            "id": wid,
            "title": title,
            "description": (
                f"来自 epic {epic_id} · 原 phase {pnum}：{title}"
            )[:8000],
            "plan_md": plan_slice,
            "phases": [new_ph],
        }
        if prev_id:
            child["depends_on_tasks"] = [prev_id]
        children.append(child)
        prev_id = wid
    return children


def fanout_from_seeded_epic(
    store: FileBoardStore,
    epic: dict,
    *,
    max_phases: int = 1,
) -> dict:
    """Hub 定稿投递：epic 已挂 plan+phases 时跳过 Claude。

    每个 phase 扇出一张 work（最多 max_children()）；后续 work 挂
    depends_on_tasks 指向上一张，保证 Engine 按序消费。
    """
    epic = normalize_task_view(epic, column="backlog")
    epic_id = epic["id"]
    if epic.get("card_kind") != "epic":
        return {"ok": False, "error": "not an epic"}
    if epic.get("child_ids"):
        return {"ok": False, "error": "already has children"}
    ws = store.workspace
    plan_path = ws / ".ccc" / "plans" / f"{epic_id}.plan.md"
    phases_path = ws / ".ccc" / "phases" / f"{epic_id}.phases.json"
    if not plan_path.is_file() or not phases_path.is_file():
        return {"ok": False, "error": "missing seed plan/phases"}
    plan_md = plan_path.read_text(encoding="utf-8")
    phases: list[dict] = []
    for line in phases_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "phase" in obj:
            phases.append(obj)
    if not phases:
        return {"ok": False, "error": "seed phases empty"}
    children_raw = _children_from_seeded_phases(
        epic=epic, plan_md=plan_md, phases=phases
    )
    if not children_raw:
        return {"ok": False, "error": "no children from seed phases"}
    result = apply_fanout(
        store,
        epic,
        children_raw=children_raw,
        epic_brief="",
        max_phases=max(1, int(max_phases or 1)),
    )
    if result.get("ok"):
        _log.info(
            "[fanout] seeded epic %s → %d work(s) %s (skip Claude, by-phase)",
            epic_id,
            len(result.get("child_ids") or []),
            result.get("child_ids"),
        )
    return result


def refresh_epic_lifecycle(store: FileBoardStore, epic_id: str) -> str | None:
    """按子卡列推导 epic 五态。返回新状态或 None（非 epic / 不在 backlog）。"""
    col, epic = store.find_task(epic_id)
    if not epic or col != "backlog":
        return None
    epic = normalize_task_view(epic, column="backlog")
    if epic.get("card_kind") != "epic":
        return None
    kids = list(epic.get("child_ids") or [])
    statuses: list[str] = []
    if not kids:
        # 无子卡：保留 failed（product 耗尽后勿每 tick 刷回 pending 空转）
        raw_keep = epic.get("split_status") or "pending"
        if raw_keep == "failed":
            new = "failed"
        elif raw_keep == "done":
            new = "done"
        else:
            new = "pending"
    else:
        for kid in kids:
            # 多副本时取权威列（最远流水线 / abnormal），避免幽灵 in_progress 卡住 epic
            kcol = store.resolve_task_column(kid)
            if kcol is None:
                # 兼容旧路径
                kcol, _ = store.find_task(kid)
            statuses.append(kcol or "missing")
        if any(s == "abnormal" for s in statuses):
            new = "failed"
        elif all(s == "released" for s in statuses):
            new = "done"
        elif all(s == "planned" for s in statuses):
            new = "planned"
        elif any(s in _FLOW_PAST_PLANNED for s in statuses):
            new = "running"
        else:
            # missing / 其它列混排：有 planned 且无流转 → planned，否则 running
            if any(s == "planned" for s in statuses) and not any(
                s in _FLOW_PAST_PLANNED for s in statuses
            ):
                new = "planned"
            else:
                new = "running"
    # 与盘上原始值比较（find_task 已把 active/blocked 归一，不能用来判断是否需写盘）
    raw_ss = None
    try:
        raw_path = store.board / "backlog" / f"{epic_id}.jsonl"
        raw_ss = json.loads(raw_path.read_text(encoding="utf-8").splitlines()[0]).get(
            "split_status"
        )
    except (OSError, json.JSONDecodeError, IndexError):
        raw_ss = epic.get("split_status")
    patch: dict = {}
    if raw_ss != new:
        patch["split_status"] = new
    # done 沉底：自动 ui_hidden，避免 Desktop 侧栏/看板灯把「已完成」当成还在跑
    if new == "done" and not epic.get("ui_hidden"):
        patch["ui_hidden"] = True
    if patch:
        store.patch_task(epic_id, patch)
        _log.info(
            "[fanout] epic %s → %s (was %s, kids=%s)%s",
            epic_id,
            new,
            raw_ss,
            statuses,
            " ui_hidden" if patch.get("ui_hidden") else "",
        )
        # H-1: epic → done 时主动落盘 epic_done（不依赖 SSE 客户端在线）
        if new == "done" and raw_ss != "done":
            try:
                from chat_server.services import flow_events as _fe

                payload: dict[str, Any] = {
                    "epic_id": epic_id,
                    "split_status": "done",
                }
                project_id = _project_id_for_workspace(store.workspace)
                if project_id:
                    payload["project_id"] = project_id
                _fe.append_event("epic_done", payload)
            except Exception as exc:
                _log.warning(
                    "[fanout] epic_done append_event failed for %s: %s",
                    epic_id,
                    exc,
                )
    return new


def refresh_epic_completion(store: FileBoardStore, epic_id: str) -> str | None:
    """兼容旧名 → refresh_epic_lifecycle。"""
    return refresh_epic_lifecycle(store, epic_id)
