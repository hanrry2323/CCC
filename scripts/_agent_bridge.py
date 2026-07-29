#!/usr/bin/env python3
"""_agent_bridge.py — CCC Agent 文件桥接协议

FlowWeave 启发：Agent Protocol v1 的文件目录交换方案。

核心设计：
  不靠 socket/IPC，而是用文件目录作为交换协议。
  任何能读文件系统的 Agent 都能接入。

目录结构：
  root/.ccc/agent-bridge/<runId>/
    request.json    ← CCC 写：指令摘要 + 参数
    prompt.md       ← CCC 写：完整 prompt（markdown）
    instructions.md ← CCC 写：约束/安全规则
    response.json   → Agent 写：执行结果（原子 rename）
    artifacts/      → Agent 写：产出物

状态机：
  pending → in_progress → completed | failed

用法：
  from _agent_bridge import AgentBridge, BridgeRun
  bridge = AgentBridge("/path/to/project")
  run = bridge.create_run("project-scan", {"target": "src"})
  # ... Agent 处理 ...
  run.mark_completed({"status": "ok", "summary": "..."})
  result = bridge.poll_run(run.run_id)
"""

from __future__ import annotations
import json
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_BRIDGE_DIR = ".ccc" / Path("agent-bridge")

_RUN_STATUSES = ("pending", "in_progress", "completed", "failed")


class BridgeRun:
    """表示一次 Agent 桥接任务。"""

    def __init__(self, bridge: "AgentBridge", run_id: str, created_at: str, status: str, request: dict, prompt: str):
        self._bridge = bridge
        self.run_id = run_id
        self.created_at = created_at
        self.status = status
        self.request = request
        self.prompt = prompt

    @property
    def run_dir(self) -> Path:
        return self._bridge._bridge_dir / self.run_id

    @property
    def response_path(self) -> Path:
        return self.run_dir / "response.json"

    @property
    def response_staging_path(self) -> Path:
        return self.run_dir / ".response.json.tmp"

    def mark_in_progress(self) -> bool:
        """标记为进行中（原子写入 status.json）。"""
        return self._bridge._write_status(self.run_id, "in_progress")

    def mark_completed(self, response: dict) -> bool:
        """标记完成并写入 response（原子 rename 写入）。"""
        return self._bridge._write_response(self.run_id, response, status="completed")

    def mark_failed(self, error: str) -> bool:
        """标记失败。"""
        return self._bridge._write_response(self.run_id, {"error": error}, status="failed")

    def get_response(self) -> Optional[dict]:
        """读取 response。"""
        return self._bridge._read_response(self.run_id)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "status": self.status,
            "request": self.request,
            "prompt": self.prompt,
            "response": self.get_response(),
        }


