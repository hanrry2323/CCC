"""server/board/plans.py — 方案/计划读写模块

方案文件路径：docs/projects/<prefix>/plans/<NNN>-<slug>.md
模板：docs/projects/_template/plan-template.md
校验：scripts/validate-plans.sh

提供：
- 列表：按项目/状态/关键词筛选
- 详情：读取单个方案文件
- 创建：生成编号、写盘、校验
- 更新：改状态/内容
- 转卡：调 new-card.sh 生成任务卡
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("ccc.board.plans")

# 有效状态
VALID_STATES = frozenset({"草案", "已确认", "部分执行", "已完成", "作废"})

# 状态流转白名单（from → allowed to）
_TRANSITIONS: dict[str, frozenset[str]] = {
    "草案": frozenset({"已确认", "作废"}),
    "已确认": frozenset({"部分执行", "作废"}),
    "部分执行": frozenset({"已完成", "作废"}),
    # 已完成 / 作废 = 终态，不可再改
}

# 方案文件路径模式
_PLAN_PATH_RE = re.compile(r"^docs/projects/([a-z]{2,4})/plans/([0-9]{3})-([a-z0-9][-a-z0-9]*)\.md$")

# 方案头部字段提取（匹配 "键：值" 格式）
_FIELD_RE = re.compile(r"([^：]+)：(.+)")


def _extract_header_fields(content: str) -> dict[str, str]:
    """从方案文件头部提取字段。只扫描标题后的连续 > 行块。"""
    fields: dict[str, str] = {}
    lines = content.split("\n")
    in_header = False
    for line in lines[:30]:
        if line.startswith(">"):
            in_header = True
            # 去掉开头的 > 和空格
            text = line.lstrip("> ").strip()
            # 按 · 分割字段
            for segment in text.split("·"):
                segment = segment.strip()
                m = _FIELD_RE.match(segment)
                if m:
                    key = m.group(1).strip()
                    val = m.group(2).strip()
                    # 只取第一次出现的字段（后面的旧状态不覆盖）
                    if key not in fields:
                        fields[key] = val
        elif in_header and not line.startswith(">"):
            # 头部块结束（非 > 行）
            break
    return fields


def _extract_title(content: str) -> str:
    """从方案文件提取标题（# 方案 · ...）。"""
    for line in content.split("\n")[:5]:
        if line.startswith("# 方案"):
            return line.lstrip("# ").strip()
    return ""


def _extract_acceptance(content: str) -> dict[str, int]:
    """提取验收标准完成情况（只统计 checkbox 行，说明文字不计）。"""
    total = 0
    done = 0
    in_section = False
    for line in content.split("\n"):
        if line.strip().startswith("## 验收标准"):
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if in_section:
            m = re.match(r"^\s*[-*]\s+\[([ xX])\]", line)
            if not m:
                continue
            total += 1
            if m.group(1) in ("x", "X"):
                done += 1
    return {"total": total, "done": done}


def _get_valid_prefixes(repo_root: Path) -> set[str]:
    """从 registry.yaml 提取有效前缀。"""
    registry = repo_root / "docs" / "projects" / "registry.yaml"
    if not registry.exists():
        return set()
    prefixes: set[str] = set()
    for line in registry.read_text().split("\n"):
        m = re.match(r"\s+- prefix:\s+(\S+)", line)
        if m:
            p = m.group(1)
            if p != "null":
                prefixes.add(p)
    return prefixes


