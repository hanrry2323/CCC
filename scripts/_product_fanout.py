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


def max_children() -> int:
    return max(1, min(MAX_CHILDREN, 16))


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
        f"- description: {epic.get('description', '')}\n\n"
        f"## 子卡约束\n"
        f"- 拆出 1–{max_children()} 张子卡（宁多勿巨型）\n"
        f"- 每张子卡最多 {max_phases} 个 phase（优先 1 个）\n"
        f"- 子卡 id：kebab-case，建议前缀 `{eid}-`\n"
        f"- 每张子卡必须可独立被开发模型消费（目标清晰、scope 明确）\n"
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
    raw: dict, *, epic_id: str, idx: int, max_phases: int
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
    ok, errs, _ = phase_lint.validate_phases_dict(phases)
    if not ok:
        raise ValueError(f"child[{idx}] phase_lint: {'; '.join(errs)}")
    pok, perrs = phase_lint.validate_plan_acceptance(plan_md)
    if not pok:
        raise ValueError(f"child[{idx}] plan_lint: {'; '.join(perrs)}")
    return {
        "id": cid,
        "title": title[:500],
        "description": str(raw.get("description") or "")[:10000],
        "plan_md": plan_md,
        "phases": phases,
    }


def apply_fanout(
    store: FileBoardStore,
    epic: dict,
    *,
    children_raw: list[dict],
    epic_brief: str = "",
    max_phases: int = 2,
) -> dict:
    """校验并落盘子卡；更新 epic。成功返回 {ok, child_ids, color_group}。"""
    epic = normalize_task_view(epic, column="backlog")
    epic_id = epic["id"]
    if epic.get("card_kind") != "epic":
        return {"ok": False, "error": "not an epic"}
    if epic.get("split_status") not in ("pending", "blocked", None, ""):
        # active 允许重拆仅当 child_ids 空（异常恢复）
        if epic.get("split_status") == "active" and epic.get("child_ids"):
            return {"ok": False, "error": "epic already split (active)"}

    children: list[dict] = []
    seen: set[str] = set()
    for i, raw in enumerate(children_raw):
        ch = _normalize_child(
            raw, epic_id=epic_id, idx=i, max_phases=max_phases
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
            ok = store.create_task(
                {
                    "id": ch["id"],
                    "title": ch["title"],
                    "description": ch["description"],
                    "card_kind": "work",
                    "parent_id": epic_id,
                    "color_group": color_group,
                    "color_depth": 1,
                    "complexity": "small" if len(ch["phases"]) <= 1 else "medium",
                },
                column="planned",
            )
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
                "[fanout] %s → child %s (%d phases)",
                epic_id,
                ch["id"],
                len(ch["phases"]),
            )

        if epic_brief:
            (plan_dir / f"{epic_id}.plan.md").write_text(
                epic_brief, encoding="utf-8"
            )

        if not store.patch_task(
            epic_id,
            {
                "card_kind": "epic",
                "split_status": "active",
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

    return {"ok": True, "child_ids": created, "color_group": color_group}


def refresh_epic_completion(store: FileBoardStore, epic_id: str) -> str | None:
    """根据子卡列状态更新 epic split_status。返回新状态或 None。"""
    col, epic = store.find_task(epic_id)
    if not epic or col != "backlog":
        return None
    epic = normalize_task_view(epic, column="backlog")
    if epic.get("card_kind") != "epic":
        return None
    kids = list(epic.get("child_ids") or [])
    if not kids:
        return None
    statuses: list[str] = []
    for kid in kids:
        kcol, _ = store.find_task(kid)
        statuses.append(kcol or "missing")
    if any(s == "abnormal" for s in statuses):
        new = "blocked"
    elif all(s == "released" for s in statuses):
        new = "done"
    else:
        new = "active"
    if epic.get("split_status") != new:
        store.patch_task(epic_id, {"split_status": new})
        _log.info("[fanout] epic %s → %s (kids=%s)", epic_id, new, statuses)
    return new
