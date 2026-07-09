"""_review_validator.py — Trae 审查报告入站校验 (v0.23.4)

校验 .ccc/reviews/ 下的 JSON 报告是否符合 SKILL.md 定义的模板。
每次 engine 空闲时自动扫描最新报告，格式不对就告警。
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {"schema_version", "generated_at", "project", "source", "findings", "summary"}
FINDING_REQUIRED = {"id", "severity", "category", "title", "description"}
VALID_SOURCES = {"daily-scan", "adversarial", "doc-quality"}
VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
VALID_CATEGORIES = {"security", "config", "code-quality", "documentation", "ops"}
SUMMARY_REQUIRED = {"total", "critical", "high", "medium", "low", "info", "auto_fixable"}


def validate_review_json(report_path: str) -> dict:
    """校验一份审查报告 JSON 是否符合规范

    Returns:
        {"valid": True} 或 {"valid": False, "errors": [错误信息]}
    """
    errors = []
    path = Path(report_path)

    if not path.exists():
        return {"valid": False, "errors": [f"文件不存在: {report_path}"]}

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"JSON 解析错误: {e}"]}

    if not isinstance(data, dict):
        return {"valid": False, "errors": ["顶层结构必须是 dict"]}

    # 1. 必填顶层字段
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"缺顶层字段: {field}")

    if errors:
        return {"valid": False, "errors": errors}

    # 2. source 合法性
    if data.get("source") not in VALID_SOURCES:
        errors.append(f"source 必须是 {VALID_SOURCES} 之一，当前: {data.get('source')}")

    # 3. generated_at 可解析
    try:
        datetime.fromisoformat(data["generated_at"])
    except (ValueError, TypeError):
        errors.append(f"generated_at 不是合法 ISO8601: {data.get('generated_at')}")

    # 4. findings 校验
    findings = data.get("findings", [])
    if not isinstance(findings, list):
        errors.append("findings 必须是数组")
    else:
        for i, f_item in enumerate(findings):
            for field in FINDING_REQUIRED:
                if field not in f_item:
                    errors.append(f"findings[{i}] 缺字段: {field}")
            sev = f_item.get("severity", "")
            if sev and sev not in VALID_SEVERITIES:
                errors.append(f"findings[{i}] severity '{sev}' 不合法（必须是 {VALID_SEVERITIES}）")
            cat = f_item.get("category", "")
            if cat and cat not in VALID_CATEGORIES:
                errors.append(f"findings[{i}] category '{cat}' 不合法（必须是 {VALID_CATEGORIES}）")

    # 5. summary 校验
    summary = data.get("summary", {})
    if not isinstance(summary, dict):
        errors.append("summary 必须是 dict")
    else:
        for field in SUMMARY_REQUIRED:
            if field not in summary:
                errors.append(f"summary 缺字段: {field}")
        if isinstance(summary, dict) and summary.get("total", 0) != len(findings):
            errors.append(
                f"summary.total ({summary.get('total')}) != len(findings) ({len(findings)})"
            )

    return {"valid": len(errors) == 0, "errors": errors}


def scan_review_dir(workspace: str) -> list[dict]:
    """扫描项目 .ccc/reviews/ 下所有 JSON 报告，返回校验结果"""
    results = []
    reviews_dir = Path(workspace) / ".ccc" / "reviews"

    if not reviews_dir.exists():
        return results

    for f in sorted(reviews_dir.glob("*.json")):
        result = validate_review_json(str(f))
        result["file"] = str(f)
        results.append(result)

    return results


def scan_all_workspaces() -> list[dict]:
    """扫描所有已知 workspace 的 review 报告"""
    from _config import Config
    cfg = Config()
    all_results = []

    for ws in cfg.audit_workspaces:
        results = scan_review_dir(ws)
        all_results.extend(results)

    # 也扫自身
    results = scan_review_dir(str(cfg.workspace))
    all_results.extend(results)

    return all_results