def list_plans(
    repo_root: Path,
    *,
    project: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """列出所有方案，支持筛选。

    Returns:
        [{id, project, num, slug, title, status, author, tool, created, updated,
          cards, path, acceptance}]
    """
    plans_dir = repo_root / "docs" / "projects"
    results: list[dict[str, Any]] = []

    if not plans_dir.exists():
        return results

    for plan_file in plans_dir.glob("*/plans/[0-9][0-9][0-9]-*.md"):
        rel = str(plan_file.relative_to(repo_root))
        m = _PLAN_PATH_RE.match(rel)
        if not m:
            continue

        prefix = m.group(1)
        num = m.group(2)
        slug = m.group(3)

        if project and prefix != project:
            continue

        try:
            content = plan_file.read_text()
        except OSError:
            continue

        fields = _extract_header_fields(content)
        plan_status = fields.get("状态", "").split("·")[0].strip()

        if status and plan_status != status:
            continue

        title = _extract_title(content)
        if q and q.lower() not in title.lower() and q.lower() not in content[:500].lower():
            continue

        acceptance = _extract_acceptance(content)

        results.append(
            {
                "id": f"{prefix}-plan-{num}",
                "project": prefix,
                "num": num,
                "slug": slug,
                "title": title,
                "status": plan_status,
                "author": fields.get("作者", ""),
                "tool": fields.get("工具", ""),
                "created": fields.get("创建", ""),
                "updated": fields.get("更新", ""),
                "cards": fields.get("关联卡", ""),
                "path": rel,
                "acceptance": acceptance,
            }
        )

    results.sort(key=lambda r: (r["project"], r["num"]))
    return results


def get_plan(repo_root: Path, rel_path: str) -> dict[str, Any] | None:
    """读取单个方案详情。"""
    plan_file = repo_root / rel_path
    if not plan_file.exists():
        return None

    m = _PLAN_PATH_RE.match(rel_path)
    if not m:
        return None

    try:
        content = plan_file.read_text()
    except OSError:
        return None

    fields = _extract_header_fields(content)
    return {
        "id": f"{m.group(1)}-plan-{m.group(2)}",
        "project": m.group(1),
        "num": m.group(2),
        "slug": m.group(3),
        "title": _extract_title(content),
        "status": fields.get("状态", "").split("·")[0].strip(),
        "author": fields.get("作者", ""),
        "tool": fields.get("工具", ""),
        "created": fields.get("创建", ""),
        "updated": fields.get("更新", ""),
        "cards": fields.get("关联卡", ""),
        "related": fields.get("关联方案", ""),
        "path": rel_path,
        "content": content,
        "acceptance": _extract_acceptance(content),
    }


def _next_num(repo_root: Path, prefix: str) -> str:
    """获取下一个可用编号。"""
    plans_dir = repo_root / "docs" / "projects" / prefix / "plans"
    if not plans_dir.exists():
        return "001"
    max_n = 0
    for f in plans_dir.glob("[0-9][0-9][0-9]-*.md"):
        try:
            n = int(f.name[:3])
            if n > max_n:
                max_n = n
        except ValueError:
            continue
    return f"{max_n + 1:03d}"


def _git_commit_push(repo_root: Path, rel_paths: list[str], message: str) -> tuple[bool, str]:
    """对指定文件批量 commit + push；与 convert_plan 同规则（P0/P1 加固：方案文件落 git）。

    Returns:
        (ok, err) — push 失败返回 (False, err) 保留本地 commit，不吞错误、不循环重试。
    """
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "--", *rel_paths],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "push"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()[:500]
        return False, f"commit/push 失败，文件已落盘需手动处理: {detail}"
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"git 操作异常: {exc}"
    logger.info("方案文件已 commit+push: %s", ", ".join(rel_paths))
    return True, ""


