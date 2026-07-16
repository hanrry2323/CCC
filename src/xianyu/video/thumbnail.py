"""
智能封面图生成 — ffmpeg 关键帧提取 + PIL 文字叠加 + CLI。

分层设计：
  Layer 1 (ffmpeg async):  get_video_duration, extract_frame
  Layer 2 (pure func):      pick_thumbnail_time
  Layer 3 (PIL sync + combo): overlay_title, generate_thumbnail

复用 src/xianyu/video/templates.py 中的 _load_font (CJK 字体探测)。
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .templates import _load_font, _wrap_text


# ---------------------------------------------------------------------------
# Layer 1 — ffmpeg/ffprobe 异步子进程
# ---------------------------------------------------------------------------


async def get_video_duration(video_path: str) -> float:
    """Use ffprobe to get video duration in seconds."""
    if not os.path.isfile(video_path):
        raise RuntimeError(f"Video file not found: {video_path}")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed (rc={proc.returncode}): "
            f"{stderr.decode(errors='replace')[:200]}"
        )
    try:
        return float(stdout.decode(errors="replace").strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe output not parseable: {stdout!r}") from exc


async def extract_frame(
    video_path: str,
    output_path: str,
    time_sec: float,
    quality: int = 2,
) -> str:
    """Extract a single frame from *video_path* at *time_sec* using ffmpeg."""
    if not os.path.isfile(video_path):
        raise RuntimeError(f"Video file not found: {video_path}")
    if time_sec < 0:
        raise ValueError(f"time_sec must be >= 0, got {time_sec}")
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(time_sec),
        "-i",
        video_path,
        "-vframes",
        "1",
        "-q:v",
        str(quality),
        output_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg frame extraction failed (rc={proc.returncode}): "
            f"{stderr.decode(errors='replace')[:200]}"
        )
    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Layer 2 — 纯函数：帧选择策略
# ---------------------------------------------------------------------------


def pick_thumbnail_time(duration: float, strategy: str = "one_third") -> float:
    """Pick an optimal timestamp for thumbnail extraction.

    Strategies:
      - "one_third" (default): ~33% into the video — avoids title/end fades.
      - "middle": exact midpoint.
      - "start": ~5% in, min 1 s — suitable for Bilibili covers.
    """
    if duration <= 0:
        raise ValueError(f"duration must be > 0, got {duration}")
    strategies: dict[str, float] = {
        "one_third": duration * 0.33,
        "middle": duration * 0.5,
        "start": min(1.0, duration * 0.05),
    }
    t = strategies.get(strategy, duration * 0.33)
    return max(0.0, min(t, duration))


# ---------------------------------------------------------------------------
# Layer 3 — PIL 文字叠加 + 端到端生成
# ---------------------------------------------------------------------------


def _build_gradient_overlay(
    width: int,
    height: int,
    overlay_height_ratio: float = 0.3,
    max_alpha: int = 180,
) -> Image.Image:
    """Build an RGBA gradient overlay darkening the bottom of the image.

    Returns a ``width × height`` RGBA image, transparent at the top,
    fading to semi-transparent black at the bottom *overlay_height_ratio*
    portion.
    """
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    overlay_start_y = int(height * (1.0 - overlay_height_ratio))
    for y in range(overlay_start_y, height):
        # alpha = 0 at overlay_start_y, alpha = max_alpha at bottom
        progress = (y - overlay_start_y) / (height - overlay_start_y)
        alpha = int(progress * max_alpha)
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    return overlay


def _draw_title_text(
    draw: ImageDraw.Draw,
    title: str,
    width: int,
    height: int,
    font_size: int,
    text_position: str = "bottom",
) -> None:
    """Draw centred title text at the chosen vertical position."""
    # Determine text bounding area
    if text_position == "bottom":
        text_area_top = int(height * 0.60)
        text_area_bottom = int(height * 0.90)
    elif text_position == "center":
        text_area_top = int(height * 0.30)
        text_area_bottom = int(height * 0.70)
    elif text_position == "top":
        text_area_top = int(height * 0.10)
        text_area_bottom = int(height * 0.40)
    else:
        text_area_top = int(height * 0.60)
        text_area_bottom = int(height * 0.90)

    max_text_width = int(width * 0.85)
    font = _load_font(font_size)

    # Try to fit text — reduce font size if too wide
    actual_font = font
    actual_font_size = font_size
    glyph_w_approx = actual_font_size
    chars_per_line = max(1, max_text_width // glyph_w_approx)
    lines = _wrap_text(title, chars_per_line)

    line_height = int(actual_font_size * 1.4)
    total_height = len(lines) * line_height
    start_y = text_area_top + (text_area_bottom - text_area_top - total_height) // 2

    for i, line in enumerate(lines):
        bbox = actual_font.getbbox(line)
        line_w = (bbox[2] - bbox[0]) if bbox else 0
        x = (width - line_w) // 2
        y = start_y + i * line_height

        # Drop shadow
        draw.text((x + 3, y + 3), line, fill=(0, 0, 0, 200), font=actual_font)
        # White text
        draw.text((x, y), line, fill=(255, 255, 255), font=actual_font)


def overlay_title(
    image_path: str,
    title: str,
    output_path: str,
    *,
    width: int = 1080,
    height: int = 1920,
    font_size: int | None = None,
    text_position: str = "bottom",
) -> str:
    """Overlay title text on an image with a bottom gradient mask.

    Args:
        image_path: Source image (full-resolution frame).
        title:      Text to overlay.
        output_path: Output PNG/JPEG path.
        width:      Target thumbnail width.
        height:     Target thumbnail height.
        font_size:  Font size in px (default: ``max(48, height // 15)``).
        text_position: ``"bottom"``, ``"center"``, or ``"top"``.

    Returns:
        Absolute path to the output thumbnail.
    """
    resolved_font_size = font_size or max(48, height // 15)
    img = Image.open(image_path).convert("RGBA")
    img = img.resize((width, height), Image.LANCZOS)

    # Build & composite gradient overlay
    overlay = _build_gradient_overlay(width, height)
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    _draw_title_text(draw, title, width, height, resolved_font_size, text_position)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    # Convert to RGB before saving if output is JPEG
    out_lower = output_path.lower()
    if out_lower.endswith(".jpg") or out_lower.endswith(".jpeg"):
        rgb = Image.new("RGB", img.size, (0, 0, 0))
        rgb.paste(img, mask=img.split()[3])  # Use alpha as mask
        rgb.save(output_path, "JPEG", quality=92)
    else:
        img.save(output_path, "PNG")
    return os.path.abspath(output_path)


async def generate_thumbnail(
    video_path: str,
    title: str,
    output_path: str | None = None,
    *,
    width: int = 1080,
    height: int = 1920,
    time_sec: float | None = None,
    strategy: str = "one_third",
    font_size: int | None = None,
    text_position: str = "bottom",
    extract_quality: int = 2,
) -> str:
    """End-to-end: extract key frame → overlay title → save thumbnail.

    Args:
        video_path:     Input video file.
        title:          Title text to overlay on the thumbnail.
        output_path:    Desired output path (default: auto-named beside the video).
        width:          Thumbnail width.
        height:         Thumbnail height.
        time_sec:       Exact timestamp to extract. ``None`` = auto-pick via *strategy*.
        strategy:       Auto-pick strategy ('one_third', 'middle', 'start').
        font_size:      Font size for title overlay (default: ratio-based).
        text_position:  'bottom', 'center', or 'top'.
        extract_quality: ffmpeg -q:v value (1-31, lower = better).

    Returns:
        Absolute path to the generated thumbnail image.
    """
    video_path = str(video_path)
    title = str(title)

    # Resolve timestamp
    if time_sec is None:
        duration = await get_video_duration(video_path)
        time_sec = pick_thumbnail_time(duration, strategy)

    # Resolve output path
    if output_path is None:
        vid_stem = Path(video_path).stem
        vid_dir = Path(video_path).parent
        output_path = str(vid_dir / f"{vid_stem}_thumb.png")

    # Extract frame to temp location
    frame_hash = hashlib.md5(
        f"{video_path}:{time_sec}".encode(), usedforsecurity=False
    ).hexdigest()[:8]
    tmp_frame = os.path.join(tempfile.gettempdir(), f"xianyu_thumb_{frame_hash}.png")
    await extract_frame(video_path, tmp_frame, time_sec, quality=extract_quality)

    try:
        result = overlay_title(
            tmp_frame,
            title,
            output_path,
            width=width,
            height=height,
            font_size=font_size,
            text_position=text_position,
        )
    finally:
        # Clean up temp frame
        try:
            os.remove(tmp_frame)
        except OSError:
            pass

    return result
