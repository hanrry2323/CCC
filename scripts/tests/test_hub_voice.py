"""hub_voice boss-mode prefix"""

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
