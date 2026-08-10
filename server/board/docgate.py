from __future__ import annotations

import re
import subprocess
from pathlib import Path

from server.board.card_header import parse_metadata, card_id


def _extract_header_fields(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = content.split("\n")
    in_header = False
    for line in lines[:30]:
        if line.startswith(">"):
            in_header = True
            fields.update(parse_metadata(line))
        elif in_header and not line.startswith(">"):
            break
    return fields


def get_card_id(card_path: Path) -> str:
    try:
        text = card_path.read_text(encoding="utf-8")
        cid = card_id(text)
        if cid:
            return cid
    except Exception:
        pass
    return card_path.stem


def _read_plan_from_repo(repo_root: Path, path: str) -> str | None:
    """读方案文件内容：优先分支 worktree 文件，缺失/旧时回退 origin/main（平台文档权威源）。

    Doc-Gate 修正（2026-08-10）：方案是平台侧文档，在 main 演进；执行体分支可能不含或含旧版。
    Q1 校验方案关联卡/状态应基于 main 权威版本，而非分支快照（避免 clw008-012 死结）。
    """
    fp = repo_root / path
    if fp.is_file():
        try:
            return fp.read_text(encoding="utf-8")
        except Exception:
            pass
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"origin/main:{path}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if res.returncode == 0 and res.stdout:
            return res.stdout
    except Exception:
        pass
    return None


def extract_paths(note: str) -> list[str]:
    candidates = re.findall(r"[a-zA-Z0-9_/.-]+", note)
    return [c for c in candidates if "/" in c or "." in c]


def get_modified_files(repo_root: Path, card_file: Path | None = None) -> list[str]:
    base_ref = "origin/main"
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", "origin/main"],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError:
        base_ref = "main"

    # Determine branch to check
    branch_ref = None
    card_id = None
    if card_file:
        try:
            card_id = get_card_id(card_file)
            stem = card_file.stem
            # Resolve branch ref in order of preference
            for b in [f"origin/codex/{stem}", f"codex/{stem}"]:
                try:
                    subprocess.run(
                        ["git", "show-ref", "--verify", f"refs/remotes/{b}" if b.startswith("origin/") else f"refs/heads/{b}"],
                        cwd=repo_root,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                    branch_ref = b
                    break
                except Exception:
                    pass
            if not branch_ref:
                # If verify failed, try with rev-parse
                for b in [f"origin/codex/{stem}", f"codex/{stem}"]:
                    try:
                        subprocess.run(
                            ["git", "rev-parse", "--verify", b],
                            cwd=repo_root,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True,
                        )
                        branch_ref = b
                        break
                    except Exception:
                        pass
        except Exception:
            pass

    if branch_ref:
        # Check if branch_ref is already merged into base_ref (ancestor check)
        is_merged = False
        try:
            res_merged = subprocess.run(
                ["git", "merge-base", "--is-ancestor", branch_ref, base_ref],
                cwd=repo_root,
                capture_output=True,
                check=False
            )
            if res_merged.returncode == 0:
                is_merged = True
        except Exception:
            pass

        diff_target = None
        if is_merged and card_id:
            try:
                # Find commits on branch_ref containing the card_id in the message
                res_commits = subprocess.run(
                    ["git", "log", branch_ref, f"--grep={card_id}", "--format=%H"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=True
                )
                commits = [c.strip() for c in res_commits.stdout.splitlines() if c.strip()]
                if commits:
                    oldest_commit = commits[-1]
                    diff_target = f"{oldest_commit}^..{branch_ref}"
                else:
                    diff_target = f"{branch_ref}^..{branch_ref}"
            except Exception:
                diff_target = f"{branch_ref}^..{branch_ref}"
        else:
            try:
                res_mb = subprocess.run(
                    ["git", "merge-base", base_ref, branch_ref],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=True
                )
                mb = res_mb.stdout.strip()
                diff_target = f"{mb}..{branch_ref}"
            except Exception:
                diff_target = f"{base_ref}...{branch_ref}"

        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", diff_target],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            pass

    try:
        res = subprocess.run(
            ["git", "diff", "--name-only", base_ref], cwd=repo_root, capture_output=True, text=True, check=True
        )
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def parse_maintenance_section(text: str) -> dict[int, dict[str, str]]:
    m = re.search(r"^## 维护区\s*$", text, re.M)
    if not m:
        return {}
    seg = text[m.end() :]
    seg = seg.split("## ", 1)[0]

    results = {}
    for num in (1, 2, 3, 4):
        item_m = re.search(rf"^\s*{num}\.\s+\*\*([^*]+)\*\*：[^\[]*\[([^]]*)\]", seg, re.M)
        if not item_m:
            continue
        name = item_m.group(1).strip()
        choice = item_m.group(2).strip()

        start_idx = item_m.end()
        sub_seg = seg[start_idx:]
        note_m = re.search(r"^\s+-\s+说明：\s*(.*)$", sub_seg, re.M)
        note = note_m.group(1).strip() if note_m else ""

        results[num] = {"name": name, "choice": choice, "note": note}
    return results


def verify_maintenance(card_path: str | Path, repo_root: str | Path) -> tuple[bool, list[str]]:
    card_path = Path(card_path)
    repo_root = Path(repo_root)

    if not card_path.is_absolute():
        card_file = repo_root / card_path
    else:
        card_file = card_path

    if not card_file.exists():
        return False, [f"任务卡不存在: {card_path}"]

    try:
        text = card_file.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"读取任务卡失败: {e}"]

    meta = parse_metadata(text)
    state = meta.get("状态", "")
    if "已关闭" in state or "作废" in state:
        return True, []

    if "## 维护区" not in text:
        return False, ["完成钩子：卡缺 ## 维护区 节（模板已含，回写时必填四问）"]

    parsed = parse_maintenance_section(text)
    if len(parsed) < 4:
        return False, [f"完成钩子：维护区只找到 {len(parsed)}/4 问"]

    problems = []

    for num in (1, 2, 3, 4):
        item = parsed.get(num)
        if not item:
            problems.append(f"第 {num} 问缺失")
            continue
        choice = item["choice"].strip("[]").strip()
        note = item["note"].strip()

        if choice not in ("是", "否", "有", "无"):
            problems.append(f"第 {num} 问「{item['name']}」未正确勾选（当前值为: {item['choice']!r}）")
            continue

        if not note or note == "" or note == "说明：" or note == "说明: " or note.startswith("<"):
            problems.append("存在空「说明」（必须写一句实情）")
            continue

        if num == 1 and choice in ("`是`", "是"):
            card_id = get_card_id(card_file)
            related = meta.get("关联", "")
            plan_m = re.search(r"([a-z]{2,4})-plan-([0-9]{3})", related)
            if not plan_m:
                problems.append("Q1 声明了方案同步[是]，但卡头「关联」字段未包含有效的方案编号（如 prefix-plan-NNN）")
            else:
                plan_prefix = plan_m.group(1)
                plan_num = plan_m.group(2)
                plan_rel = f"docs/projects/{plan_prefix}/plans/{plan_num}-"
                plan_text = None
                import glob as _glob
                plans_dir = repo_root / "docs" / "projects" / plan_prefix / "plans"
                plan_files = list(plans_dir.glob(f"{plan_num}-*.md")) if plans_dir.is_dir() else []
                if plan_files:
                    try:
                        plan_text = plan_files[0].read_text(encoding="utf-8")
                    except Exception:
                        plan_text = None
                if plan_text is None:
                    try:
                        res = subprocess.run(
                            ["git", "-C", str(repo_root), "ls-tree", "--name-only", "origin/main", plan_rel],
                            capture_output=True, text=True, check=False, timeout=15,
                        )
                        names = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
                        if names:
                            cand = _read_plan_from_repo(repo_root, plan_rel + names[0])
                            if cand:
                                plan_text = cand
                    except Exception:
                        pass
                if plan_text is None:
                    problems.append(f"Q1 声明关联的方案文件不存在：docs/projects/{plan_prefix}/plans/{plan_num}-*.md")
                else:
                    try:
                        plan_fields = _extract_header_fields(plan_text)
                        plan_status = plan_fields.get("状态", "").split("·")[0].strip()
                        plan_cards = plan_fields.get("关联卡", "")

                        has_card = bool(re.search(rf"\b{card_id}\b", plan_cards, re.I))
                        has_status = plan_status in ("部分执行", "已完成")
                        # Q1 收紧（ccc062）：方案同步[是] = 方案已推进（部分执行/已完成）且关联卡含本卡，两者都需满足（AND）
                        if not (has_card and has_status):
                            missing = []
                            if not has_status:
                                missing.append(f"方案 {plan_prefix}-plan-{plan_num} 状态为「{plan_status}」（须为部分执行/已完成）")
                            if not has_card:
                                missing.append(f"方案关联卡「{plan_cards}」中不包含本卡 ID「{card_id}」")
                            problems.append("Q1 方案同步校验失败。" + "；".join(missing))
                    except Exception as e:
                        problems.append(f"Q1 读取方案文件失败: {e}")

        elif num == 1 and choice in ("`否`", "否"):
            # Q1 收紧（ccc062）：勾选[否]但卡头含方案编号 → 须在说明里讲清为何不推进（防随意[否]规避）
            related = meta.get("关联", "")
            if re.search(r"([a-z]{2,4})-plan-([0-9]{3})", related):
                if "方案" not in note and "不推进" not in note and "无" not in note:
                    problems.append("Q1 勾选了方案同步[否]，但卡头含方案编号且说明未解释为何不推进（须在说明中说明，如：无方案编号/方案不涉及/待统一推进）")

        elif num == 2 and choice in ("`有`", "有"):
            paths = extract_paths(note)
            q2_files = [p for p in paths if "docs/notes/" in p or "lessons" in p]
            if not q2_files:
                problems.append("Q2 声明了有教训沉淀[有]，但说明中未引用任何 docs/notes/*.md 或 lessons.md 文件")
            else:
                found = False
                for f in q2_files:
                    if (repo_root / f).exists():
                        found = True
                        break
                if not found:
                    problems.append(f"Q2 声明的教训文件不存在：{', '.join(q2_files)}")

        elif num == 3 and choice in ("`是`", "是"):
            modified = get_modified_files(repo_root, card_file)
            card_id = get_card_id(card_file)
            prefix_m = re.match(r"^([a-z]{2,4})", card_id)
            prefix = prefix_m.group(1) if prefix_m else "ccc"

            paths = extract_paths(note)
            q3_files = [p for p in paths if "README.md" in p or "docs/projects/" in p]
            if not q3_files:
                q3_files = [f"docs/projects/{prefix}/README.md"]

            file_exists = False
            file_has_diff = False
            for f in q3_files:
                f_path = repo_root / f
                if f_path.exists():
                    file_exists = True
                    if f in modified:
                        file_has_diff = True
                        break

            if not file_exists:
                problems.append(f"Q3 声明更新了项目档案[是]，但指定的项目档案文件不存在：{', '.join(q3_files)}")
            elif not file_has_diff:
                problems.append(
                    f"Q3 声明更新了项目档案[是]，但指定的项目档案文件 {', '.join(q3_files)} 在当前分支上没有检测到相对 origin/main 的修改"
                )

        elif num == 4 and choice in ("`是`", "是"):
            modified = get_modified_files(repo_root, card_file)
            card_id = get_card_id(card_file)
            prefix_m = re.match(r"^([a-z]{2,4})", card_id)
            prefix = prefix_m.group(1) if prefix_m else "ccc"

            paths = extract_paths(note)
            q4_files = [p for p in paths if "roadmap.md" in p or "README.md" in p or "docs/projects/" in p]
            if not q4_files:
                q4_files = ["docs/roadmap.md", f"docs/projects/{prefix}/README.md"]

            file_exists = False
            file_has_diff = False
            for f in q4_files:
                f_path = repo_root / f
                if f_path.exists():
                    file_exists = True
                    if f in modified:
                        file_has_diff = True
                        break
            if not file_exists:
                problems.append(f"Q4 声明更新了线路图[是]，但指定的文件不存在：{', '.join(q4_files)}")
            elif not file_has_diff:
                problems.append(
                    f"Q4 声明更新了线路图[是]，但指定的文件 {', '.join(q4_files)} 在当前分支上没有检测到相对 origin/main 的修改"
                )

    return len(problems) == 0, problems
