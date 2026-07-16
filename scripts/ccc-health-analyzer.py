"""ccc-health-analyzer — 代码健康分析引擎

检测维度:
  - 死代码 (vulture) — 未使用的类/函数/变量
  - 复杂度 (radon) — 圈复杂度 / Maintainability Index
  - 循环依赖 (AST) — 模块级 import 环

输出统一 finding 结构，供进化检测消费。

Usage:
    python3 ccc-health-analyzer.py /path/to/workspace
    python3 ccc-health-analyzer.py /path/to/workspace --jsonl
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess as sp
from pathlib import Path

from _logger import get_logger

_log = get_logger("health-analyzer")

# 跳过目录（vulture / radon / 循环依赖共用）
_SKIP_PARTS = {
    ".ccc", ".venv", "venv", "__pycache__", "node_modules", ".git",
    ".claude", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".codebase-memory", ".code-review-graph", ".archived-2026-07-06",
}
_EXCLUDE_PATTERNS = ",".join(sorted(_SKIP_PARTS))

# radon 圈复杂度阈值
_CC_WARNING = 10
_CC_HIGH = 20
_CC_VERY_HIGH = 40
_MI_THRESHOLD = 50


def make_finding(
    severity: str,
    category: str,
    file: str,
    line: int | None,
    title: str,
    description: str = "",
    tool: str = "ast",
    confidence: str = "medium",
) -> dict:
    assert severity in ("critical", "high", "medium", "low", "info"), severity
    assert confidence in ("high", "medium", "low"), confidence
    return {
        "severity": severity,
        "category": category,
        "file": file,
        "line": line,
        "title": title,
        "description": description or title,
        "tool": tool,
        "confidence": confidence,
    }


def _tool_available(name: str) -> bool:
    try:
        sp.run([name, "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, sp.TimeoutExpired):
        return False


def _relative_path(fpath: str, prefix: str) -> str:
    try:
        return str(Path(fpath).resolve().relative_to(Path(prefix).resolve()))
    except ValueError:
        return fpath


# ═══════════════════════════════════════════════════════════════
# 1. 死代码 — vulture
# ═══════════════════════════════════════════════════════════════

def _parse_vulture_output(text: str, ws: str) -> list[dict]:
    """解析 vulture 文本输出 → findings。

    格式: path/to/file.py:42: unused variable 'foo' (60% confidence)
    """
    findings = []
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        fpath, line_str, msg = parts
        try:
            lineno = int(line_str)
        except ValueError:
            lineno = None
        msg = msg.strip()
        conf = "medium"
        if "(60%" in msg or "(70%" in msg:
            conf = "medium"
        elif "(80%" in msg or "(90%" in msg or "(100%" in msg:
            conf = "high"

        sev = "medium"
        if "unused import" in msg or "unused attribute" in msg:
            sev = "low"
        elif "unused function" in msg or "unused class" in msg or "unused method" in msg:
            sev = "medium"
        elif "unused variable" in msg:
            sev = "low"

        findings.append(make_finding(
            severity=sev,
            category="dead_code",
            file=_relative_path(fpath, ws),
            line=lineno,
            title=msg[:120],
            tool="vulture",
            confidence=conf,
        ))
    return findings


def _analyze_dead_code(ws: str) -> list[dict]:
    if not _tool_available("vulture"):
        _log.warning("vulture 未安装，跳过死代码检测: pip install vulture")
        return []
    try:
        r = sp.run(
            [
                "vulture", ws,
                "--min-confidence", "60",
                "--exclude", _EXCLUDE_PATTERNS,
            ],
            capture_output=True, text=True, timeout=120,
        )
        return _parse_vulture_output(r.stdout, ws)
    except sp.TimeoutExpired:
        _log.warning("vulture 超时 (120s)，跳过")
        return []
    except OSError as e:
        _log.warning("vulture 执行失败: %s", e)
        return []


# ═══════════════════════════════════════════════════════════════
# 2. 复杂度 — radon
# ═══════════════════════════════════════════════════════════════

def _parse_radon_cc(json_text: str, prefix: str) -> list[dict]:
    """解析 radon cc -j 输出 → findings。"""
    findings = []
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    for fpath, blocks in data.items():
        if not isinstance(blocks, list):
            continue  # 跳过 --total-average 等非列表项
        rel = _relative_path(fpath, prefix)
        for b in blocks:
            name = b.get("name", "?")
            complexity = b.get("complexity", 0)
            if complexity >= _CC_VERY_HIGH:
                sev = "high"
            elif complexity >= _CC_HIGH:
                sev = "medium"
            elif complexity >= _CC_WARNING:
                sev = "low"
            else:
                continue
            findings.append(make_finding(
                severity=sev,
                category="complexity",
                file=rel,
                line=b.get("lineno"),
                title=f"圈复杂度 {complexity}: {name}",
                description=(
                    f"函数 '{name}' 圈复杂度 {complexity}"
                    f"（阈值 warning>={_CC_WARNING}, high>={_CC_HIGH}, very_high>={_CC_VERY_HIGH}）"
                ),
                tool="radon",
                confidence="high",
            ))
    return findings


def _parse_radon_mi(json_text: str, prefix: str) -> list[dict]:
    """解析 radon mi -j 输出 → findings。

    radon 6.x 格式: {"path": {"mi": 72.5, "rank": "A"}}
    """
    findings = []
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    for fpath, mi_val in data.items():
        if isinstance(mi_val, dict):
            mi = mi_val.get("mi", 100)
        elif isinstance(mi_val, (int, float)):
            mi = float(mi_val)
        else:
            continue
        if mi >= _MI_THRESHOLD:
            continue
        rel = _relative_path(fpath, prefix)
        findings.append(make_finding(
            severity="low",
            category="complexity",
            file=rel,
            line=None,
            title=f"可维护性指数 {mi:.0f}（< {_MI_THRESHOLD}）",
            description=f"模块 '{rel}' Maintainability Index {mi:.1f}，低于阈值 {_MI_THRESHOLD}",
            tool="radon",
            confidence="medium",
        ))
    return findings


def _analyze_complexity(ws: str) -> list[dict]:
    if not _tool_available("radon"):
        _log.warning("radon 未安装，跳过复杂度检测: pip install radon")
        return []
    findings: list[dict] = []
    ignore = ":".join(sorted(_SKIP_PARTS))
    try:
        r = sp.run(
            ["radon", "cc", ws, "-j", "-i", ignore],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0 and r.stdout.strip():
            findings.extend(_parse_radon_cc(r.stdout, ws))
        elif r.returncode != 0:
            _log.warning("radon cc 退出码 %d: %s", r.returncode, (r.stderr or "")[:200])
    except sp.TimeoutExpired:
        _log.warning("radon cc 超时 (120s)")
    except OSError as e:
        _log.warning("radon cc 执行失败: %s", e)

    try:
        r = sp.run(
            ["radon", "mi", ws, "-j", "-i", ignore],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0 and r.stdout.strip():
            findings.extend(_parse_radon_mi(r.stdout, ws))
        elif r.returncode != 0:
            _log.warning("radon mi 退出码 %d", r.returncode)
    except sp.TimeoutExpired:
        _log.warning("radon mi 超时 (120s)")
    except OSError as e:
        _log.warning("radon mi 执行失败: %s", e)

    return findings


# ═══════════════════════════════════════════════════════════════
# 3. 循环依赖 — AST import 图 (stdlib only)
# ═══════════════════════════════════════════════════════════════

def _module_name_from_path(fpath: Path, ws: Path) -> str:
    try:
        rel = fpath.relative_to(ws)
    except ValueError:
        return fpath.stem
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts)


def _extract_imports(tree: ast.AST) -> list[str]:
    """提取模块级 import 的完整模块名（含包路径）。"""
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # 相对 import 在图构建时单独处理更稳；此处跳过简化
            if node.module:
                imports.append(node.module)
    return imports


def _should_skip(path: Path) -> bool:
    return any(part in _SKIP_PARTS for part in path.parts)


def _analyze_circular_deps(ws: str) -> list[dict]:
    """AST DFS 检测模块级循环依赖。排除自引用与 .ccc/.venv/__pycache__。"""
    ws_path = Path(ws).resolve()
    py_files = [p for p in ws_path.rglob("*.py") if not _should_skip(p)]

    import_graph: dict[str, list[str]] = {}
    module_to_file: dict[str, str] = {}
    for fpath in py_files:
        mod = _module_name_from_path(fpath, ws_path)
        if not mod:
            continue
        module_to_file[mod] = str(fpath.relative_to(ws_path))
        import_graph.setdefault(mod, [])
        try:
            tree = ast.parse(fpath.read_text(encoding="utf-8", errors="ignore"))
            import_graph[mod].extend(_extract_imports(tree))
        except (SyntaxError, OSError):
            pass

    all_modules = set(import_graph.keys())

    def _resolve_dep(dep: str) -> str | None:
        if dep in all_modules:
            return dep
        # 最长前缀匹配：import scripts.foo → scripts.foo
        candidates = [m for m in all_modules if m == dep or m.startswith(dep + ".")]
        if candidates:
            return min(candidates, key=len)
        # import scripts.foo.bar 而只有 scripts.foo
        parts = dep.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in all_modules:
                return candidate
            parts.pop()
        return None

    resolved_graph: dict[str, list[str]] = {}
    for mod, deps in import_graph.items():
        resolved: list[str] = []
        seen: set[str] = set()
        for d in deps:
            target = _resolve_dep(d)
            if target and target != mod and target not in seen:
                seen.add(target)
                resolved.append(target)
        resolved_graph[mod] = resolved

    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in resolved_graph.get(node, []):
            if neighbor == node:
                continue  # 排除自引用
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                try:
                    idx = path.index(neighbor)
                    cycles.append(path[idx:] + [neighbor])
                except ValueError:
                    pass
        rec_stack.discard(node)

    for mod in sorted(all_modules):
        if mod not in visited:
            dfs(mod, [mod])

    seen_cycles: set[str] = set()
    findings: list[dict] = []
    for cycle in cycles:
        # 去掉末尾重复闭合点再规范化
        body = cycle[:-1] if cycle and cycle[0] == cycle[-1] else cycle
        if len(body) < 2:
            continue
        min_idx = body.index(min(body))
        norm = body[min_idx:] + body[:min_idx]
        key = " -> ".join(norm)
        if key in seen_cycles:
            continue
        seen_cycles.add(key)
        files_in_cycle = [module_to_file.get(m, m) for m in norm]
        findings.append(make_finding(
            severity="medium" if len(norm) <= 3 else "low",
            category="circular_dependency",
            file=files_in_cycle[0],
            line=None,
            title=f"循环依赖: {' → '.join(norm)}",
            description=f"模块间循环依赖 ({len(norm)} 个模块): {' → '.join(files_in_cycle)}",
            tool="ast",
            confidence="high",
        ))
    return findings


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def analyze_health(workspace: str) -> list[dict]:
    """返回 finding list。"""
    findings: list[dict] = []
    _log.info("开始健康分析: %s", workspace)
    findings.extend(_analyze_dead_code(workspace))
    findings.extend(_analyze_complexity(workspace))
    findings.extend(_analyze_circular_deps(workspace))
    _log.info("健康分析完成: %d 条发现", len(findings))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="CCC 代码健康分析引擎")
    parser.add_argument("workspace", help="项目路径")
    parser.add_argument("--jsonl", action="store_true", help="JSON lines 输出（默认: 人类可读）")
    args = parser.parse_args()

    findings = analyze_health(args.workspace)

    if args.jsonl:
        for f in findings:
            print(json.dumps(f, ensure_ascii=False))
    else:
        if not findings:
            print("无发现")
            return
        print(f"健康分析: {len(findings)} 条发现\n")
        for f in findings:
            print(f"  [{f['severity']:>6}] [{f['category']:<20}] {f['file']}:{f['line'] or '-'}")
            print(f"          {f['title']}")
        print()


if __name__ == "__main__":
    main()
