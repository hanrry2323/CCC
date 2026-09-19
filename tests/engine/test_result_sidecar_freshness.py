"""D1 回归：JSON sidecar 新鲜度闸（2026-09-19 指令单 D1）。

根因：dsh-executor 按 work_id 命名 sidecar（不带轮次号），上一轮残留件遮蔽本轮
只写 markdown 的收单——xy079 run16/run17 把 12:07 陈旧空说明写进卡。
修复：json 与 markdown 同时存在时，仅当 json 不旧于 md 才采信 json，
否则记 warning 并走 markdown 分支；只有 json 无 md 仍采信 json（不回归）。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock


def _result_text(work_id: str = "d1a01") -> str:
    """构造完整契约 markdown 信封（节标题用执行体实际写法「## 维护区」）。"""
    return (
        f"# 执行结果 · {work_id} · smoke: d1\n"
        f"## 0. 卡标题复述\n\n{work_id} · smoke: d1\n"
        "## 1. 探针输出\n\n- probe ok\n"
        "## 2. 自测输出\n\n- 8 passed\n- test exit=0\n- lint=0\n"
        "## 维护区\n\n"
        "1. 方案同步：[是] 方案已推进\n"
        "2. 教训沉淀：[有] 见 lessons\n"
        "3. 档案/README：[否] 无变更\n"
        "4. 线路图：[否] 无变化\n"
        "## 4. 变更证据\n\ncommit=abc1234 branch=codex/d1a01 push=success\n"
    )


def _a2_card_text(work_id: str = "d1a01") -> str:
    return (
        f"# 任务卡 {work_id} · smoke: d1（开发执行体 执行）\n"
        f"> 关联：tst-plan-001 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：tst · 日期：2026-09-19\n"
        "## 目标\n占位\n"
        "## 回写区\n\n**执行体**：DSH · 日期：\n"
        "## 维护区\n\n1. **方案同步**：是/否\n"
        "2. **教训沉淀**：有/无\n"
    )


def _write_envelope(log_dir: Path, work_id: str) -> Path:
    result_md = log_dir / f"{work_id}-ccc-result.md"
    result_md.parent.mkdir(parents=True, exist_ok=True)
    result_md.write_text(_result_text(work_id), encoding="utf-8")
    return result_md


def _setup_card_and_work(tmp_path: Path, work_id: str):
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / f"{work_id}-smoke.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(_a2_card_text(work_id), encoding="utf-8")
    return card_path, Work(id=work_id, role="开发执行体", card_path=str(card_path))


def _mock_git(monkeypatch, tmp_path: Path) -> None:
    """把 repo 解析与 git 子进程都指向 tmp 隔离，避免任何生产 write 与真实 git。"""
    monkeypatch.setattr("server.git_sync.resolve_repo_root", lambda *a, **k: tmp_path)
    monkeypatch.setattr(
        "server.engine.main.subprocess.run",
        lambda cmd, **kw: MagicMock(returncode=1 if "--quiet" in cmd else 0),
    )


def _sidecar_text(work_id: str) -> str:
    """含完整 maintenance_notes 的新鲜 sidecar 内容。

    手构 payload 而非经 result_sidecar.parse_result：后者仍按旧硬编码「## 3. 维护区四问」
    解析（不在本单改动范围），而本测试的信封按执行体实际写法用无序号「## 维护区」，
    正是 xy079 现场情形。
    """
    return json.dumps(
        {
            "work_id": work_id,
            "card_title": f"{work_id} · smoke: d1",
            "probe_output": "- probe ok",
            "selftest_output": "- 8 passed\n- test exit=0\n- lint=0",
            "exit_codes": {"test": 0, "compile": 0, "lint": 0},
            "maintenance": {"plan_sync": "是", "lesson": "有", "readme": "否", "roadmap": "否"},
            "maintenance_notes": {
                "plan_sync": "方案已推进",
                "lesson": "见 lessons",
                "readme": "无变更",
                "roadmap": "无变化",
            },
            "annotation_fulfillment": "",
            "evidence": {"commits": ["abc1234"], "diff_stat": "1 file changed"},
        },
        ensure_ascii=False,
    )


