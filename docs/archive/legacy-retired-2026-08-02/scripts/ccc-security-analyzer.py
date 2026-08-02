"""ccc-security-analyzer — 安全扫描引擎

检测维度:
  - 安全编码 (bandit) — eval/exec/sql 注入/硬编码密钥
  - 依赖漏洞 (pip-audit) — CVE 扫描

输出统一 finding 结构，供进化检测消费。

Usage:
    python3 ccc-security-analyzer.py /path/to/workspace
    python3 ccc-security-analyzer.py /path/to/workspace --jsonl
"""

from __future__ import annotations

import argparse
import json
import subprocess as sp
from pathlib import Path

from _logger import get_logger

_log = get_logger("security-analyzer")

_BANDIT_SEV_MAP = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
_BANDIT_CONF_MAP = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
_CVE_SEV_MAP = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low"}


def make_finding(
    severity: str,
    category: str,
    file: str,
    line: int | None,
    title: str,
    description: str = "",
    tool: str = "bandit",
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
# 1. 安全编码 — bandit
# ═══════════════════════════════════════════════════════════════

def _parse_bandit_json(data: dict, prefix: str) -> list[dict]:
    findings = []
    for result in data.get("results", []):
        sev = _BANDIT_SEV_MAP.get(result.get("issue_severity", "MEDIUM"), "medium")
        conf = _BANDIT_CONF_MAP.get(result.get("issue_confidence", "MEDIUM"), "medium")
        fpath = result.get("filename", "")
        findings.append(make_finding(
            severity=sev,
            category="security",
            file=_relative_path(fpath, prefix),
            line=result.get("line_number"),
            title=(result.get("issue_text") or "")[:120],
            description=(
                f"[{result.get('test_id', '?')}] {result.get('issue_text', '')}"
                f" — {(result.get('code') or '')[:200]}"
            ),
            tool="bandit",
            confidence=conf,
        ))
    return findings


def _analyze_security_issues(ws: str) -> list[dict]:
    if not _tool_available("bandit"):
        _log.warning("bandit 未安装，跳过安全扫描: pip install bandit")
        return []

    # bandit -x 接受逗号分隔路径；-q 抑制进度条以免污染 JSON stdout
    exclude = ",".join([
        ".ccc", ".venv", "venv", "__pycache__", "node_modules", ".git",
        ".claude", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ])

    try:
        r = sp.run(
            ["bandit", "-r", ws, "-f", "json", "-q", "-x", exclude],
            capture_output=True, text=True, timeout=180,
        )
        # exit 0=无发现, 1=有发现（都正常）, 2=错误
        if r.returncode not in (0, 1):
            _log.warning("bandit 退出码 %d: %s", r.returncode, (r.stderr or "")[:200])
            return []
        raw = r.stdout.strip()
        if not raw:
            return []
        # 兜底：若仍有前缀噪声，从第一个 { 起切 JSON
        if not raw.startswith("{"):
            idx = raw.find("{")
            if idx < 0:
                _log.warning("bandit 输出非 JSON: %s", raw[:200])
                return []
            raw = raw[idx:]
        data = json.loads(raw)
        return _parse_bandit_json(data, ws)
    except json.JSONDecodeError:
        _log.warning("bandit 输出非 JSON: %s", (r.stdout or "")[:200])
        return []
    except sp.TimeoutExpired:
        _log.warning("bandit 超时 (180s)")
        return []
    except OSError as e:
        _log.warning("bandit 执行失败: %s", e)
        return []


# ═══════════════════════════════════════════════════════════════
# 2. 依赖漏洞 — pip-audit
# ═══════════════════════════════════════════════════════════════

def _parse_pip_audit_json(data) -> list[dict]:
    """解析 pip-audit --format json 输出。

    兼容两种形态:
      - dict: {"dependencies": [{"name", "version", "vulns": [...]}]}
      - list: [{"name", "version", "vulns": [...]}]
    """
    findings = []
    if isinstance(data, list):
        deps = data
    elif isinstance(data, dict):
        deps = data.get("dependencies", [])
    else:
        return []

    for dep in deps:
        name = dep.get("name", "?")
        version = dep.get("version", "?")
        for vuln in dep.get("vulns", []):
            aliases = vuln.get("aliases") or []
            cve_id = next((a for a in aliases if str(a).startswith("CVE-")), None)
            if not cve_id:
                cve_id = aliases[0] if aliases else vuln.get("id", "?")
            sev_raw = (vuln.get("severity") or "").strip().upper()
            sev = _CVE_SEV_MAP.get(sev_raw, "medium")
            desc = vuln.get("description") or ""
            findings.append(make_finding(
                severity=sev,
                category="cve",
                file=f"requirements/{name}",
                line=None,
                title=f"{cve_id}: {name}@{version} — {desc[:80]}",
                description=f"{cve_id}: {name} ({version}) — {desc[:500]}",
                tool="pip-audit",
                confidence="high",
            ))
    return findings


def _run_pip_audit(cmd: list[str], label: str) -> list[dict]:
    try:
        r = sp.run(cmd, capture_output=True, text=True, timeout=120)
        # exit 0=无漏洞, 1=有漏洞, 2=错误
        if r.returncode == 2:
            _log.warning("pip-audit 错误 (%s): %s", label, (r.stderr or "")[:200])
            return []
        if not r.stdout.strip():
            return []
        data = json.loads(r.stdout)
        return _parse_pip_audit_json(data)
    except json.JSONDecodeError:
        _log.warning("pip-audit 输出非 JSON (%s)", label)
        return []
    except sp.TimeoutExpired:
        _log.warning("pip-audit 超时 (120s): %s", label)
        return []
    except OSError as e:
        _log.warning("pip-audit 执行失败 (%s): %s", label, e)
        return []


def _analyze_vulnerabilities(ws: str) -> list[dict]:
    if not _tool_available("pip-audit"):
        _log.warning("pip-audit 未安装，跳过 CVE 扫描: pip install pip-audit")
        return []

    ws_path = Path(ws)
    findings: list[dict] = []
    scanned = False

    # requirements*.txt / Pipfile → -r
    for candidate in ["requirements.txt", "requirements-dev.txt", "Pipfile"]:
        p = ws_path / candidate
        if p.exists():
            scanned = True
            findings.extend(_run_pip_audit(
                ["pip-audit", "--format", "json", "-r", str(p)],
                candidate,
            ))

    # pyproject.toml → project_path 模式
    if (ws_path / "pyproject.toml").exists():
        scanned = True
        findings.extend(_run_pip_audit(
            ["pip-audit", "--format", "json", str(ws_path)],
            "pyproject.toml",
        ))

    if not scanned:
        _log.info("未找到 requirements.txt / pyproject.toml / Pipfile，跳过 CVE")

    return findings


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def analyze_security(workspace: str) -> list[dict]:
    """返回 finding list。"""
    findings: list[dict] = []
    _log.info("开始安全分析: %s", workspace)
    findings.extend(_analyze_security_issues(workspace))
    findings.extend(_analyze_vulnerabilities(workspace))
    _log.info("安全分析完成: %d 条发现", len(findings))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="CCC 安全扫描引擎")
    parser.add_argument("workspace", help="项目路径")
    parser.add_argument("--jsonl", action="store_true", help="JSON lines 输出")
    args = parser.parse_args()

    findings = analyze_security(args.workspace)

    if args.jsonl:
        for f in findings:
            print(json.dumps(f, ensure_ascii=False))
    else:
        if not findings:
            print("无发现")
            return
        print(f"安全分析: {len(findings)} 条发现\n")
        for f in findings:
            print(f"  [{f['severity']:>6}] [{f['category']:<10}] {f['file']}:{f['line'] or '-'}")
            print(f"          {f['title']}")
        print()


if __name__ == "__main__":
    main()
