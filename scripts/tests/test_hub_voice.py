"""Desktop 对话人格（boss / light）前缀"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "chat_server"))


def test_wrap_hub_prompt_prefixes_and_idempotent():
    from hub_voice import HUB_BOSS_VOICE, wrap_hub_prompt

    out = wrap_hub_prompt("怎么解决拥塞？")
    assert "老板模式" in out
    assert "Desktop 对话人格" in out
    assert "怎么解决拥塞？" in out
    assert out.count("【Desktop 对话人格") == 1
    again = wrap_hub_prompt(out)
    assert again.count("【Desktop 对话人格") == 1
    assert "禁止" in HUB_BOSS_VOICE
    assert "ccc-transfer" in HUB_BOSS_VOICE
    assert "定稿块" in HUB_BOSS_VOICE
    assert "Mac2017 Engine" in HUB_BOSS_VOICE
    assert "中转站" in HUB_BOSS_VOICE  # 禁止口径里会提到，用于禁令
    assert "禁止**出现" in HUB_BOSS_VOICE or "禁止出现" in HUB_BOSS_VOICE or "`flash` 中转站" in HUB_BOSS_VOICE



def test_light_mode_short_prefix():
    from hub_voice import HUB_LIGHT_VOICE, resolve_prompt_mode, wrap_hub_prompt

    assert resolve_prompt_mode("稳态OK", requested="light") == "light"
    out = wrap_hub_prompt("稳态OK", mode="light")
    assert "轻量" in out
    assert "老板模式" not in out
    assert "Desktop 对话人格" in out
    assert len(out) < len(HUB_LIGHT_VOICE) + 40
    # 定稿关键词强制 full
    assert resolve_prompt_mode("请定稿转任务", requested="light") == "full"
    full = wrap_hub_prompt("请定稿转任务", mode="light")
    assert "老板模式" in full


def test_legacy_hub_marker_idempotent():
    from hub_voice import wrap_hub_prompt

    legacy = "【Hub 对话人格 · 老板模式 · 强制】\nold\n---\n你好"
    assert wrap_hub_prompt(legacy) == legacy