class AgentBridge:
    """Agent 文件桥接入口。

    创建 run → Agent 处理 → 轮询/回调 → 获取结果
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self._bridge_dir = self.root / _BRIDGE_DIR
        self._bridge_dir.mkdir(parents=True, exist_ok=True)

    # ── 创建 Run ──

    def create_run(
        self,
        action: str,
        params: Optional[dict] = None,
        prompt: str = "",
        instructions: str = "",
    ) -> BridgeRun:
        """创建一次桥接任务。

        Args:
            action: 动作名，如 "project-scan", "diff-review", "batch-inspect"
            params: 参数字典
            prompt: 完整 prompt markdown
            instructions: 安全/约束指令
        Returns:
            BridgeRun 对象
        """
        run_id = _generate_run_id(action)
        now = _now_iso()

        run_dir = self._bridge_dir / run_id
        artifacts_dir = run_dir / "artifacts"
        run_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(exist_ok=True)

        request = {
            "run_id": run_id,
            "action": action,
            "params": params or {},
            "created_at": now,
        }

        # 原子写入
        self._atomic_write(run_dir / "request.json", request)
        self._atomic_write(run_dir / "prompt.md", prompt)
        if instructions:
            self._atomic_write(run_dir / "instructions.md", instructions)
        self._atomic_write(run_dir / "response.json", {"status": "pending", "error": None})
        self._atomic_write(run_dir / "status.json", {"status": "pending", "updated_at": now})

        return BridgeRun(
            bridge=self,
            run_id=run_id,
            created_at=now,
            status="pending",
            request=request,
            prompt=prompt,
        )

    # ── 轮询 ──

    def poll_run(self, run_id: str) -> Optional[BridgeRun]:
        """读取一个 run 的当前状态。"""
        run_dir = self._bridge_dir / run_id
        if not run_dir.exists():
            return None

        request = self._read_json(run_dir / "request.json") or {}
        status_data = self._read_json(run_dir / "status.json") or {}
        prompt = self._read_text(run_dir / "prompt.md") or ""

        return BridgeRun(
            bridge=self,
            run_id=run_id,
            created_at=request.get("created_at", ""),
            status=status_data.get("status", "unknown"),
            request=request,
            prompt=prompt,
        )

    def wait_run(
        self,
        run_id: str,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
    ) -> Optional[BridgeRun]:
        """轮询等待完成。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.poll_run(run_id)
            if run and run.status in ("completed", "failed"):
                return run
            time.sleep(poll_interval)
        return self.poll_run(run_id)

    def list_runs(self, status: Optional[str] = None) -> list[BridgeRun]:
        """列出所有桥接任务。"""
        runs = []
        if not self._bridge_dir.exists():
            return runs

        for entry in sorted(os.scandir(self._bridge_dir), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            run = self.poll_run(entry.name)
            if run is None:
                continue
            if status and run.status != status:
                continue
            runs.append(run)
        return runs

    # ── 清理 ──

    def cleanup(self, max_age_hours: float = 24) -> int:
        """清理过期任务。"""
        now = time.time()
        removed = 0
        for run in self.list_runs():
            run_dir = self._bridge_dir / run.run_id
            if not run_dir.exists():
                continue
            try:
                mtime = run_dir.stat().st_mtime
                if (now - mtime) / 3600 > max_age_hours:
                    shutil.rmtree(run_dir, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
        return removed

    # ── 内部 ──

    def _atomic_write(self, path: Path, data: Any) -> None:
        """原子写入 JSON 或文本文件。"""
        tmp = path.with_suffix(".tmp")
        is_json = path.suffix == ".json"
        try:
            if is_json:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(data)
            tmp.rename(path)
        except OSError:
            if tmp.exists():
                tmp.unlink()
            raise

    def _read_json(self, path: Path) -> Optional[Any]:
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _read_text(self, path: Path) -> Optional[str]:
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    def _write_status(self, run_id: str, status: str) -> bool:
        """原子写 status.json。"""
        p = self._bridge_dir / run_id / "status.json"
        if status not in _RUN_STATUSES:
            return False
        try:
            self._atomic_write(p, {"status": status, "updated_at": _now_iso()})
            return True
        except OSError:
            return False

    def _write_response(self, run_id: str, response: dict, status: str = "completed") -> bool:
        """原子写 response.json（tmp → rename），保证不会读到半写文件。"""
        run_dir = self._bridge_dir / run_id
        if not run_dir.exists():
            return False

        # 先写 staging
        staging = run_dir / ".response.json.tmp"
        final = run_dir / "response.json"
        try:
            with open(staging, "w", encoding="utf-8") as f:
                json.dump(response, f, ensure_ascii=False, indent=2)
            staging.rename(final)
            self._atomic_write(run_dir / "status.json", {"status": status, "updated_at": _now_iso()})
            return True
        except OSError:
            if staging.exists():
                staging.unlink()
            return False

    def _read_response(self, run_id: str) -> Optional[dict]:
        """读 response.json（跳过 staging 文件）。"""
        p = self._bridge_dir / run_id / "response.json"
        return self._read_json(p)


def _generate_run_id(action: str) -> str:
    """生成可读的 run_id。"""
    suffix = uuid.uuid4().hex[:8]
    safe = re.sub(r"[^a-zA-Z0-9-]", "-", action)[:30]
    return f"{safe}-{suffix}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


import re  # noqa: E402 — 在函数用了才 import


# ── CLI ──

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Agent Bridge 工具")
    ap.add_argument("action", choices=["create", "list", "poll", "cleanup"])
    ap.add_argument("--dir", default=".", help="项目根目录")
    ap.add_argument("--run-id", help="run ID")
    ap.add_argument("--action-name", default="cli-task", help="action 名")
    ap.add_argument("--prompt", default="", help="prompt 内容")
    args = ap.parse_args()

    bridge = AgentBridge(args.dir)

    if args.action == "create":
        run = bridge.create_run(args.action_name, prompt=args.prompt)
        print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))

    elif args.action == "list":
        runs = bridge.list_runs()
        print(f"共 {len(runs)} 个 run:")
        for r in runs:
            print(f"  {r.run_id} [{r.status}] {r.request.get('action','?')}")

    elif args.action == "poll":
        if not args.run_id:
            print("需要 --run-id")
            sys.exit(1)
        run = bridge.poll_run(args.run_id)
        if run:
            print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"run {args.run_id} 不存在")
            sys.exit(1)

    elif args.action == "cleanup":
        removed = bridge.cleanup()
        print(f"清理了 {removed} 个过期 run")
