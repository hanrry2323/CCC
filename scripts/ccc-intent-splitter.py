#!/usr/bin/env python3
"""ccc-intent-splitter.py — Claude 后台拆卡程序（无记忆 · 2017 端）。

契约：docs/product/ccc-new-architecture-overview.md 四层分工第 2 层。
- 消费业务仓 `.ccc/intent-proposals/<proposal_id>.md` 方案文件
- 复用 _product_fanout + _product_session 拆卡
- 每张子卡附 skill_ref@<hash> / prompt_ref@<hash>
- apply_fanout 落盘 work 子卡到 planned
- wake Engine 消费
- 写审计日志到 `<proposal_id>.result.jsonl`

配置家隔离：CLAUDE_CONFIG_DIR=~/.ccc/intent-splitter（与 engine-claude 隔离，无记忆）

Usage:
  ccc-intent-splitter --proposal <proposal_id> --project <project_id>
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_log = logging.getLogger("ccc.intent_splitter")

# scripts/ 目录入 sys.path（复用 _product_fanout / _product_session / _board_store 等）
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# 平台仓根（references/ 库所在）
CCC_ROOT = SCRIPTS_DIR.parent
REFERENCES_DIR = CCC_ROOT / "references"

LOCK_FILE = Path.home() / ".ccc" / "intent-splitter.lock"
DEFAULT_MAX_PHASES = 2

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONT_RE.match(text.strip() + ("\n" if not text.endswith("\n") else ""))
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta, (m.group(2) or "").strip()


def _resolve_workspace(project_id: str) -> Path:
    """从 CCC_TARGET_WORKSPACE 或 _workspace_registry 解析业务仓路径。"""
    env_ws = os.environ.get("CCC_TARGET_WORKSPACE", "").strip()
    if env_ws:
        return Path(env_ws).expanduser().resolve()
    # 回退：从 _workspace_registry 按 project_id 查
    try:
        from _workspace_registry import list_registered_entries
        for entry in list_registered_entries():
            name = (entry.get("name") or "").lower().replace(" ", "-")
            if name == project_id.lower():
                return Path(entry["path"]).resolve()
    except Exception as exc:
        _log.warning("resolve_workspace registry: %s", exc)
    # 最终回退：~/program/apps/<project_id>
    fallback = Path.home() / "program" / "apps" / project_id
    return fallback


def _read_proposal(workspace: Path, proposal_id: str) -> dict:
    """读方案文件，返回 epic dict（含 title/goal/acceptance/plan_md/skill_ref/prompt_ref）。"""
    path = workspace / ".ccc" / "intent-proposals" / f"{proposal_id}.md"
    if not path.is_file():
        raise FileNotFoundError(f"方案文件不存在: {path}")
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    # 解析 4 节（目标/范围/步骤概要/验收意图）— 简化为 title + body 作为 description
    title = meta.get("title") or proposal_id
    skill_ref = meta.get("skill_ref") or "skills/write-code"
    prompt_ref = meta.get("prompt_ref") or "prompts/write-code-prompt"
    project_id = meta.get("project_id") or ""
    # body 即方案正文（4 节）；作为 epic description + plan_md
    return {
        "proposal_id": proposal_id,
        "project_id": project_id,
        "title": title[:80],
        "description": body[:2000],
        "goal": body.split("\n\n")[0][:500] if body else title,
        "plan_md": body,
        "skill_ref": skill_ref,
        "prompt_ref": prompt_ref,
        "meta": meta,
    }


def _build_profile(workspace: Path) -> str:
    """读业务仓 profile.md / AGENTS.md 作为项目概况。"""
    for name in (".ccc/profile.md", "AGENTS.md", "profile.md", "README.md"):
        p = workspace / name
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")[:1500]
            except OSError:
                continue
    return f"（无 profile；workspace={workspace}）"


_DEFAULT_TEMPLATE_PLAN = """# Plan

## 目标
<一句话目标>

## Phase 1 — <模块>
- `path/to/file.py`