def create_plan(
    repo_root: Path,
    *,
    project: str,
    title: str,
    content: str,
    author: str,
    tool: str,
) -> dict[str, Any]:
    """创建新方案文件。

    Returns:
        {ok, path, id} or {error}
    """
    valid_prefixes = _get_valid_prefixes(repo_root)
    if project not in valid_prefixes:
        return {"error": f"无效项目前缀: {project}"}

    if not author or not author.strip():
        return {"error": "作者不能为空"}

    # 并发锁（Fix #9）：编号分配 + 写盘串行化，防两请求同取 next num 互相覆盖。
    lock_f = _acquire_convert_lock(repo_root, project)
    if lock_f is None:
        return {"error": f"{project} 有方案创建/转卡进行中，请稍后重试"}
    try:
        num = _next_num(repo_root, project)
        slug = _title_to_slug(title)
        plans_dir = repo_root / "docs" / "projects" / project / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        plan_id = f"{project}-plan-{num}"

        # 构建完整方案文件
        plan_content = f"""# 方案 · {title}

> 项目：{project} · 编号：{plan_id} · 状态：已确认 · 作者：{author} · 工具：{tool}
> 创建：{today} · 更新：{today}
> 关联卡：无
> 关联方案：无

{content}
"""
        file_path = plans_dir / f"{num}-{slug}.md"
        file_path.write_text(plan_content)

        rel = str(file_path.relative_to(repo_root))

        # 校验
        validate_script = repo_root / "scripts" / "validate-plans.sh"
        if validate_script.exists():
            result = subprocess.run(
                ["bash", str(validate_script), str(file_path)],
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
            if result.returncode != 0:
                # 校验失败，删除文件
                file_path.unlink(missing_ok=True)
                return {"error": f"方案校验失败:\n{result.stderr or result.stdout}"}

        # Fix #8：commit+push 与 convert_plan 同规则
        ok, err = _git_commit_push(repo_root, [rel], f"plans: create {plan_id} — {slug}")
        if not ok:
            return {"ok": True, "path": rel, "id": plan_id, "partial": True, "warning": err}

        return {"ok": True, "path": rel, "id": plan_id}
    finally:
        _release_convert_lock(lock_f, repo_root, project)


def _title_to_slug(title: str) -> str:
    """标题转 slug（简单英文提取，中文 fallback 为 task）。"""
    # 提取英文单词
    english = re.findall(r"[a-zA-Z0-9]+", title)
    if english:
        return "-".join(w.lower() for w in english[:6])
    return "task"


def update_plan(
    repo_root: Path,
    *,
    rel_path: str,
    status: str | None = None,
    content: str | None = None,
    cards: str | None = None,
) -> dict[str, Any]:
    """更新方案状态或内容。

    Returns:
        {ok} or {error}
    """
    plan_file = repo_root / rel_path
    if not plan_file.exists():
        return {"error": "方案文件不存在"}

    if not _PLAN_PATH_RE.match(rel_path):
        return {"error": "无效的方案路径格式"}

    if status and status not in VALID_STATES:
        return {"error": f"无效状态: {status}（须为: {'/'.join(sorted(VALID_STATES))}）"}

    try:
        current = plan_file.read_text()
    except OSError:
        return {"error": "读取方案文件失败"}

    # 状态流转白名单校验
    if status:
        current_fields = _extract_header_fields(current)
        current_status = current_fields.get("状态", "").split("·")[0].strip()
        if current_status in _TRANSITIONS:
            allowed = _TRANSITIONS[current_status]
            if status not in allowed:
                return {"error": f"状态流转非法: {current_status} → {status}（允许: {', '.join(sorted(allowed))}）"}
        elif current_status in ("已完成", "作废"):
            return {"error": f"终态不可修改: {current_status}"}

    today = date.today().isoformat()

    if status:
        # 替换状态字段
        current = re.sub(
            r"(状态：)([^ ·]+)",
            f"\\1{status}",
            current,
            count=1,
        )

    # 更新日期
    current = re.sub(
        r"(更新：)([0-9-]+)",
        f"\\1{today}",
        current,
        count=1,
    )

    if cards is not None:
        # 替换关联卡字段
        if "关联卡：" in current:
            current = re.sub(
                r"(关联卡：)([^\n]*)",
                f"\\1{cards}",
                current,
                count=1,
            )
        else:
            # 如果字段不存在，在头部插入
            lines = current.split("\n")
            # 在关联方案行后插入
            for i, line in enumerate(lines):
                if "关联方案：" in line:
                    lines.insert(i + 1, f"> 关联卡：{cards}")
                    break
            current = "\n".join(lines)

    if content is not None:
        # 替换正文内容（保留头部）
        parts = current.split("\n\n", 2)
        header = "\n\n".join(parts[:2]) if len(parts) >= 2 else current
        current = f"{header}\n\n{content}\n"

    plan_file.write_text(current)

    # Fix #8：commit+push 与 convert_plan 同规则
    ok, err = _git_commit_push(repo_root, [rel_path], f"plans: update {rel_path}")
    if not ok:
        return {"ok": True, "updated": True, "partial": True, "warning": err}

    return {"ok": True, "updated": True}


_CONVERT_LOCK = threading.Lock()


def _acquire_convert_lock(repo_root: Path, prefix: str):
    """同前缀转卡互斥锁（fcntl 文件锁；无 fcntl 环境退化为进程内锁）。"""
    lock_dir = repo_root / "docs" / "projects" / prefix / "plans"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f".convert-{prefix}.lock"
    try:
        import fcntl
    except ImportError:
        if not _CONVERT_LOCK.acquire(blocking=False):
            return None
        return ("thread", None)
    try:
        f = open(lock_path, "w")
    except OSError:
        return None
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return ("fcntl", f)


def _release_convert_lock(handle, repo_root: Path, prefix: str) -> None:
    kind, f = handle
    if kind == "thread":
        _CONVERT_LOCK.release()
        return
    try:
        import fcntl

        fcntl.flock(f, fcntl.LOCK_UN)
    finally:
        f.close()
        lock_path = repo_root / "docs" / "projects" / prefix / "plans" / f".convert-{prefix}.lock"
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _extract_created_card(stdout: str, prefix: str, repo_root: Path) -> tuple[Path, str] | None:
    """从 new-card.sh 输出提取生成的卡文件（路径 + 卡 ID）。"""
    fname_m = re.search(rf"({prefix}\d{{3}}-[a-z0-9][-a-z0-9]*\.md)", stdout)
    if not fname_m:
        return None
    fname = fname_m.group(1)
    path_m = re.search(rf"([^\s]*docs/dispatch/{prefix}/{re.escape(fname)})", stdout)
    if path_m:
        p = Path(path_m.group(1))
        path = p if p.is_absolute() else repo_root / p
    else:
        path = repo_root / "docs" / "dispatch" / prefix / fname
    return path, fname.split("-", 1)[0]


def plan_card_states(repo_root: Path, cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """方案 → 关联卡在看板六列的分布（ccc-plan-024 流程条数据源）。

    cards: 已富化卡列表（含 id / board_column / state）。
    Returns:
        {plan_rel_path: {"total": n, "cols": {"待分派": n, ...}}}
    """
    plans = list_plans(repo_root)
    cards_by_id = {str(c.get("id", "")).lower(): c for c in cards if c.get("id")}
    out: dict[str, dict[str, Any]] = {}
    col_keys = ("待分派", "执行中", "机审", "已回写", "打回", "已关闭")
    for p in plans:
        ref = re.findall(r"([a-zA-Z]+[0-9]+)", p.get("cards") or "")
        cols = {k: 0 for k in col_keys}
        for cid in ref:
            c = cards_by_id.get(cid.lower())
            col = str((c or {}).get("board_column") or (c or {}).get("state") or "待分派")
            cols[col] = cols.get(col, 0) + 1
        out[p["path"]] = {"total": len(ref), "cols": cols}
    return out


def _rollback_created(files: list[Path]) -> None:
    """删除本轮已生成的卡文件（转卡失败时回滚，保证重试不产生重复卡）。"""
    for p in files:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


def convert_plan(
    repo_root: Path,
    *,
    rel_path: str,
    no_push: bool = False,
) -> dict[str, Any]:
    """将方案转为任务卡。

    1. 读取方案的「转卡计划」段
    2. 调 new-card.sh 生成任务卡（全部成功才推进状态；失败回滚已生成卡）
    3. 自动推进方案状态为「部分执行」+ 写入关联卡
    4. 默认 commit+push 到远端（no_push=True 供测试/无 git 环境跳过）

    Returns:
        {ok, cards: [card_id]} or {error}
    """
    plan_file = repo_root / rel_path
    if not plan_file.exists():
        return {"error": "方案文件不存在"}

    m = _PLAN_PATH_RE.match(rel_path)
    if not m:
        return {"error": "无效的方案路径格式"}

    prefix = m.group(1)

    # 红线（2026-08-10）：禁出卡前缀（如 ccc 平台自研）禁止转卡，方案仍可存在与查看
    try:
        from server.board.registry import forbidden_prefixes

        if prefix in forbidden_prefixes(str(repo_root / "docs" / "projects" / "registry.yaml")):
            return {"error": f"项目 {prefix} 为禁出卡前缀（平台自研红线），禁止转卡"}
    except Exception:
        pass

    # 并发锁：同前缀同时只允许一个转卡，防重复出卡
    lock_f = _acquire_convert_lock(repo_root, prefix)
    if lock_f is None:
        return {"error": f"{prefix} 有转卡进行中，请稍后重试"}
    try:
        return _convert_plan_locked(repo_root, rel_path=rel_path, prefix=prefix, no_push=no_push)
    finally:
        _release_convert_lock(lock_f, repo_root, prefix)


def _convert_plan_locked(
    repo_root: Path,
    *,
    rel_path: str,
    prefix: str,
    no_push: bool,
) -> dict[str, Any]:
    m = _PLAN_PATH_RE.match(rel_path)
    plan_file = repo_root / rel_path
    try:
        content = plan_file.read_text()
    except OSError:
        return {"error": "读取方案文件失败"}

    # 状态检查：只允许已确认/部分执行转卡
    current_fields = _extract_header_fields(content)
    current_status = current_fields.get("状态", "").split("·")[0].strip()
    if current_status not in ("已确认", "部分执行"):
        return {"error": f"当前状态「{current_status}」不可转卡，只有「已确认」或「部分执行」状态可以转卡"}

    # 提取转卡计划
    plan_section = ""
    in_section = False
    for line in content.split("\n"):
        if line.strip().startswith("## 转卡计划"):
            in_section = True
            continue
        if in_section and line.strip().startswith("##"):
            break
        if in_section:
            plan_section += line + "\n"

    if not plan_section.strip():
        return {"error": "方案缺少「转卡计划」段"}

    # 转卡计划段限 8 行
    plan_lines = [ln for ln in plan_section.strip().split("\n") if ln.strip() and not ln.strip().startswith("#")]
    if len(plan_lines) > 8:
        return {"error": f"转卡计划段最多 8 行，当前 {len(plan_lines)} 行"}

    # 提取标题（方案标题去掉「方案 · 」前缀）
    title = _extract_title(content).removeprefix("方案 · ").strip()

    new_card_script = repo_root / "scripts" / "new-card.sh"
    if not new_card_script.exists():
        return {"error": "new-card.sh 不存在"}

    created_files: list[Path] = []
    cards: list[str] = []

    # 按行拆分转卡计划，每行作为一张卡的标题
    for line in plan_section.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 清理 markdown 列表标记
        card_title = re.sub(r"^[-*]\s*|^\d+\.\s*", "", line).strip()
        if not card_title:
            continue

        full_title = f"{title} — {card_title}"
        result = subprocess.run(
            ["bash", str(new_card_script), "--project", prefix, "--title", full_title],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )

        if result.returncode != 0:
            _rollback_created(created_files)
            return {
                "error": f"出卡失败: {card_title}\n{result.stderr or result.stdout}",
                "cards": cards,
            }

        created = _extract_created_card(result.stdout, prefix, repo_root)
        if created is None:
            _rollback_created(created_files)
            return {
                "error": f"出卡成功但无法解析卡文件路径: {card_title}\n{result.stdout}",
                "cards": cards,
            }
        created_files.append(created[0])
        cards.append(created[1])

    # 自动推进状态为「部分执行」+ 写入关联卡
    today = date.today().isoformat()
    card_list = ", ".join(cards) if cards else "无"
    current = plan_file.read_text()

    # 更新状态
    current = re.sub(r"(状态：)([^ ·]+)", r"\1部分执行", current, count=1)
    # 更新日期
    current = re.sub(r"(更新：)([0-9-]+)", f"\\1{today}", current, count=1)
    # 更新关联卡
    current = re.sub(r"(关联卡：)([^\n]*)", f"\\1{card_list}", current, count=1)

    plan_file.write_text(current)

    if no_push:
        return {"ok": True, "cards": cards}

    # commit+push：卡文件与方案状态同批提交，Engine 才能感知新卡
    rel_paths = [str(p.relative_to(repo_root)) for p in created_files] + [rel_path]
    plan_id = f"{prefix}-plan-{m.group(2)}"
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "--", *rel_paths],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "commit",
                "-m",
                f"cards: convert-plan {plan_id} ({len(cards)} slices)",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "push"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "error": f"卡已生成并推进方案状态，但提交/推送失败，需手动推送: {exc.stderr or exc.stdout}",
            "cards": cards,
            "partial": True,
        }

    return {"ok": True, "cards": cards}
