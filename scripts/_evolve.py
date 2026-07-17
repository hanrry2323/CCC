"""_evolve.py — 代码分析 → 去重/优先级排序 → 投 backlog 的自动进化闭环

全链路入口: evolve_run(workspace, max_tasks=5)

依赖:
  - ccc-health-analyzer.py / ccc-security-analyzer.py（importlib 加载）
  - FileBoardStore.create_task 投递 backlog
  - .ccc/evolve/fingerprints.json 去重跟踪（最近 500 条）
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _board_store import FileBoardStore  # noqa: E402
from _logger import get_logger  # noqa: E402
from _utils import now_iso, sanitize_id  # noqa: E402

_log = get_logger("evolve")

_SEVERITY_WEIGHTS = {
    "critical": 100,
    "high": 50,
    "medium": 15,
    "low": 5,
    "info": 1,
}
_CONFIDENCE_WEIGHTS = {"high": 3, "medium": 2, "low": 1}
_CATEGORY_PRIORITY = [
    "cve",
    "circular_dependency",
    "security",
    "dead_code",
    "complexity",
]
_CATEGORY_BONUS = {
    "cve": 20,
    "security": 10,
    "circular_dependency": 15,
    "dead_code": 3,
    "complexity": 1,
}
_SEVERITY_DOWNGRADE = {
    "critical": "high",
    "high": "medium",
    "medium": "low",
    "low": "info",
    "info": "info",
}

# pytest assert 是标准用法，tests/ 下 B101 完全过滤
_NOISE_RULES = [
    lambda f: (
        "tests/" in f.get("file", "")
        and f.get("tool") == "bandit"
        and "B101" in f.get("description", "")
    ),
]

_FP_MAX = 500
_ANALYZER_CACHE: dict[str, object] = {}


def _load_analyzer(module_name: str, filename: str):
    """importlib 加载带连字符的 analyzer 脚本。"""
    if module_name in _ANALYZER_CACHE:
        return _ANALYZER_CACHE[module_name]
    path = _SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load analyzer: {path}")
    mod = importlib.util.module_from_spec(spec)
    # 确保 analyzer 内 from _logger / 兄弟模块可解析
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    spec.loader.exec_module(mod)
    _ANALYZER_CACHE[module_name] = mod
    return mod


def _fingerprint(f: dict) -> str:
    """file:line:category:tool — line 缺失或 None 时用 '?'。"""
    line = f.get("line")
    line_s = "?" if line is None else line
    return (
        f"{f.get('file', '?')}:{line_s}:{f.get('category', '?')}:{f.get('tool', '?')}"
    )


def _score_finding(f: dict) -> float:
    s = _SEVERITY_WEIGHTS.get(f.get("severity", ""), 1)
    c = _CONFIDENCE_WEIGHTS.get(f.get("confidence", ""), 1)
    b = _CATEGORY_BONUS.get(f.get("category", ""), 0)
    return float(s * c + b)


def _category_rank(category: str) -> int:
    try:
        return _CATEGORY_PRIORITY.index(category)
    except ValueError:
        return len(_CATEGORY_PRIORITY)


def _filter_noise(findings: list[dict]) -> list[dict]:
    """噪声过滤：tests/ 下 B101 全丢；其他 tests/ security 降一级严重度。"""
    out: list[dict] = []
    for f in findings:
        if any(rule(f) for rule in _NOISE_RULES):
            continue
        item = dict(f)
        if "tests/" in item.get("file", "") and item.get("category") == "security":
            sev = item.get("severity", "info")
            item["severity"] = _SEVERITY_DOWNGRADE.get(sev, "info")
        out.append(item)
    return out


def _deduplicate(findings: list[dict]) -> list[dict]:
    """同批次内按 fingerprint 去重，保留分数更高者。"""
    best: dict[str, dict] = {}
    for f in findings:
        fp = _fingerprint(f)
        prev = best.get(fp)
        if prev is None or _score_finding(f) > _score_finding(prev):
            best[fp] = f
    return list(best.values())


def _fp_path(ws_dir: Path) -> Path:
    return ws_dir / ".ccc" / "evolve" / "fingerprints.json"


def _load_fingerprints(ws_dir: Path, max_count: int = _FP_MAX) -> set[str]:
    """读 fingerprints.json，取最后 max_count 条。"""
    path = _fp_path(ws_dir)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _log.warning("fingerprints 读取失败: %s", e)
        return set()
    if isinstance(data, list):
        return set(str(x) for x in data[-max_count:])
    if isinstance(data, dict) and isinstance(data.get("fingerprints"), list):
        return set(str(x) for x in data["fingerprints"][-max_count:])
    return set()


def _trim_fingerprints(ws_dir: Path, max_count: int = _FP_MAX) -> None:
    """只保留最近 max_count 条。"""
    path = _fp_path(ws_dir)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, list):
        return
    if len(data) <= max_count:
        return
    path.write_text(
        json.dumps(data[-max_count:], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _save_fingerprint(ws_dir: Path, fp: str) -> None:
    """append fingerprint 到文件，并 trim。"""
    path = _fp_path(ws_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                existing = [str(x) for x in data]
        except (OSError, json.JSONDecodeError):
            existing = []
    existing.append(fp)
    if len(existing) > _FP_MAX:
        existing = existing[-_FP_MAX:]
    path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _post_finding(ws_dir: Path, finding: dict) -> str | None:
    """将单条 finding 投到 backlog。成功返回 task_id，失败返回 None。"""
    category = finding.get("category", "unknown")
    tool = finding.get("tool", "unknown")
    fp = _fingerprint(finding)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = hashlib.sha1(fp.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
    raw_id = f"evolve-{category}-{ts}-{short}"
    tid = sanitize_id(raw_id)
    if tid == "invalid":
        _log.warning("invalid task id from fingerprint: %s", fp)
        return None

    title = (finding.get("title") or fp)[:80]
    desc = finding.get("description") or finding.get("title") or ""
    if len(desc) > 9000:
        desc = desc[:9000] + "\n…(truncated)"

    # 附带定位信息，方便 product/dev 接手
    desc_full = (
        f"[evolve] {category}/{tool}\n"
        f"file: {finding.get('file')}\n"
        f"line: {finding.get('line')}\n"
        f"severity: {finding.get('severity')}  confidence: {finding.get('confidence')}\n"
        f"fingerprint: {fp}\n\n"
        f"{desc}"
    )
    if len(desc_full) > 9000:
        desc_full = desc_full[:9000] + "\n…(truncated)"

    now = now_iso()
    task = {
        "id": tid,
        "title": title,
        "description": desc_full,
        "tags": ["evolve", str(category), str(tool)],
        "status": "backlog",
        "created_at": now,
        "updated_at": now,
    }

    store = FileBoardStore(ws_dir)
    ok = store.create_task(task, column="backlog")
    if not ok:
        _log.warning("create_task 失败: %s", tid)
        return None
    _save_fingerprint(ws_dir, fp)
    return tid


def evolve_run(workspace: str, max_tasks: int = 5) -> dict:
    """全链路：分析 → 去重/排序/限流 → 投 backlog

    v0.42.4: 自动投入永久禁用；仅扫描不写 backlog。

    Returns:
        { "posted": int, "total": int, "filtered": int,
          "errors": list[str], "posted_tasks": list[str] }
    """
    try:
        from _ccc_control import may_auto_inject_tasks, may_invent

        if not may_auto_inject_tasks() or not may_invent():
            _log.info(
                "[evolve] skip post backlog — auto-inject hard-disabled (%s)",
                workspace,
            )
            return {
                "posted": 0,
                "total": 0,
                "filtered": 0,
                "errors": ["auto-inject hard-disabled"],
                "posted_tasks": [],
            }
    except ImportError:
        return {
            "posted": 0,
            "total": 0,
            "filtered": 0,
            "errors": ["control import failed; refuse invent"],
            "posted_tasks": [],
        }

    ws_dir = Path(workspace).resolve()
    errors: list[str] = []
    posted_tasks: list[str] = []

    _log.info("evolve 开始: %s (max_tasks=%d)", ws_dir, max_tasks)

    # 1. 调用分析器
    all_findings: list[dict] = []
    try:
        health = _load_analyzer("ccc_health_analyzer", "ccc-health-analyzer.py")
        all_findings.extend(health.analyze_health(str(ws_dir)))
    except Exception as e:
        msg = f"health analyzer failed: {e}"
        _log.warning(msg)
        errors.append(msg)

    try:
        security = _load_analyzer("ccc_security_analyzer", "ccc-security-analyzer.py")
        all_findings.extend(security.analyze_security(str(ws_dir)))
    except Exception as e:
        msg = f"security analyzer failed: {e}"
        _log.warning(msg)
        errors.append(msg)

    total = len(all_findings)

    # 2. 噪声过滤
    filtered_list = _filter_noise(all_findings)
    noise_dropped = total - len(filtered_list)

    # 3. 批次内去重
    deduped = _deduplicate(filtered_list)

    # 4. 优先级排序 → 取全局 top-N → 再跳过已投递 fingerprint
    #    （保证同一批最高优发现不会在每次调度时把次优也灌进 backlog）
    deduped.sort(
        key=lambda f: (-_score_finding(f), _category_rank(f.get("category", "")))
    )
    top_n = deduped[: max(0, int(max_tasks))]
    seen = _load_fingerprints(ws_dir)
    to_post = [f for f in top_n if _fingerprint(f) not in seen]
    already = len(top_n) - len(to_post)

    # 5. 投递
    for finding in to_post:
        try:
            tid = _post_finding(ws_dir, finding)
            if tid:
                posted_tasks.append(tid)
                _log.info(
                    "posted %s ← [%s] %s",
                    tid,
                    finding.get("severity"),
                    (finding.get("title") or "")[:60],
                )
            else:
                errors.append(f"post failed: {_fingerprint(finding)}")
        except Exception as e:
            errors.append(f"post exception: {e}")
            _log.warning("post exception: %s", e)

    _trim_fingerprints(ws_dir)

    # filtered = 噪声丢弃 + top-N 内已投过 + 未进 top-N 的其余 finding
    filtered_count = noise_dropped + already + max(0, len(deduped) - len(top_n))
    result = {
        "posted": len(posted_tasks),
        "total": total,
        "filtered": filtered_count,
        "errors": errors,
        "posted_tasks": posted_tasks,
    }
    _log.info(
        "evolve 完成: posted=%d total=%d filtered=%d errors=%d",
        result["posted"],
        result["total"],
        result["filtered"],
        len(errors),
    )
    return result