def test_json_newer_than_md_trusts_json(tmp_path, monkeypatch):
    """正向：json 比 md 新 → 采信 json（maintenance_notes 全量进卡）。"""
    work_id = "d1a01"
    card_path, work = _setup_card_and_work(tmp_path, work_id)
    log_dir = tmp_path / "logs"
    result_md = _write_envelope(log_dir, work_id)
    result_json = log_dir / f"{work_id}-ccc-result.json"
    result_json.write_text(_sidecar_text(work_id), encoding="utf-8")
    # 让 json 明确新于 md：把 json 的 mtime 推到 md 之后
    md_ts = result_md.stat().st_mtime
    import os as _os

    _os.utime(result_json, (md_ts + 5, md_ts + 5))
    assert result_json.stat().st_mtime > result_md.stat().st_mtime

    _mock_git(monkeypatch, tmp_path)
    from server.engine.main import _apply_executor_result_to_card

    ok, err = _apply_executor_result_to_card(work, result_md, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    text = card_path.read_text(encoding="utf-8")
    # json 路径写回维护区四行说明完整
    assert "方案已推进" in text
    assert "见 lessons" in text


def test_json_older_than_md_falls_back_to_markdown(tmp_path, monkeypatch, caplog):
    """本缺陷回归：json 比 md 旧 → 走 markdown 分支且日志含「陈旧」字样。"""
    work_id = "d1a02"
    card_path, work = _setup_card_and_work(tmp_path, work_id)
    log_dir = tmp_path / "logs"
    result_md = _write_envelope(log_dir, work_id)
    result_json = log_dir / f"{work_id}-ccc-result.json"
    # 陈旧 json：内容是最小合法 payload，但 mtime 比 md 旧（写完后把 mtime 回拨）
    result_json.write_text(
        json.dumps(
            {
                "card_title": f"{work_id} · stale",
                "probe_output": "stale probe",
                "selftest_output": "stale selftest",
                "maintenance": {"plan_sync": "是", "lesson": "有", "readme": "否", "roadmap": "否"},
                "maintenance_notes": {"plan_sync": "", "lesson": "", "readme": "", "roadmap": ""},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    import os as _os

    old = result_json.stat().st_mtime
    result_md_ts = result_md.stat().st_mtime
    _os.utime(result_json, (old - 100, old - 100))  # json 回拨到 md 之前
    assert result_json.stat().st_mtime < result_md_ts

    _mock_git(monkeypatch, tmp_path)
    with caplog.at_level(logging.WARNING, logger="ccc.engine"):
        from server.engine.main import _apply_executor_result_to_card

        ok, err = _apply_executor_result_to_card(work, result_md, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    # 走 markdown 分支 → 维护区用信封的完整说明，而非陈旧 json 的空串
    text = card_path.read_text(encoding="utf-8")
    assert "方案已推进" in text
    assert "见 lessons" in text
    # 陈旧 json 的 maintenance_notes 三空绝不能进卡：四条说明都非空。
    # markdown 分支按信封原文写回（1. 方案同步：[是] …），JSON 路径则加粗，
    # 断言格式无关：匹配四问的编号+名+勾选，检查勾选后的说明段非空。
    import re as _re

    maint_lines = _re.findall(r"^\d+\. \*{0,2}(?:方案同步|教训沉淀|档案/README|线路图)\*{0,2}：\[(?:是|否|有|无)\]\s*(.*)$", text, _re.M)
    assert len(maint_lines) == 4, maint_lines
    assert all(ln.strip() for ln in maint_lines), maint_lines
    assert "陈旧" in caplog.text, caplog.text


def test_only_json_trusts_json(tmp_path, monkeypatch):
    """不回归：只有 json 无 md → 仍采信 json。"""
    work_id = "d1a03"
    card_path, work = _setup_card_and_work(tmp_path, work_id)
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    result_json = log_dir / f"{work_id}-ccc-result.json"
    result_json.write_text(_sidecar_text(work_id), encoding="utf-8")
    # 只有 json，无 md
    assert not (log_dir / f"{work_id}-ccc-result.md").exists()

    _mock_git(monkeypatch, tmp_path)
    from server.engine.main import _apply_executor_result_to_card

    result_md = log_dir / f"{work_id}-ccc-result.md"  # 传入的 result_path（仅用于推导 json 名）
    ok, err = _apply_executor_result_to_card(work, result_md, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    text = card_path.read_text(encoding="utf-8")
    assert "方案已推进" in text


def test_only_md_no_json_uses_markdown(tmp_path, monkeypatch):
    """正向：只有 md 无 json → markdown 分支（兼容窗口）。"""
    work_id = "d1a04"
    card_path, work = _setup_card_and_work(tmp_path, work_id)
    log_dir = tmp_path / "logs"
    result_md = _write_envelope(log_dir, work_id)
    assert not (log_dir / f"{work_id}-ccc-result.json").exists()

    _mock_git(monkeypatch, tmp_path)
    from server.engine.main import _apply_executor_result_to_card

    ok, err = _apply_executor_result_to_card(work, result_md, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    text = card_path.read_text(encoding="utf-8")
    assert "方案已推进" in text
