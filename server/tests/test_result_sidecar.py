"""P1.3：JSON result sidecar 生成 + 引擎优先读 JSON 收单 + 缺失回退 markdown 兼容。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from server.engine.result_sidecar import convert_file, parse_result


def _result_text(work_id: str = "tst999") -> str:
    return (
        f"# 执行结果 · {work_id} · smoke: sidecar\n"
        f"## 0. 卡标题复述\n\n{work_id} · smoke: sidecar\n"
        "## 1. 探针输出\n\n- probe ok\n"
        "## 2. 自测输出\n\n- 8 passed\n- test exit=0\n- lint=0\n- compile=0\n"
        "## 3. 维护区四问\n\n"
        "1. 方案同步：[是] 方案已推进\n"
        "2. 教训沉淀：[有] 见 lessons\n"
        "3. 档案/README：[否] 无变更\n"
        "4. 线路图：[否] 无变化\n"
        "## 4. 变更证据\n\ncommit=abc1234 branch=codex/tst999 push=success\n"
    )


def test_parse_result_extracts_contract_fields() -> None:
    payload = parse_result(_result_text(), "tst999")
    assert payload["work_id"] == "tst999"
    assert "tst999" in payload["card_title"]
    assert "probe ok" in payload["probe_output"]
    assert "8 passed" in payload["selftest_output"]
    assert payload["exit_codes"] == {"test": 0, "compile": 0, "lint": 0}
    assert payload["maintenance"]["plan_sync"] == "是"
    assert payload["maintenance"]["lesson"] == "有"
    assert payload["maintenance"]["readme"] == "否"
    assert payload["evidence"]["commits"] == ["abc1234"]
    assert isinstance(payload["evidence"]["diff_stat"], str)


def test_convert_file_writes_sidecar(tmp_path: Path) -> None:
    src = tmp_path / "tst999-ccc-result.md"
    dst = tmp_path / "tst999-ccc-result.json"
    src.write_text(_result_text(), encoding="utf-8")
    convert_file(src, dst, "tst999")
    payload = json.loads(dst.read_text(encoding="utf-8"))
    assert payload["work_id"] == "tst999"
    assert payload["selftest_output"].startswith("- 8 passed")
    assert payload["evidence"]["commits"] == ["abc1234"]


def test_parse_missing_section_raises() -> None:
    text = _result_text().replace("## 1. 探针输出\n", "", 1)
    try:
        parse_result(text, "tst999")
    except ValueError:
        return
    raise AssertionError("expected ValueError for incomplete contract")


def _a2_card_text(work_id: str = "tst999") -> str:
    return (
        "# 任务卡 tst999 · smoke: sidecar（开发执行体 执行）\n"
        "> 关联：tst-plan-001 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：tst · 日期：2026-09-06\n"
        "## 目标\n占位\n"
        "## 回写区\n\n**执行体**：DSH · 日期：\n"
        "## 维护区\n\n1. **方案同步**：是/否\n"
        "2. **教训沉淀**：有/无\n"
    )


def test_apply_executor_result_json_sidecar_priority(tmp_path, monkeypatch):
    """JSON sidecar 存在 → 引擎优先读 JSON 收单（不回退 markdown split）。"""
    from server.engine.main import _apply_executor_result_to_card
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / "tst999-smoke.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(_a2_card_text(), encoding="utf-8")

    result_md = tmp_path / "logs" / "tst999-ccc-result.md"
    result_md.parent.mkdir(parents=True)
    result_md.write_text(_result_text(), encoding="utf-8")
    result_json = tmp_path / "logs" / "tst999-ccc-result.json"
    payload = parse_result(_result_text(), "tst999")
    result_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    work = Work(id="tst999", role="开发执行体", card_path=str(card_path))
    monkeypatch.setattr("server.git_sync.resolve_repo_root", lambda *a, **k: tmp_path)
    monkeypatch.setattr(
        "server.engine.main.subprocess.run",
        lambda cmd, **kw: MagicMock(returncode=1 if "--quiet" in cmd else 0),
    )

    ok, err = _apply_executor_result_to_card(work, result_md, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    text = card_path.read_text(encoding="utf-8")
    assert "状态：已回写" in text, text
    assert "## 回写区" in text
    assert "tst999 · smoke: sidecar" in text
    assert "## 维护区" in text
    # P1.3 修订：JSON sidecar 的 maintenance_notes（完整说明）映射进卡面；勾选值仍来自 maintenance
    assert "1. **方案同步**：[是] " in text
    assert "方案已推进" in text
    assert "2. **教训沉淀**：[有] " in text


def test_apply_executor_result_missing_json_falls_back_to_markdown(tmp_path, monkeypatch):
    """JSON sidecar 缺失 → 回退 markdown 四段 split（兼容窗口完整保留）。"""
    from server.engine.main import _apply_executor_result_to_card
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / "tst998-smoke.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(_a2_card_text("tst998"), encoding="utf-8")

    result_md = tmp_path / "logs" / "tst998-ccc-result.md"
    result_md.parent.mkdir(parents=True)
    result_md.write_text(_result_text("tst998"), encoding="utf-8")

    work = Work(id="tst998", role="开发执行体", card_path=str(card_path))
    monkeypatch.setattr("server.git_sync.resolve_repo_root", lambda *a, **k: tmp_path)
    monkeypatch.setattr(
        "server.engine.main.subprocess.run",
        lambda cmd, **kw: MagicMock(returncode=1 if "--quiet" in cmd else 0),
    )

    ok, err = _apply_executor_result_to_card(work, result_md, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    text = card_path.read_text(encoding="utf-8")
    assert "状态：已回写" in text
    assert "## 维护区" in text
    assert "方案同步：[是] 方案已推进" in text

def test_annotation_fulfillment_in_sidecar(tmp_path):
    """P1.3+：JSON sidecar 必须携带批注落实段，供引擎批注 fail-closed 校验。"""
    from server.engine.result_sidecar import parse_result
    md = (
        "## 0. 卡标题复述\n\nxy061\n\n"
        "## 人工批注落实\n\n1. running 无产物：已落实（server.py:1969）\n\n"
        "## 1. 探针输出\n\nprobe\n\n"
        "## 2. 自测输出\n\ntest ok\n\n"
        "## 3. 维护区四问\n\n1. **方案同步**：[是] ok\n2. **教训沉淀**：[无] ok\n3. **档案/README**：[否] ok\n4. **线路图**：[否] ok\n\n"
        "## 4. 变更证据\n\ncommit=abc1234\n"
    )
    payload = parse_result(md, "xy061")
    assert "已落实" in payload["annotation_fulfillment"]
