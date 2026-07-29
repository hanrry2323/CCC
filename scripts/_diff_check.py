#!/usr/bin/env python3
"""_diff_check.py — CCC 安全检查模块

FlowWeave 启发：GitReview 工作流的敏感文件拦截、大变更预警、删除预警。

能力：
1. 敏感文件检测：.env、密钥、credentials、控制面文件是否混入变更
2. 大文件/大变更预警：单文件 >500 行新增、整体变更超阈值
3. 删除预警：单次删除 >5 个文件
4. 工作区越界检测：变更是否越出承诺范围
5. 统一返回格式：[flag, ...] 或 True/False

用法：
  from _diff_check import check_uncommitted, check_commit_range
  flags = check_uncommitted(cwd="/path/to/project")
  flags = check_commit_range("HEAD~1..HEAD", cwd="/path/to/project")
"""

from __future__ import annotations
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ── 敏感文件模式 ──

_SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?:^|/)\.env(?:\.\w+)?$"),
    re.compile(r"(?:^|/)\.env\.local$"),
    re.compile(r"(?:^|/)credentials\.\w+$"),
    re.compile(r"(?:^|/)\.credentials"),
    re.compile(r"(?:^|/)\w+-secret\.\w+$"),
    re.compile(r"(?:^|/)\w+-secrets\.\w+$"),
    re.compile(r"(?:^|/)\w+-key\.\w+$"),
    re.compile(r"(?:^|/)\w+-keys\.\w+$"),
    re.compile(r"(?:^|/)\.ssh/"),
    re.compile(r"(?:^|/)\.token$"),
    re.compile(r"(?:^|/)\.tokens$"),
    re.compile(r"(?:^|/)token\.\w+$"),
    re.compile(r"(?:^|/)\.pypirc$"),
    re.compile(r"(?:^|/)\.npmrc$"),
    re.compile(r"(?:^|/)\.netrc$"),
    re.compile(r"(?:^|/)config\.hub\.toml$"),
    re.compile(r"(?:^|/)control\.json$"),
    re.compile(r"(?:^|/)\.ccc/.*control\.json"),
    re.compile(r"(?:^|/)launchd\.plist$"),
    re.compile(r"(?:^|/)\.launchd/"),
    re.compile(r"password|secret|token|credential|api_key|apikey", re.IGNORECASE),
]

# ── 控制面/无关仓路径 ──

_CONTROL_DIRS = frozenset({".ccc", ".cursor", "node_modules", ".venv", ".venv-hub", ".build"})


# ── 工具 ──

