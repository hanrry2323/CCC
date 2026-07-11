"""test_build_prompt.py — 单元测试

验证 _build_prompt.py 的 prompt 构建逻辑，确保受 P1 约束。
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from _build_prompt import build_product_prompt


async def test_default_template():
    """测试默认模板（无 executor_path）"""
    result = await build_product_prompt()
    assert "redacted" in result
    assert "async function" in result
    print("✓ default_template 包含必要的样板")


async def test_custom_executor_path():
    """测试自定义 executor_path 挂载"""
    result = await build_product_prompt(executor_path=".pdf/text/none")
    assert ".pdf/text/none" in result
    assert 'return ".pdf/text/none"' in result
    print("✓ custom_executor_path .pdf/text/none 正确挂载")


async def test_custom_template_file():
    """测试自定义模板文件"""
    # 创建临时模板文件
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir) / "custom_template.md"
        tmppath.write_text("CUSTOM {{executor_path}} TEST")

        result = await build_product_prompt(
            template_path=tmppath, executor_path=".html/preview"
        )
        assert "CUSTOM .html/preview TEST" in result
        print("✓ custom_template_file 正确渲染")


if __name__ == "__main__":
    asyncio.run(test_default_template())
    asyncio.run(test_custom_executor_path())
    asyncio.run(test_custom_template_file())
    print("\n✓ test_build_prompt.py 全部通过")
