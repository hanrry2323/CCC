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

import base64
import hashlib
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENCOTE_SRC = PROJECT_ROOT / "server" / "config" / "opencode-skills"
CLAUDE_SRC = PROJECT_ROOT / "server" / "config" / "claude-skills"

NODES = {
    "M1": {"host": "", "windows": False},
    "2017": {"host": "fan@192.168.3.116", "windows": False},
    "252": {"host": "win@192.168.3.252", "windows": True},  # Windows Worker（W9）
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


def remote_cmd(host: str, cmd: str, timeout: int = 45) -> str:
    """执行远端命令；host 空=本机。SSH 不稳（252）用重试 + 长超时。"""
    if not host:
        res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
        return res.stdout.strip()
    last = ""
    for _ in range(4):  # 重试容错（252 banner 超时已知问题）
        try:
            res = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=30", "-o", "BatchMode=yes", host, cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            last = res.stdout.strip()
            if last or "timed out" not in res.stderr.lower():
                return last
        except subprocess.TimeoutExpired:
            last = ""
    return last


def remote_hash(host: str, path: str, windows: bool = False) -> str | None:
    if windows:
        # Windows：用 python hashlib（md5 -q 不存在）
        py = f"import hashlib;print(hashlib.md5(open(r'{path}','rb').read()).hexdigest())"
        out = remote_cmd(host, f'python -c "{py}"')
        return out if re_full_hex(out) else None
    out = remote_cmd(host, f"md5 -q {path} 2>/dev/null || md5sum {path} 2>/dev/null | awk '{{print $1}}'")
    return out if re_full_hex(out) else None


def re_full_hex(s: str) -> bool:
    return bool(s and len(s) == 32 and all(c in "0123456789abcdef" for c in s.lower()))


def sync_one(host: str, src_dir: Path, dst_rel: str, name: str, check_only: bool, windows: bool = False) -> None:
    src = src_dir / name
    if not src.is_dir():
        log(f"跳过（仓无 skill）: {name}")
        return
    dst = f"{dst_rel}/{name}"
    src_hash = file_hash(src / "SKILL.md")
    dst_hash = remote_hash(host, f"{dst}/SKILL.md", windows=windows)
    if check_only:
        if src_hash == dst_hash:
            log(f"OK: {name} @ {host or '本机'}（hash 一致）")
        else:
            log(f"MISMATCH: {name} @ {host or '本机'}（仓={src_hash} 节点={dst_hash or '缺失'}）→ 需 sync")
        return
    # 下发：Windows 用 base64+python（rsync 不可用）；类 Unix 用 rsync
    if windows:
        b64 = base64.b64encode((src / "SKILL.md").read_bytes()).decode()
        py = (
            f"import base64,os,sys;"
            f"d=r'{dst}';os.makedirs(d,exist_ok=True);"
            f"open(os.path.join(d,'SKILL.md'),'wb').write(base64.b64decode(sys.stdin.read()))"
        )
        res = subprocess.run(
            ["sh", "-c", f"echo '{b64}' | ssh -o ConnectTimeout=30 -o BatchMode=yes {host} 'python -c \"{py}\"'"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if res.returncode != 0:
            log(f"SYNC FAIL: {name} → {dst}（Windows）: {res.stderr.strip()[:100]}")
            return
        log(f"SYNCED: {name} → {host}:{dst}")
        return
    # 本机用绝对路径；远端用 ~（ssh 命令展开），rsync 目标用探明的远端绝对路径
    tail_kind = "claude" if "claude" in dst_rel else "opencode"
    if not host:
        mk_dst = dst
        remote_home = str(Path.home())
        rsync_dst = f"{remote_home}/.{tail_kind}/skills/{name}"
    else:
        mk_dst = dst_rel  # ssh 展开 ~
        remote_home = remote_cmd(host, "echo $HOME") or ""
        rsync_dst = f"{host}:{remote_home}/.{tail_kind}/skills/{name}"
    cmd = f"mkdir -p {mk_dst}"
    remote_cmd(host, cmd)
    rsync_cmd = ["rsync", "-az", "--delete", "--exclude", "__pycache__", f"{src}/", f"{rsync_dst}/"]
    res = subprocess.run(rsync_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"SYNC FAIL: {name} → {rsync_dst}: {res.stderr.strip()[:120]}")
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
        windows = bool(meta.get("windows"))
        # Windows 节点 skill 目录用绝对路径（~ 在 Windows OpenSSH 不展开）；
        # 本机用绝对路径；类 Unix 远端用 ~（ssh 命令展开，rsync 目标用探明的远端绝对路径）
        if windows:
            oc_dir, cl_dir = "C:/Users/win/.opencode/skills", "C:/Users/win/.claude/skills"
        elif not host:
            oc_dir, cl_dir = SKILL_DIRS["opencode"][1], SKILL_DIRS["claude"][1]
        else:
            oc_dir, cl_dir = "~/.opencode/skills", "~/.claude/skills"
        log(f"── 节点 {node}（host={host or '本机'}）──")
        for name in opencode_names:
            sync_one(host, OPENCOTE_SRC, oc_dir, name, check_only, windows=windows)
        for name in claude_names:
            sync_one(host, CLAUDE_SRC, cl_dir, name, check_only, windows=windows)
    log(f"完成（check={check_only}）")


if __name__ == "__main__":
    main()
