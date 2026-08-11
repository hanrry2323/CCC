#!/usr/bin/env python3
"""sync-skills —— skill 一键下发/校验（role-skills 一致性 · ccc-plan-020 A 轨第 4 项）

从 CCC 仓 skill 仓库同步到各节点 skill 目录 + 校验版本一致。
解决「skill 本体三处手工 scp 不同步」缺口。

skill 仓库：
  server/config/opencode-skills/<name>/  → ~/.opencode/skills/<name>
  server/config/claude-skills/<name>/    → ~/.claude/skills/<name>

节点（host 空=本机）：
  M1   （本机）        host=""
  2017 （fan@192.168.3.116）
  252  （待配置）       host=""  # TODO: 接入后填

用法：
  scripts/sync-skills.py                 # 下发所有节点 + 校验
  scripts/sync-skills.py --check         # 仅校验版本一致
  scripts/sync-skills.py --node 2017     # 只同步指定节点
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENCOTE_SRC = PROJECT_ROOT / "server" / "config" / "opencode-skills"
CLAUDE_SRC = PROJECT_ROOT / "server" / "config" / "claude-skills"

NODES = {
    "M1": {"host": ""},
    "2017": {"host": "fan@192.168.3.116"},
    "252": {"host": ""},  # TODO: 252 接入后填 ssh 目标
}

HOME_DIR = Path.home()
SKILL_DIRS = {
    "opencode": ("opencode-skills", str(HOME_DIR / ".opencode" / "skills")),
    "claude": ("claude-skills", str(HOME_DIR / ".claude" / "skills")),
}


def log(msg: str) -> None:
    print(f"[sync-skills] {msg}")


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def remote_cmd(host: str, cmd: str) -> str:
    if not host:
        res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    else:
        res = subprocess.run(["ssh", "-o", "ConnectTimeout=8", host, cmd], capture_output=True, text=True)
    return res.stdout.strip()


def remote_hash(host: str, path: str) -> str | None:
    out = remote_cmd(host, f"md5 -q {path} 2>/dev/null || md5sum {path} 2>/dev/null | awk '{{print $1}}'")
    return out or None


def sync_one(host: str, src_dir: Path, dst_rel: str, name: str, check_only: bool) -> None:
    src = src_dir / name
    if not src.is_dir():
        log(f"跳过（仓无 skill）: {name}")
        return
    dst = f"{dst_rel}/{name}"
    src_hash = file_hash(src / "SKILL.md")
    dst_hash = remote_hash(host, f"{dst}/SKILL.md")
    if check_only:
        if src_hash == dst_hash:
            log(f"OK: {name} @ {host or '本机'}（hash 一致）")
        else:
            log(f"MISMATCH: {name} @ {host or '本机'}（仓={src_hash} 节点={dst_hash or '缺失'}）→ 需 sync")
        return
    # 下发（rsync --delete 保持与仓一致；排除 __pycache__）
    cmd = f"mkdir -p {dst_rel}"
    remote_cmd(host, cmd)
    dst_full = dst if not host else f"{host}:{dst}"
    rsync_cmd = ["rsync", "-az", "--delete", "--exclude", "__pycache__", f"{src}/", f"{dst_full}/"]
    res = subprocess.run(rsync_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"SYNC FAIL: {name} → {dst_full}: {res.stderr.strip()[:120]}")
        return
    log(f"SYNCED: {name} → {host or '本机'}:{dst}")


def main() -> None:
    check_only = "--check" in sys.argv
    target = None
    if "--node" in sys.argv:
        idx = sys.argv.index("--node")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
    opencode_names = sorted(d.name for d in OPENCOTE_SRC.iterdir() if d.is_dir())
    claude_names = sorted(d.name for d in CLAUDE_SRC.iterdir() if d.is_dir())
    log(f"skill 仓库: opencode={' '.join(opencode_names) or '空'} claude={' '.join(claude_names) or '空'}")
    for node, meta in NODES.items():
        if target and target != node:
            continue
        host = meta["host"]
        log(f"── 节点 {node}（host={host or '本机'}）──")
        for name in opencode_names:
            sync_one(host, OPENCOTE_SRC, "~/.opencode/skills", name, check_only)
        for name in claude_names:
            sync_one(host, CLAUDE_SRC, "~/.claude/skills", name, check_only)
    log(f"完成（check={check_only}）")


if __name__ == "__main__":
    main()
