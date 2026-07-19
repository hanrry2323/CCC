"""hub_voice boss-mode / light-mode prefix"""

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
    assert "怎么解决拥塞？" in out
    assert out.count("【Hub 对话人格") == 1
    again = wrap_hub_prompt(out)
    assert again.count("【Hub 对话人格") == 1
    assert "禁止" in HUB_BOSS_VOICE
    assert "ccc-transfer" in HUB_BOSS_VOICE
    assert "定稿块" in HUB_BOSS_VOICE


def test_light_mode_short_prefix():
    from hub_voice import HUB_LIGHT_VOICE, resolve_prompt_mode, wrap_hub_prompt

    assert resolve_prompt_mode("稳态OK", requested="light") == "light"
    out = wrap_hub_prompt("稳态OK", mode="light")
    assert "轻量" in out
    assert "老板模式" not in out
    assert len(out) < len(HUB_LIGHT_VOICE) + 40
    # 定稿关键词强制 full
    assert resolve_prompt_mode("请定稿转任务", requested="light") == "full"
    full = wrap_hub_prompt("请定稿转任务", mode="light")
    assert "老板模式" in full
