"""_jsonl_rotate.py — Phase 4.3: jsonl 轮转写入 + tail-style 读取

提供 RotatingFileHandler 风格的 jsonl 封装：
- 写：append；超过 max_bytes 则 rotate（.1 → .2 → .3，原文件移走）
- 读：tail-style 从文件末尾向前读最近 N 条（避免整文件 splitlines）

适用：failures.jsonl / events.jsonl / upstream-probe.jsonl /
     flow-events.jsonl / engine-restarts.jsonl
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5MB
DEFAULT_BACKUP_COUNT = 3


def rotate_if_needed(path: Path, max_bytes: int = DEFAULT_MAX_BYTES, backup_count: int = DEFAULT_BACKUP_COUNT) -> bool:
    """文件超过 max_bytes 则轮转：path → path.1 → path.2 → ... → path.{backup_count}（丢弃）"""
    try:
        if not path.is_file():
            return False
        size = path.stat().st_size
        if size < max_bytes:
            return False
    except OSError:
        return False
    # .{n-1} → .{n}（从高到低，避免覆盖）
    for i in range(backup_count - 1, 0, -1):
        src = path.with_suffix(path.suffix + f".{i}")
        dst = path.with_suffix(path.suffix + f".{i + 1}")
        if src.is_file():
            try:
                src.replace(dst)
            except OSError:
                pass
    # path → path.1
    try:
        path.replace(path.with_suffix(path.suffix + ".1"))
    except OSError:
        return False
    return True


def append_jsonl(path: Path, record: dict, *, max_bytes: int = DEFAULT_MAX_BYTES, backup_count: int = DEFAULT_BACKUP_COUNT) -> None:
    """append 一条 jsonl；先检查轮转。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    rotate_if_needed(path, max_bytes=max_bytes, backup_count=backup_count)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def tail_read_jsonl(path: Path, last: int = 200) -> list[dict[str, Any]]:
    """从文件末尾向前读最近 last 条 jsonl 记录。

    策略：从末尾向前按块读，累积足够行后解析；轮转备份文件（.1/.2/.3）
    在主文件不足时依次补充。
    """
    if last <= 0 or not path.is_file():
        return _tail_read_all([path]) if path.is_file() else []

    # 主文件 + 备份（按时间顺序：.3 最旧 → 主文件最新）
    candidates = []
    for i in range(DEFAULT_BACKUP_COUNT, 0, -1):
        b = path.with_suffix(path.suffix + f".{i}")
        if b.is_file():
            candidates.append(b)
    candidates.append(path)

    # 从最新文件末尾向前收集行
    lines: list[str] = []
    remaining = last
    for f in reversed(candidates):
        if remaining <= 0:
            break
        got = _tail_lines(f, remaining)
        lines = got + lines  # 旧文件行在前
        remaining -= len(got)

    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out


def _tail_read_all(paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in paths:
        if not p.is_file():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        out.append(obj)
                except json.JSONDecodeError:
                    continue
        except OSError:
            continue
    return out


def _tail_lines(path: Path, n: int) -> list[str]:
    """从文件末尾向前读 n 行（不含末尾换行）。"""
    if n <= 0 or not path.is_file():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return []
            chunk_size = 4096
            pos = size
            lines: list[str] = []
            tail = b""
            while pos > 0 and len(lines) < n:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size)
                tail = chunk + tail
                parts = tail.split(b"\n")
                # 最末一段可能不完整（除非已到文件头）→ 留给下次
                if pos > 0:
                    tail = parts[0]
                    complete = parts[1:]
                else:
                    tail = b""
                    complete = parts
                for line in reversed(complete):
                    if line:
                        lines.append(line.decode("utf-8", errors="replace"))
                    if len(lines) >= n:
                        break
            if tail and len(lines) < n:
                lines.append(tail.decode("utf-8", errors="replace"))
            lines.reverse()
            return lines[:n]
    except OSError:
        return []
