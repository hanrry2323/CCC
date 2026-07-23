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


def test_transfer_outbox_mental_model_locked():
    """转任务闭环口径：入队方 / 冲刷器 / 禁误说（防 Agent 读 flush.py 串台）。"""
    from hub_voice import HUB_BOSS_VOICE

    assert "转任务闭环" in HUB_BOSS_VOICE
    assert "确认入队方 = Desktop App" in HUB_BOSS_VOICE
    assert "唯一冲刷器 = sidecar" in HUB_BOSS_VOICE
    assert "禁止**把 sidecar" in HUB_BOSS_VOICE or "禁止把 sidecar" in HUB_BOSS_VOICE
    assert "不是** sidecar 解析入队" in HUB_BOSS_VOICE or "不是 sidecar 解析入队" in HUB_BOSS_VOICE
    assert "Hub 灯不挡确认" in HUB_BOSS_VOICE
    assert "transfer-receipts.json" in HUB_BOSS_VOICE
    assert "强制 enabled" in HUB_BOSS_VOICE
    assert "不自造" in HUB_BOSS_VOICE


def test_dual_layer_mind_locked_in_voice():
    from hub_voice import HUB_BOSS_VOICE

    assert "双层心智" in HUB_BOSS_VOICE
    assert "L0 不变核" in HUB_BOSS_VOICE
    assert "L1 项目脑" in HUB_BOSS_VOICE
    assert "禁止**你改写" in HUB_BOSS_VOICE or "禁止你改写" in HUB_BOSS_VOICE
    assert "live board" in HUB_BOSS_VOICE
    assert "禁止 invent" in HUB_BOSS_VOICE


def test_identity_core_keywords_subset_of_voice():
    """L0 身份 SSOT 关键词须出现在 hub_voice，防文档/注入漂移。"""
    from pathlib import Path

    from hub_voice import HUB_BOSS_VOICE

    identity = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "product"
        / "desktop-agent-identity.md"
    ).read_text(encoding="utf-8")
    for needle in (
        "双层心智",
        "确认不依赖 Hub",
        "红线 12",
        "不是** Cursor",
    ):
        assert needle in identity or needle.replace("**", "") in identity
    for needle in ("双层心智", "转任务闭环", "L0 不变核", "确认入队方 = Desktop App"):
        assert needle in HUB_BOSS_VOICE


def test_light_mode_short_prefix():
    from hub_voice import HUB_LIGHT_VOICE, resolve_prompt_mode, wrap_hub_prompt

    # light 已退役：resolve 恒 full；wrap 仍走老板人格
    assert resolve_prompt_mode("稳态OK", requested="light") == "full"
    out = wrap_hub_prompt("稳态OK", mode="light")
    assert "老板模式" in out
    assert "Desktop 对话人格" in out
    assert "ccc-transfer" in out or "定稿块" in out
    assert resolve_prompt_mode("请定稿转任务", requested="light") == "full"
    full = wrap_hub_prompt("请定稿转任务", mode="light")
    assert "老板模式" in full
    # 退役常量仍保留，供兼容引用
    assert "已退役" in HUB_LIGHT_VOICE


def test_legacy_hub_marker_idempotent():
    from hub_voice import wrap_hub_prompt

    legacy = "【Hub 对话人格 · 老板模式 · 强制】\nold\n---\n你好"
    assert wrap_hub_prompt(legacy) == legacy


def test_two_stage_flow_locked_in_voice():
    """主路径两段；对齐基线非硬门槛；板堵优先 board-repair；定稿后二级卡仅 title/备注。"""
    from hub_voice import HUB_BOSS_VOICE

    assert "主路径" in HUB_BOSS_VOICE
    assert "硬门槛" in HUB_BOSS_VOICE
    assert "board-repair" in HUB_BOSS_VOICE or "repair" in HUB_BOSS_VOICE
    assert "ready_for_task=false" in HUB_BOSS_VOICE
    assert "human_note" in HUB_BOSS_VOICE
    assert "退回对话重定稿" in HUB_BOSS_VOICE
    assert "四段流程" not in HUB_BOSS_VOICE


def test_sidecar_finalize_forces_lens_verify():
    """定稿不依赖点对齐基线，sidecar 仍注入强制 board+git；板堵优先 repair。"""
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "ccc-agent-sidecar.py").read_text(
        encoding="utf-8"
    )
    assert "定稿 · 强制核实" in src or "定稿/转任务 · 强制核实" in src
    assert "board-repair" in src or "repair" in src
    assert re.search(r"定稿|ccc-transfer|转任务契约", src)