## 验收
- DRY_RUN=true python3 -c "assert True"
"""


def _skill_commit_hash(ref_path: str) -> str:
    """读 references/ 库 HEAD 的 7 位 commit hash。"""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=str(REFERENCES_DIR),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode == 0:
            return r.stdout.strip()[:7]
    except Exception as exc:
        _log.debug("skill_commit_hash: %s", exc)
    return ""


def _attach_skill_version(
    store,
    child_ids: list[str],
    skill_ref: str,
    prompt_ref: str,
) -> int:
    """给每张子卡附 skill_ref@<hash> / prompt_ref@<hash>（patch_task note）。"""
    h = _skill_commit_hash(skill_ref)
    tagged = 0
    skill_ref_versioned = f"{skill_ref}@{h}" if h else skill_ref
    prompt_ref_versioned = f"{prompt_ref}@{h}" if h else prompt_ref
    for cid in child_ids:
        try:
            col, task = store.find_task(cid)
            if not task:
                continue
            note_raw = task.get("note") or ""
            note_data = {}
            if isinstance(note_raw, str) and note_raw.strip().startswith("{"):
                try:
                    note_data = json.loads(note_raw)
                except json.JSONDecodeError:
                    note_data = {}
            tg = note_data.get("transfer_gate") or {}
            tg["skill_ref"] = skill_ref_versioned
            tg["prompt_ref"] = prompt_ref_versioned
            note_data["transfer_gate"] = tg
            store.patch_task(cid, {"note": json.dumps(note_data, ensure_ascii=False)[:2000]})
            # 更新 tags 加 skill:<ref>
            tags = task.get("tags") or []
            tags = [t for t in tags if not str(t).startswith("skill:")]
            tags.append(f"skill:{skill_ref}")
            store.patch_task(cid, {"tags": tags})
            tagged += 1
        except Exception as exc:
            _log.warning("attach_skill_version %s: %s", cid, exc)
    return tagged


def _append_audit(workspace: Path, proposal_id: str, event: dict) -> None:
    """追加事件到 <proposal_id>.result.jsonl。"""
    d = workspace / ".ccc" / "intent-proposals"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{proposal_id}.result.jsonl"
    line = json.dumps({**event, "ts": event.get("ts") or _now_iso()}, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _extract_scope_from_md(md: str) -> list[str]:
    """从 `# 范围` / `## 范围` 节解析目标文件路径列表。"""
    if not md:
        return []
    lines = md.splitlines()
    in_scope = False
    paths: list[str] = []
    for line in lines:
        s = line.strip()
        low = s.lstrip("#").strip().lower()
        if s.startswith("#"):
            in_scope = low in ("范围", "scope", "目标文件")
            continue
        if not in_scope:
            continue
        item = s.lstrip("-*").strip().strip("`").strip()
        if not item or item.startswith(("http", "#", "--")):
            continue
        # 提取文件路径（排除说明文字）
        m = re.search(r"([A-Za-z0-9_./\-]+\.(?:py|md|sh|json|yaml|yml|txt|toml))", item)
        if m:
            paths.append(m.group(1).lstrip("./"))
    return paths


def _extract_paths_from_acceptance(md: str) -> list[str]:
    """从验收命令里提取涉及的产物路径（兜底）。"""
    if not md:
        return []
    acc_section = []
    in_acc = False
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("#"):
            in_acc = s.lstrip("#").strip() in ("验收", "验证")
            continue
        if in_acc:
            acc_section.append(line)
    scope: list[str] = []
    for line in acc_section:
        for m in re.finditer(r"([A-Za-z0-9_./\-]+\.py)", line):
            p = m.group(1).lstrip("./")
            if p not in scope:
                scope.append(p)
    return scope


def _run_fanout(store, epic: dict, workspace: Path, proposal_id: str) -> dict:
    """调 Claude 拆卡 + apply_fanout 落盘。返回 {ok, child_ids, error}。

    SDK 不可用时 fallback：直接从方案 plan_md 创建单张 work 子卡。
    """
    from _product_fanout import apply_fanout, build_fanout_prompt, parse_fanout_output
    from _product_session import run_contract_loop_sync

    profile = _build_profile(workspace)
    prompt = build_fanout_prompt(
        epic=epic,
        workspace=workspace,
        profile=profile,
        code_ctx="",
        template_plan=_DEFAULT_TEMPLATE_PLAN,
        ref_plans="",
        max_phases=DEFAULT_MAX_PHASES,
    )

    def _validate_epic(text: str) -> None:
        parse_fanout_output(text)

    def _gate_epic(text: str):
        _brief, children = parse_fanout_output(text)
        return text, (_brief, children)

    task_id = epic["id"]
    sess = run_contract_loop_sync(
        prompt=prompt,
        workspace=workspace,
        task_id=task_id,
        mode="epic",
        model="flash",
        validate_fn=_validate_epic,
        gate_fn=_gate_epic,
    )
    if not sess.get("ok"):
        # fallback：SDK 不可用时直接创建单张 work 子卡
        _log.warning(
            "splitter SDK 不可用 (%s)，走 fallback 单 phase 拆卡",
            sess.get("error", "")[:80],
        )
        return _fallback_create_work(store, epic, workspace, proposal_id)

    _brief, children = parse_fanout_output(sess.get("output") or "")
    fr = apply_fanout(
        store,
        epic,
        children_raw=children,
        epic_brief=_brief,
        max_phases=DEFAULT_MAX_PHASES,
    )
    if not fr.get("ok"):
        return {"ok": False, "error": fr.get("error") or "fanout failed"}
    return {
        "ok": True,
        "child_ids": fr.get("child_ids") or [],
        "claude_session_id": sess.get("claude_session_id") or "",
    }


def _fallback_create_work(
    store,
    epic: dict,
    workspace: Path,
    proposal_id: str,
) -> dict:
    """SDK 不可用时 fallback：从方案 plan_md 直接创建单张 work 子卡。

    绕过 apply_fanout，直接 create_task 到 planned 列。
    必须生成 .ccc/plans/<tid>.plan.md + .ccc/phases/<tid>.phases.json，
    否则 Engine dispatch.try_launch_planned 会跳过（缺 plan/phases 文件）。
    """
    epic_id = epic["id"]
    work_id = f"{epic_id}-w1"
    title = epic.get("title") or proposal_id
    description = epic.get("description") or epic.get("plan_md") or ""
    plan_md = epic.get("plan_md") or description
    skill_ref = ""
    prompt_ref = ""
    note_raw = epic.get("note") or ""
    if isinstance(note_raw, str) and note_raw.strip().startswith("{"):
        try:
            note_data = json.loads(note_raw)
            tg = note_data.get("transfer_gate") or {}
            skill_ref = tg.get("skill_ref") or ""
            prompt_ref = tg.get("prompt_ref") or ""
        except json.JSONDecodeError:
            pass

    work_data = {
        "id": work_id,
        "title": title[:80],
        "description": description[:1500],
        "card_kind": "work",
        "complexity": "medium",  # 与 product role fanout 一致，避免被跳过
        "parent_id": epic_id,
        "note": json.dumps({
            "transfer_gate": {
                "skill_ref": skill_ref,
                "prompt_ref": prompt_ref,
                "pipeline": "dev",
                "feasibility": "ok",
                "source": "intent-splitter-fallback",
            },
            "fallback": True,
        }, ensure_ascii=False)[:2000],
        "tags": ["intent-proposal", "fallback", f"proposal:{proposal_id}"],
    }
    if not store.create_task(work_data, column="planned"):
        col, existing = store.find_task(work_id)
        if not existing:
            return {"ok": False, "error": f"fallback create work failed: {work_id}"}

    # 从方案 # 范围 解析目标文件路径 → phases scope（产物确定性）
    scope = _extract_scope_from_md(plan_md)
    if not scope:
        # 兜底：从验收命令里找文件路径
        scope = _extract_paths_from_acceptance(plan_md)

    # 生成 plan + phases 文件（Engine dispatch 必需）
    plan_dir = workspace / ".ccc" / "plans"
    phases_dir = workspace / ".ccc" / "phases"
    plan_dir.mkdir(parents=True, exist_ok=True)
    phases_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / f"{work_id}.plan.md").write_text(plan_md, encoding="utf-8")
    # phases 格式：第一行 schema_version，后续每行一个 phase JSON
    phase = {
        "phase": 1,
        "status": "pending",
        "description": title[:200],
        "scope": scope,
        "subtasks": {f"1.{i+1}": f"created {s}" for i, s in enumerate(scope)},
        "timeout": 300,
        "commit": None,
        "notes": "intent-splitter-fallback",
    }
    phases_body = (
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + json.dumps(phase, ensure_ascii=False)
        + "\n"
    )
    (phases_dir / f"{work_id}.phases.json").write_text(phases_body, encoding="utf-8")
    _log.info("[splitter-fallback] %s plan+phases 已生成", work_id)

    # 更新 epic child_ids + split_status
    try:
        store.patch_task(epic_id, {
            "child_ids": [work_id],
            "split_status": "planned",
        })
    except Exception as exc:
        _log.warning("fallback patch epic %s: %s", epic_id, exc)

    return {
        "ok": True,
        "child_ids": [work_id],
        "claude_session_id": "",
        "fallback": True,
    }


def main(proposal_id: str, project_id: str) -> dict:
    """主流程：读方案 → 创建 epic → fanout → 附 skill_ref → wake engine → 审计。"""
    # 单实例保护
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        _log.warning("splitter 已在运行，跳过 proposal=%s", proposal_id)
        return {"ok": False, "error": "splitter_busy"}

    workspace = _resolve_workspace(project_id)
    if not workspace.is_dir():
        msg = f"workspace 不存在: {workspace}"
        _append_audit(workspace, proposal_id, {"status": "failed", "error": msg})
        return {"ok": False, "error": msg}

    try:
        _t0 = time.monotonic()
        _append_audit(workspace, proposal_id, {
            "status": "running",
            "project_id": project_id,
            "workspace": str(workspace),
        })

        # 1. 读方案
        try:
            _t1 = time.monotonic()
            prop = _read_proposal(workspace, proposal_id)
            read_ms = int((time.monotonic() - _t1) * 1000)
        except Exception as exc:
            _append_audit(workspace, proposal_id, {"status": "failed", "error": str(exc)})
            return {"ok": False, "error": str(exc)}

        # 2. 创建 epic 卡到 backlog
        from _board_store import FileBoardStore

        _t2 = time.monotonic()
        store = FileBoardStore(workspace)
        epic_id = f"{proposal_id}-epic"
        skill_ref = prop["skill_ref"]
        prompt_ref = prop["prompt_ref"]
        note = json.dumps({
            "transfer_gate": {
                "skill_ref": skill_ref,
                "prompt_ref": prompt_ref,
                "pipeline": "dev",
                "feasibility": "ok",
                "source": "intent-splitter",
            }
        }, ensure_ascii=False)
        epic_data = {
            "id": epic_id,
            "title": prop["title"],
            "description": prop["description"],
            "card_kind": "epic",
            "split_status": "pending",
            "complexity": "medium",
            "note": note[:2000],
            "tags": ["intent-proposal", f"skill:{skill_ref}", f"proposal:{proposal_id}"],
        }
        if not store.create_task(epic_data, column="backlog"):
            # 可能已存在（重试）；尝试 find
            col, existing = store.find_task(epic_id)
            if not existing:
                msg = f"create epic failed: {epic_id}"
                _append_audit(workspace, proposal_id, {"status": "failed", "error": msg})
                return {"ok": False, "error": msg}

        # 3. 读取已创建的 epic（apply_fanout 需要完整 task dict）
        _col, epic_task = store.find_task(epic_id)
        if not epic_task:
            msg = f"epic not found after create: {epic_id}"
            _append_audit(workspace, proposal_id, {"status": "failed", "error": msg})
            return {"ok": False, "error": msg}

        # 4. fanout 拆卡
        _t3 = time.monotonic()
        fr = _run_fanout(store, epic_task, workspace, proposal_id)
        fanout_ms = int((time.monotonic() - _t3) * 1000)
        if not fr.get("ok"):
            _append_audit(workspace, proposal_id, {
                "status": "failed",
                "error": fr.get("error") or "fanout failed",
                "timing_ms": {"read": read_ms, "fanout": fanout_ms},
            })
            return {"ok": False, "error": fr.get("error")}

        child_ids = fr.get("child_ids") or []

        # 5. 给子卡附 skill_ref@<hash>
        _t4 = time.monotonic()
        tagged = _attach_skill_version(store, child_ids, skill_ref, prompt_ref)
        attach_ms = int((time.monotonic() - _t4) * 1000)

        # 6. wake engine
        _t5 = time.monotonic()
        try:
            from _engine_wake import ensure_engine_for_task
            ensure_engine_for_task(
                reason=f"intent-splitter:{proposal_id}",
                task_id=epic_id,
                workspace=workspace,
                workspace_name=project_id,
            )
        except Exception as exc:
            _log.warning("wake engine: %s", exc)
        wake_ms = int((time.monotonic() - _t5) * 1000)

        # 7. 审计完成（含阶段耗时埋点）
        total_ms = int((time.monotonic() - _t0) * 1000)
        _append_audit(workspace, proposal_id, {
            "status": "ok",
            "cards_produced": len(child_ids),
            "child_ids": child_ids,
            "epic_id": epic_id,
            "claude_session_id": fr.get("claude_session_id") or "",
            "skill_ref": skill_ref,
            "prompt_ref": prompt_ref,
            "fallback": bool(fr.get("fallback")),
            "tagged_cards": tagged,
            "timing_ms": {
                "read": read_ms,
                "create_epic": int((time.monotonic() - _t2) * 1000),
                "fanout": fanout_ms,
                "attach": attach_ms,
                "wake": wake_ms,
                "total": total_ms,
            },
        })
        return {
            "ok": True,
            "cards_produced": len(child_ids),
            "child_ids": child_ids,
            "epic_id": epic_id,
            "error": "",
            "claude_session_id": fr.get("claude_session_id") or "",
        }
    except Exception as exc:
        _log.error("splitter main: %s", exc, exc_info=True)
        try:
            _append_audit(workspace, proposal_id, {"status": "failed", "error": str(exc)})
        except Exception:
            pass
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
            lock_fp.close()
        except Exception:
            pass


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Claude 后台拆卡程序（无记忆）")
    parser.add_argument("--proposal", required=True, help="proposal_id")
    parser.add_argument("--project", required=True, help="project_id")
    args = parser.parse_args()

    logging.basicConfig(
        level=os.environ.get("CCC_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    result = main(args.proposal, args.project)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(_cli())
