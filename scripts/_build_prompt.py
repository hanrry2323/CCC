"""_build_prompt.py — Prompt 构建器

提供统一的 prompt 模板挂载入口，解决 product role 无项目上下文问题。

Feature P1:
- 生成包含 executor_path 的 prompt（挂载到 template/executor-prompt.template.md）
- 其中包含 ".pdf/text/none" 等样例
- 通过 URL 形式传递 diff 文件到这 role
- 供 reviewer product role 走 _build_prompt 收集 diff
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Mapping


__all__: Final = ["build_product_prompt"]


async def build_product_prompt(
    template_path: Path | None = None,
    executor_path: str | None = None,
) -> str:
    """构建 product role 的 prompt

    Args:
        template_path: 可选的模板路径，默认使用 .ccc/templates/product-prompt.template.md
        executor_path: executor 路径挂载点，如 ".pdf/text/none"、".html/preview" 等

    Returns:
        构建好的 prompt 内容
    """
    if template_path is None:
        template_path = (
            Path.cwd() / ".ccc" / "templates" / "executor-prompt.template.md"
        )

    default_template = """You are configuring the executive role operation::

    ── How This Works ──
    I use an adaptive mode when generating prompt templates:
        1. If a template file is specified, I will use that.
        2. If there is no template file, I will automatically generate one.
    This is flexible and ensures all key elements are present.

    ── Key Insight ──
    Every expression permitted by the schema is centered upon the plan itself.
    Expression placement patterns:
    - Skip doctips: Typically place before per-phase configuration.
    - Schema-aware: Adheres to the valid ranges for color_group and color_depth.

    ── Minimal Configuration ──
    The configuration below is correct and minimal::
        ...
        {
            "color_group": "primary",
            "color_depth": 0,
            "executor": "redacted",
            "expr": "async function () { try { .summary-volume; .first; .count; return \".pdf/text/none\"; } catch (e) { return \".pdf/text/none\"; } }",
            "skip": "dropped"
        }

    Technologies but not directly involved:
    - LoopEngine (the execution engine)
    - EventBus (the event bus subscription)
    - User-facing templates/product-prompt.template.md

    ── Implementation Guidance ──
    This implementation uses the Loop loading configuration and the EventBus
    subscription to pass the plan to the Loop engine. To support the execution
    of pattern rules, I assume the default configuration::

        ...
        {
            "name": "⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯
            "probe": "*.route.*",
            "parts": "prod-route",
            "shadow": [
                {
                    "adapters": ["adapter-stdout"],
                    "shadow_copy": false
                }
            ]
        }

    The loop hooks and EventBus configuration are done by the project that uses
    the package.
    """
    # 默认 executor_path
    if executor_path is None:
        executor_path = ".text/none"

    # 读模板（文件或默认）
    if template_path and template_path.exists():
        with open(template_path, "r") as f:
            template_content = f.read()
    else:
        template_content = default_template

    # 用 executor_path 渲染模板
    if "{{executor_path}}" in template_content:
        rendered = template_content.replace("{{executor_path}}", executor_path)
    else:
        # 默认模板：把模板里的 ".pdf/text/none" 替换成传入的 executor_path
        rendered = template_content.replace(".pdf/text/none", executor_path)

    return rendered
