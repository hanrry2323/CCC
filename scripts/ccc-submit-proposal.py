#!/usr/bin/env python3
"""ccc-submit-proposal.py — M1 端 CLI：读方案文件 → POST Hub API。

契约：docs/product/ccc-new-architecture-overview.md 四层分工。
- IDE 只谈方案，写方案到 docs/intent-proposals/（或任意路径）
- 本 CLI 读方案文件 → POST Hub /api/desktop/proposal → Hub 触发 2017 splitter 拆卡

Usage:
  ccc-submit-proposal <file> [--project <project_id>] [--skill <skill_ref>] [--wait]
  ccc-submit-proposal --flush-outbox
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HUB_URL = os.environ.get("CCC_HUB_URL", "http://127.0.0.1:17777").rstrip("/")
HUB_USER = os.environ.get("CCC_CHAT_USER", "ccc")
HUB_PASS = os.environ.get("CCC_CHAT_PASS", "ccc")
OUTBOX_DIR = Path.home() / ".ccc" / "proposal-outbox"
DEFAULT_SKILL_REF = "skills/write-code"
DEFAULT_PROMPT_REF = "prompts/write-code-prompt"
POLL_INTERVAL_S = 3
POLL_TIMEOUT_S = 180

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONT_RE.match(text.strip() + ("\n" if not text.endswith("\n") else ""))
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta, (m.group(2) or "").strip()


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(f"{HUB_USER}:{HUB_PASS}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _post_to_hub(body: dict) -> dict:
    """POST /api/desktop/proposal；网络失败 raise urllib.error.URLError。"""
    url = f"{HUB_URL}/api/desktop/proposal"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_auth_header(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def _get_result(proposal_id: str, project_id: str) -> dict:
    url = f"{HUB_URL}/api/desktop/proposal/{proposal_id}/result?project_id={project_id}"
    req = urllib.request.Request(url, headers=_auth_header(), method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _write_outbox(body: dict) -> Path:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    safe = re.sub(r"[^a-zA-Z0-9_-]", "-", body.get("title", "untitled"))[:40]
    path = OUTBOX_DIR / f"{ts}-{safe}.json"
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _flush_outbox() -> int:
    """批量重试 outbox 中的方案。返回成功数。"""
    if not OUTBOX_DIR.is_dir():
        print(f"[outbox] 无 outbox 目录: {OUTBOX_DIR}")
        return 0
    files = sorted(OUTBOX_DIR.glob("*.json"))
    if not files:
        print("[outbox] 无待重试方案")
        return 0
    ok = 0
    for path in files:
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            print(f"[outbox] 重试 {path.name} ...", end=" ")
            result = _post_to_hub(body)
            if result.get("ok"):
                print(f"✓ proposal_id={result.get('proposal_id')}")
                path.unlink()
                ok += 1
            else:
                print(f"✗ {result.get('error', 'unknown')}")
        except Exception as exc:
            print(f"✗ {exc}")
    print(f"[outbox] 成功 {ok}/{len(files)}")
    return ok


def _poll_result(proposal_id: str, project_id: str) -> int:
    """阻塞轮询直到 status=ok|failed。返回 exit code。"""
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            data = _get_result(proposal_id, project_id)
            status = data.get("status", "queued")
            cards = data.get("cards_produced", 0)
            print(f"[poll] status={status} cards={cards}", flush=True)
            if status == "ok":
                print(f"[poll] ✓ 拆卡完成 proposal_id={proposal_id} cards={cards}")
                return 0
            if status == "failed":
                print(f"[poll] ✗ 拆卡失败 proposal_id={proposal_id} error={data.get('error','')}")
                return 1
        except Exception as exc:
            print(f"[poll] 查询失败: {exc}", flush=True)
        time.sleep(POLL_INTERVAL_S)
    print(f"[poll] ✗ 超时 {POLL_TIMEOUT_S}s proposal_id={proposal_id}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="提交方案文件到 Hub，触发 splitter 拆卡",
    )
    parser.add_argument("file", nargs="?", help="方案文件路径（.md）")
    parser.add_argument("--project", default="", help="目标 project_id（覆盖 frontmatter）")
    parser.add_argument("--skill", default="", help="skill_ref（覆盖 frontmatter）")
    parser.add_argument("--prompt", default="", help="prompt_ref（覆盖 frontmatter）")
    parser.add_argument("--wait", action="store_true", help="阻塞轮询直到拆卡完成")
    parser.add_argument("--flush-outbox", action="store_true", help="批量重试 outbox")
    args = parser.parse_args(argv)

    if args.flush_outbox:
        return 0 if _flush_outbox() >= 0 else 1

    if not args.file:
        parser.error("需要提供方案文件路径，或使用 --flush-outbox")

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.is_file():
        print(f"[error] 文件不存在: {file_path}", file=sys.stderr)
        return 1

    text = file_path.read_text(encoding="utf-8")
    meta, body_md = _parse_frontmatter(text)

    project_id = (args.project or meta.get("project_id") or meta.get("project") or "").strip()
    skill_ref = (args.skill or meta.get("skill_ref") or DEFAULT_SKILL_REF).strip()
    prompt_ref = (args.prompt or meta.get("prompt_ref") or DEFAULT_PROMPT_REF).strip()
    title = (meta.get("title") or file_path.stem).strip()

    if not project_id:
        print("[error] 缺少 project_id（--project 或 frontmatter project_id）", file=sys.stderr)
        return 1

    # proposal_md：frontmatter 之后的正文；若无 frontmatter 则整文件
    proposal_md = body_md if body_md else text

    request_body = {
        "project_id": project_id,
        "proposal_md": proposal_md,
        "title": title,
        "skill_ref": skill_ref,
        "prompt_ref": prompt_ref,
    }

    print(f"[submit] project={project_id} skill={skill_ref} title={title[:60]}")
    try:
        result = _post_to_hub(request_body)
    except (urllib.error.URLError, OSError) as exc:
        out = _write_outbox(request_body)
        print(f"[outbox] Hub 不可达 ({exc}) → 已落盘 {out}", file=sys.stderr)
        print(f"[outbox] 重试: ccc-submit-proposal --flush-outbox", file=sys.stderr)
        return 1

    if not result.get("ok"):
        print(f"[error] Hub 拒绝: {result.get('error', 'unknown')}", file=sys.stderr)
        return 1

    proposal_id = result.get("proposal_id", "")
    print(f"[submit] ✓ queued proposal_id={proposal_id}")
    print(f"[submit] 结果查询: {HUB_URL}/api/desktop/proposal/{proposal_id}/result?project_id={project_id}")

    if args.wait and proposal_id:
        return _poll_result(proposal_id, project_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
