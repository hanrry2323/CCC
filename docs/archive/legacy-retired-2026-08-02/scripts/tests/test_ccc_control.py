"""tests for CCC control plane (_ccc_control.py)"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import _ccc_control as ctrl  # noqa: E402


@pytest.fixture()
def control_home(tmp_path, monkeypatch):
    monkeypatch.setattr(ctrl, "CONTROL_DIR", tmp_path)
    monkeypatch.setattr(ctrl, "CONTROL_FILE", tmp_path / "control.json")
    monkeypatch.setattr(ctrl, "DISABLED_SENTINEL", tmp_path / "DISABLED")
    monkeypatch.delenv("CCC_FOREGROUND", raising=False)
    return tmp_path


def test_default_mode_is_disabled(control_home):
    assert ctrl.get_mode() == "disabled"
    assert ctrl.is_disabled() is True
    assert ctrl.may_start_engine() is False
    assert ctrl.may_start_ui() is False
    assert ctrl.may_invent() is False


def test_ui_mode_allows_ui_not_engine(control_home):
    ctrl.set_mode("ui", reason="frontend")
    assert ctrl.get_mode() == "ui"
    assert ctrl.may_start_ui() is True
    assert ctrl.may_start_engine() is False
    assert ctrl.may_invent() is False
    assert ctrl.is_enabled() is False
    assert not ctrl.DISABLED_SENTINEL.exists()


def test_enable_is_queue_consumer(control_home):
    ctrl.set_mode("enabled", reason="test")
    assert ctrl.get_mode() == "enabled"
    assert ctrl.may_start_engine() is True
    assert ctrl.may_invent() is False
    assert ctrl.may_start_ui() is True
    data = json.loads(ctrl.CONTROL_FILE.read_text())
    assert data["policy"]["queue_consumer_only"] is True
    assert data["policy"]["invent_allowed"] is False


def test_invent_mode_hard_disabled(control_home):
    """v0.42.4: invent 永久禁用，set_mode 降级 enabled。"""
    out = ctrl.set_mode("invent", reason="flywheel")
    assert out["mode"] == "enabled"
    assert ctrl.may_invent() is False
    assert ctrl.may_auto_inject_tasks() is False
    s = ctrl.status_dict()
    assert s["invent_allowed"] is False
    assert s["invent_hard_disabled"] is True
    assert s["engine_allowed"] is True


def test_enable_disable_roundtrip(control_home):
    ctrl.set_mode("enabled", reason="test")
    assert not ctrl.DISABLED_SENTINEL.exists()
    ctrl.set_mode("disabled", reason="test stop")
    assert ctrl.get_mode() == "disabled"
    assert ctrl.DISABLED_SENTINEL.exists()
    assert ctrl.may_start_engine() is False


def test_legacy_disabled_sentinel_wins(control_home):
    ctrl.set_mode("enabled", reason="x")
    ctrl.DISABLED_SENTINEL.write_text("legacy\n")
    assert ctrl.get_mode() == "disabled"
    assert ctrl.may_start_engine() is False


def test_foreground_bypass(control_home, monkeypatch):
    assert ctrl.foreground_bypass() is False
    monkeypatch.setenv("CCC_FOREGROUND", "1")
    assert ctrl.foreground_bypass() is True


def test_status_dict(control_home):
    ctrl.set_mode("ui", reason="r")
    s = ctrl.status_dict()
    assert s["mode"] == "ui"
    assert s["enabled"] is False
    assert s["ui_allowed"] is True
    assert s["engine_allowed"] is False


def test_set_mode_source_whitelist_allows_known(control_home):
    """红线 12 实质化：白名单内的 source 必须接受。"""
    for src in ("cli", "hub", "task_dispatch", "daily_review", "ops_manual"):
        out = ctrl.set_mode("ui", reason=f"src={src}", source=src)
        assert out["source"] == src


def test_set_mode_source_whitelist_rejects_unknown(control_home):
    """红线 12 实质化：白名单外的 source 必须 raise ValueError。"""
    import pytest

    for src in ("agent", "auto", "test", "t", "any_random_string", ""):
        with pytest.raises(ValueError, match="invalid source"):
            ctrl.set_mode("enabled", reason="x", source=src)


def test_set_mode_source_whitelist_blocks_arbitrary_enable(control_home):
    """模拟历史漏洞：agent 直接 Python 调用 set_mode('enabled') 现在被拒。"""
    import pytest

    with pytest.raises(ValueError):
        ctrl.set_mode("enabled", reason="agent bootstrap", source="agent")
    assert ctrl.get_mode() == "disabled"  # 没改成


# ── 控制面 4 态迁移路径全覆盖（v0.62.0 形式化验证）──


def test_ui_to_disabled(control_home):
    """ui → disabled：sentinel 创建，engine 停止"""
    ctrl.set_mode("ui", reason="frontend")
    ctrl.set_mode("disabled", reason="stop")
    assert ctrl.get_mode() == "disabled"
    assert ctrl.may_start_engine() is False
    assert ctrl.may_start_ui() is False
    assert ctrl.DISABLED_SENTINEL.exists()


def test_ui_to_ui_idempotent(control_home):
    """ui → ui 幂等"""
    ctrl.set_mode("ui", reason="first")
    ctrl.set_mode("ui", reason="again")
    assert ctrl.get_mode() == "ui"
    assert ctrl.may_start_engine() is False
    assert ctrl.may_start_ui() is True


def test_ui_to_enabled(control_home):
    """ui → enabled"""
    ctrl.set_mode("ui", reason="frontend")
    ctrl.set_mode("enabled", reason="production")
    assert ctrl.get_mode() == "enabled"
    assert ctrl.may_start_engine() is True
    assert ctrl.may_start_ui() is True


def test_ui_to_invent_coerced(control_home):
    """ui → invent 被降级为 enabled（INVENT_HARD_DISABLED）"""
    ctrl.set_mode("ui", reason="frontend")
    out = ctrl.set_mode("invent", reason="try")
    assert out["mode"] == "enabled"
    assert ctrl.get_mode() == "enabled"
    assert ctrl.may_invent() is False
    assert ctrl.may_start_engine() is True


def test_enabled_to_ui(control_home):
    """enabled → ui"""
    ctrl.set_mode("enabled", reason="production")
    ctrl.set_mode("ui", reason="frontend")
    assert ctrl.get_mode() == "ui"
    assert ctrl.may_start_engine() is False
    assert ctrl.may_start_ui() is True
    assert not ctrl.DISABLED_SENTINEL.exists()


def test_enabled_to_enabled_idempotent(control_home):
    """enabled → enabled 幂等"""
    ctrl.set_mode("enabled", reason="first")
    ctrl.set_mode("enabled", reason="again")
    assert ctrl.get_mode() == "enabled"
    assert ctrl.may_start_engine() is True
    assert not ctrl.DISABLED_SENTINEL.exists()


def test_enabled_disabled_full_cycle(control_home):
    """enabled → disabled → enabled → disabled 完整流转"""
    ctrl.set_mode("enabled", reason="start")
    assert ctrl.get_mode() == "enabled"
    assert not ctrl.DISABLED_SENTINEL.exists()

    ctrl.set_mode("disabled", reason="stop")
    assert ctrl.get_mode() == "disabled"
    assert ctrl.DISABLED_SENTINEL.exists()

    ctrl.set_mode("enabled", reason="restart")
    assert ctrl.get_mode() == "enabled"
    assert not ctrl.DISABLED_SENTINEL.exists()

    ctrl.set_mode("disabled", reason="final stop")
    assert ctrl.get_mode() == "disabled"
    assert ctrl.DISABLED_SENTINEL.exists()


def test_get_mode_corrupted_json_fallback(control_home):
    """损坏 control.json 时降级 disabled"""
    ctrl.set_mode("enabled", reason="production")
    ctrl.CONTROL_FILE.write_text("这不是合法 json\n")
    assert ctrl.get_mode() == "disabled"


def test_get_mode_empty_json_fallback(control_home):
    """空文件降级 disabled"""
    ctrl.set_mode("enabled", reason="production")
    ctrl.CONTROL_FILE.write_text("")
    assert ctrl.get_mode() == "disabled"


def test_get_mode_dangling_mode_fallback(control_home):
    """mode 字段非法值降级 disabled"""
    import json

    ctrl.set_mode("enabled", reason="production")
    data = json.loads(ctrl.CONTROL_FILE.read_text())
    data["mode"] = "bogus"
    ctrl.CONTROL_FILE.write_text(json.dumps(data, ensure_ascii=False) + "\n")
    assert ctrl.get_mode() == "disabled"


def test_set_mode_invalid_value_raises(control_home):
    """非法 mode 字符串抛 ValueError"""
    import pytest

    with pytest.raises(ValueError, match="invalid mode"):
        ctrl.set_mode("invalid_mode")


def test_control_event_written_on_set_mode(control_home, monkeypatch):
    """set_mode 写入 control-events.jsonl"""
    import json

    # _emit_control_event 用 Path.home()/.ccc/stats/；
    # _ccc_control 内 Path 已 import 为模块级，需直接设 home
    fake_home = Path(str(control_home))
    monkeypatch.setattr(ctrl.Path, "home", lambda: fake_home)

    ctrl.set_mode("enabled", reason="production", source="cli")
    event_file = control_home / ".ccc" / "stats" / "control-events.jsonl"
    assert event_file.exists(), f"expected {event_file} to exist"
    lines = event_file.read_text().strip().split("\n")
    assert len(lines) >= 1
    event = json.loads(lines[-1])
    assert event["kind"] == "control_mode_change"
    assert event["mode"] == "enabled"
    assert event["source"] == "cli"
    assert event["pid"] > 0


def test_policy_field_schema(control_home):
    """policy 结构完整性"""
    import json

    ctrl.set_mode("enabled", reason="production")
    data = json.loads(ctrl.CONTROL_FILE.read_text())
    assert data["schema_version"] == "1.2"
    assert data["source"] == "cli"
    policy = data["policy"]
    assert policy["forbid_popen_engine"] is True
    assert policy["forbid_crontab_autostart"] is True
    assert policy["invent_allowed"] is False
    assert policy["invent_hard_disabled"] is True
    assert policy["queue_consumer_only"] is True
    assert policy["auto_inject_tasks"] is False
