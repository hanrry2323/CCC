#!/usr/bin/env python3
"""Generate placeholder icons for Tauri app."""

from PIL import Image, ImageDraw, ImageFont
import os
import subprocess
import sys

ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "src-tauri", "icons")
ICONS_DIR = os.path.abspath(ICONS_DIR)
os.makedirs(ICONS_DIR, exist_ok=True)


# Create a 1024x1024 source icon with "CCC" letters
def make_source(size=1024, text="CCC", bg=(28, 28, 32), fg=(120, 220, 232)):
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    # Draw a terminal-style box
    box_inset = size // 8
    draw.rectangle(
        [box_inset, box_inset, size - box_inset, size - box_inset],
        outline=(80, 80, 96),
        width=size // 64,
    )
    # Title bar
    title_h = size // 12
    draw.rectangle(
        [box_inset, box_inset, size - box_inset, box_inset + title_h],
        fill=(48, 48, 56),
    )
    # Three traffic-light dots
    dot_r = title_h // 4
    cy = box_inset + title_h // 2
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = box_inset + title_h // 2 + i * (title_h // 2 + dot_r * 2)
        draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=color)
    # Prompt arrow ">"
    try:
        font_size = size // 5
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()
    prompt = "$ "
    full_text = prompt + "ccc"
    bbox = draw.textbbox((0, 0), full_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - size // 12
    ty = (size - th) // 2 + size // 16
    draw.text((tx, ty), prompt, fill=(120, 220, 232), font=font)
    draw.text((tx + font_size // 2 * len(prompt), ty), "ccc", fill=fg, font=font)
    # Cursor block
    cursor_x = tx + tw + size // 64
    cursor_w = size // 32
    draw.rectangle([cursor_x, ty, cursor_x + cursor_w, ty + font_size], fill=fg)
    return img


def main():
    src = make_source()
    src_path = os.path.join(ICONS_DIR, "icon.png")
    src.save(src_path, "PNG")
    print(f"wrote {src_path}")

    sizes = [
        ("32x32.png", 32),
        ("128x128.png", 128),
        ("128x128@2x.png", 256),
    ]
    for name, sz in sizes:
        p = os.path.join(ICONS_DIR, name)
        src.resize((sz, sz), Image.LANCZOS).save(p, "PNG")
        print(f"wrote {p}")

    # Build .icns via iconutil
    iconset = os.path.join(ICONS_DIR, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    icns_specs = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]
    for name, sz in icns_specs:
        src.resize((sz, sz), Image.LANCZOS).save(os.path.join(iconset, name), "PNG")

    icns_path = os.path.join(ICONS_DIR, "icon.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns_path], check=True)
    print(f"wrote {icns_path}")

    # Build .ico for Windows compatibility
    ico_sizes = [
        (16, 16),
        (24, 24),
        (32, 32),
        (48, 48),
        (64, 64),
        (128, 128),
        (256, 256),
    ]
    base = src.copy()
    base.save(
        os.path.join(ICONS_DIR, "icon.ico"),
        format="ICO",
        sizes=ico_sizes,
    )
    print(f"wrote {os.path.join(ICONS_DIR, 'icon.ico')}")


if __name__ == "__main__":
    main()
