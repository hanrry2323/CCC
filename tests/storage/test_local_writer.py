"""
Test cases for local_writer.py
"""

import os
import tempfile
from pathlib import Path

import pytest

from xianyu.storage.local_writer import write_local_output


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_write_local_output_success(temp_dir):
    """Test successful write of HTML and metadata."""
    output = write_local_output(
        title="测试标题",
        body="测试正文内容",
        image_paths=["./test_images/img1.jpg", "./test_images/img2.png"],
        output_dir=temp_dir,
    )

    assert output["success"] is True
    assert "output_path" in output
    assert "metadata_path" in output
    assert output["metadata"]["title"] == "测试标题"
    assert output["metadata"]["body"] == "测试正文内容"
    assert len(output["metadata"]["image_paths"]) == 2
    assert os.path.exists(output["output_path"])
    assert os.path.exists(output["metadata_path"])


def test_write_local_output_no_existing_directory(temp_dir):
    """Test that output directory is created if it doesn't exist."""
    # Use a non-existent subdirectory
    output_dir = os.path.join(temp_dir, "new_subdir", "nested", "path")
    output = write_local_output(
        title="测试", body="测试", image_paths=[], output_dir=output_dir
    )

    assert output["success"] is True
    # Verify all nested directories were created
    output_path = Path(output["output_path"])
    assert output_path.parent.exists()


def test_write_local_output_mixed_image_status(temp_dir):
    """Test with some images existing and some not."""
    output = write_local_output(
        title="测试",
        body="测试",
        image_paths=["./existing_path.jpg", "./nonexistent_path.jpg"],
        output_dir=temp_dir,
    )

    assert output["success"] is True
    # The HTML should still be generated even if one image is missing
    output_path = Path(output["output_path"])
    assert output_path.exists()


def test_write_local_output_special_characters(temp_dir):
    """Test handling of special characters in title and body."""
    title = "测试标题 & <script>alert('xss')</script>"
    body = "测试正文 <script>console.log('test')</script>"

    output = write_local_output(title, body, [], temp_dir)

    assert output["success"] is True
    html_content = Path(output["output_path"]).read_text(encoding="utf-8")
    # Verify HTML escaping
    assert "&amp;" in html_content
    assert "&lt;" in html_content


def test_write_local_output_json_metadata(temp_dir):
    """Test that metadata JSON is properly formatted."""
    output = write_local_output(
        title="测试",
        body="测试",
        image_paths=["./img1.jpg", "./img2.png"],
        output_dir=temp_dir,
    )

    assert output["success"] is True

    import json

    with open(output["metadata_path"], "r", encoding="utf-8") as f:
        metadata = json.load(f)

    assert metadata["title"] == "测试"
    assert metadata["body"] == "测试"
    assert "generated_at" in metadata
    assert "html_path" in metadata
    assert metadata["html_path"] == output["output_path"]


def test_write_local_output_non_ws_output(temp_dir):
    """Test output directory name is not in workspace."""
    workspace_dir = os.path.join(temp_dir, "workspace", "outputs")
    output_dir = os.path.join(workspace_dir, "image_text")

    output = write_local_output(
        title="测试标题", body="测试正文", image_paths=[], output_dir=output_dir
    )

    assert output["success"] is True
    # Verify structure matches spec
    output_path = Path(output["output_path"])
    assert "outputs" in str(output_path)
    assert "image_text" in str(output_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