def _git(cmd: list[str], cwd: str | Path, timeout: int = 15) -> tuple[int, str]:
    """运行 git 命令，返回 (returncode, stdout)。"""
    try:
        r = subprocess.run(
            ["git"] + cmd,
            capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
        return r.returncode, r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return -1, ""


def _git_diff_stat(cwd: str | Path, rev_range: Optional[str] = None) -> list[dict]:
    """获取 git diff --stat，返回每行解析结果。"""
    cmd = ["diff", "--stat"]
    if rev_range:
        cmd.append(rev_range)
    rc, out = _git(cmd, cwd)
    if rc != 0 or not out:
        return []

    results = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith(" ") or "file changed" in line or "files changed" in line:
            continue
        # 格式: "path | N ++++++++-------"
        parts = line.split("|")
        if len(parts) == 2:
            fpath = parts[0].strip()
            changes = parts[1].strip()
            # 提取插入/删除数
            insertions = 0
            deletions = 0
            m_ins = re.search(r"(\d+)\s*\+", changes)
            m_del = re.search(r"(\d+)\s*-", changes)
            if m_ins:
                insertions = int(m_ins.group(1))
            if m_del:
                deletions = int(m_del.group(1))
            results.append({
                "path": fpath,
                "insertions": insertions,
                "deletions": deletions,
            })
        elif parts:
            results.append({"path": parts[0].strip(), "insertions": 0, "deletions": 1})
    return results


def _git_diff_name_status(cwd: str | Path, rev_range: Optional[str] = None) -> list[dict]:
    """获取 git diff --name-status，每行 (status, path)。"""
    cmd = ["diff", "--name-status"]
    if rev_range:
        cmd.append(rev_range)
    rc, out = _git(cmd, cwd)
    if rc != 0:
        return []
    results = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            results.append({"status": parts[0], "path": parts[1]})
    return results


def _git_diff_files(cwd: str | Path) -> list[dict]:
    """未提交变更的文件列表。等价于 git status --short。"""
    rc, out = _git(["status", "--short"], cwd)
    if rc != 0:
        return []
    results = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        xy = line[:2]
        fpath = line[2:].strip()
        results.append({"status": xy, "path": fpath})
    return results


# ── 检查规则 ──

def _is_sensitive(path: str) -> Optional[str]:
    """检查路径是否匹配敏感模式。返回原因或 None。"""
    p = path.replace("\\", "/")
    # 先精确模式
    for pat in _SENSITIVE_PATTERNS:
        if pat.search(p):
            return f"敏感文件匹配: {pat.pattern[:40]}"
    return None


def _is_out_of_bounds(path: str, allowed_prefixes: list[str]) -> Optional[str]:
    """检查文件是否越出允许范围。"""
    p = path.replace("\\", "/")
    for prefix in allowed_prefixes:
        if p.startswith(prefix) or f"/{prefix}/" in p:
            return None
    # 控制面目录总是越界
    first_seg = p.split("/")[0]
    if first_seg in _CONTROL_DIRS:
        return f"控制面目录变更: {first_seg}"
    return None


# ── 主检查函数 ──

def _make_flag(level: str, rule: str, message: str, details: Optional[list] = None) -> dict:
    return {"level": level, "rule": rule, "message": message, "details": details or []}


def check_uncommitted(
    cwd: str | Path = ".",
    *,
    allowed_prefixes: Optional[list[str]] = None,
    max_file_insertions: int = 500,
    max_delete_count: int = 5,
) -> list[dict]:
    """检查未提交的变更。

    返回 flags 列表：
      {"level": "warn"|"block", "rule": "...", "message": "...", "details": [...]}
    """
    flags = []
    cwd = Path(cwd).resolve()

    # 1. 文件列表
    changes = _git_diff_files(cwd)
    if not changes:
        return flags  # 空

    # 2. 敏感文件检测
    for ch in changes:
        reason = _is_sensitive(ch["path"])
        if reason:
            flags.append(_make_flag(
                "block", "sensitive-file",
                f"敏感文件混入变更: {ch['path']}",
                [{"path": ch["path"], "reason": reason}],
            ))

    # 3. 越界检测
    if allowed_prefixes:
        for ch in changes:
            reason = _is_out_of_bounds(ch["path"], allowed_prefixes)
            if reason:
                flags.append(_make_flag(
                    "warn", "out-of-bounds",
                    f"变更越出范围: {ch['path']} — {reason}",
                ))

    # 4. 大变更预警
    stats = _git_diff_stat(cwd)
    total_ins = 0
    for s in stats:
        if s["insertions"] > max_file_insertions:
            flags.append(_make_flag(
                "warn", "large-change",
                f"单文件新增过多: {s['path']} ({s['insertions']} 行)",
                [s],
            ))
        total_ins += s["insertions"]

    # 5. 删除预警
    deleted = [s["path"] for s in stats if s["deletions"] > 0 and s["insertions"] == 0]
    if len(deleted) > max_delete_count:
        flags.append(_make_flag(
            "warn", "bulk-delete",
            f"批量删除预警: {len(deleted)} 个文件将被删除",
            deleted,
        ))

    # 6. 体量异常
    if total_ins > 2000:
        flags.append(_make_flag(
            "warn", "large-patch",
            f"本次变更体量异常: 共 {total_ins} 行新增",
        ))

    return flags


def check_commit_range(
    rev_range: str,
    cwd: str | Path = ".",
    *,
    allowed_prefixes: Optional[list[str]] = None,
    max_file_insertions: int = 500,
    max_delete_count: int = 5,
) -> list[dict]:
    """检查已提交的变更范围。"""
    cwd = Path(cwd).resolve()
    flags = []

    changes = _git_diff_name_status(cwd, rev_range)
    if not changes:
        return flags

    # 敏感文件检测
    for ch in changes:
        reason = _is_sensitive(ch["path"])
        if reason:
            flags.append(_make_flag(
                "block", "sensitive-file",
                f"敏感文件混入 commit: {ch['path']}",
            ))

    # 越界检测
    if allowed_prefixes:
        for ch in changes:
            reason = _is_out_of_bounds(ch["path"], allowed_prefixes)
            if reason:
                flags.append(_make_flag(
                    "warn", "out-of-bounds",
                    f"变更越出范围: {ch['path']}",
                ))

    # 大变更 + 删除预警
    stats = _git_diff_stat(cwd, rev_range)
    deleted = 0
    for s in stats:
        if s["insertions"] > max_file_insertions:
            flags.append(_make_flag(
                "warn", "large-change",
                f"单文件新增过多: {s['path']} ({s['insertions']} 行)",
            ))
        if s["deletions"] > 0 and s["insertions"] == 0:
            deleted += 1

    if deleted > max_delete_count:
        flags.append(_make_flag(
            "warn", "bulk-delete",
            f"批量删除预警: {deleted} 个文件被删除",
        ))

    return flags


def any_blocked(flags: list[dict]) -> bool:
    """检查是否有需要阻止的 flag。"""
    return any(f.get("level") == "block" for f in flags)


def summary(flags: list[dict]) -> str:
    """格式化输出。"""
    if not flags:
        return "✓ 安全检查通过，无异常"

    lines = []
    for f in flags:
        icon = "🔴" if f["level"] == "block" else "🟡"
        lines.append(f"  {icon} [{f['rule']}] {f['message']}")
    return "\n".join(lines)


# ── CLI ──

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="CCC 安全检查")
    ap.add_argument("--uncommitted", action="store_true", help="检查未提交变更")
    ap.add_argument("--range", help="commit 范围，如 HEAD~3..HEAD")
    ap.add_argument("--dir", default=".", help="工作目录")
    args = ap.parse_args()

    if args.range:
        flags = check_commit_range(args.range, cwd=args.dir)
    else:
        flags = check_uncommitted(cwd=args.dir)

    print(summary(flags))
    if any_blocked(flags):
        sys.exit(1)
