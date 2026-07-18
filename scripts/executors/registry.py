"""执行器注册表 — opencode | python | ollama | cli。

契约：docs/product/executor-plugins.md
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


EXECUTOR_IDS = frozenset({"opencode", "python", "ollama", "cli", "auto"})


@dataclass
class ExecResult:
    ok: bool
    executor: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    detail: str = ""
    duration_s: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


class ExecutorPlugin(Protocol):
    id: str

    def run(self, work_ctx: dict[str, Any]) -> ExecResult: ...


def normalize_executor(executor_id: str | None, *, pipeline: str = "") -> str:
    eid = (executor_id or "opencode").strip().lower()
    if eid == "auto":
        p = (pipeline or "").strip().lower()
        if "python" in p or p in ("py", "script"):
            return "python"
        if "ollama" in p:
            return "ollama"
        if p in ("cli", "shell", "ops"):
            return "cli"
        return "opencode"
    if eid not in EXECUTOR_IDS - {"auto"}:
        return "opencode"
    return eid


class OpenCodePlugin:
    id = "opencode"

    def run(self, work_ctx: dict[str, Any]) -> ExecResult:
        # 正式路径仍由 Engine / OpenCodeExecutor 接管；此处仅声明与冒烟
        return ExecResult(
            ok=True,
            executor=self.id,
            detail="deferred_to_engine_opencode",
            meta={"work_id": work_ctx.get("work_id")},
        )


class PythonPlugin:
    id = "python"

    def run(self, work_ctx: dict[str, Any]) -> ExecResult:
        spec = work_ctx.get("executor_spec") or {}
        cwd = Path(work_ctx.get("cwd") or spec.get("cwd") or ".")
        entry = spec.get("entrypoint") or work_ctx.get("entrypoint")
        if not entry:
            # 桩：无 entrypoint 时写一条标记，证明执行面可达
            marker = cwd / ".ccc" / "executor-python.ok"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps(
                    {
                        "work_id": work_ctx.get("work_id"),
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            return ExecResult(
                ok=True,
                executor=self.id,
                detail="python_stub_marker",
                meta={"marker": str(marker)},
            )
        entry_path = Path(entry)
        if not entry_path.is_absolute():
            entry_path = cwd / entry_path
        if not entry_path.is_file():
            return ExecResult(
                ok=False,
                executor=self.id,
                exit_code=2,
                detail=f"entrypoint missing: {entry_path}",
            )
        t0 = time.time()
        try:
            proc = subprocess.run(
                [os.environ.get("CCC_PYTHON", "python3"), str(entry_path)],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=int(spec.get("timeout") or 120),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(
                ok=False,
                executor=self.id,
                exit_code=124,
                detail="timeout",
                stderr=str(exc)[:500],
                duration_s=time.time() - t0,
            )
        return ExecResult(
            ok=proc.returncode == 0,
            executor=self.id,
            exit_code=proc.returncode,
            stdout=(proc.stdout or "")[:8000],
            stderr=(proc.stderr or "")[:4000],
            duration_s=time.time() - t0,
        )


class OllamaPlugin:
    id = "ollama"

    def run(self, work_ctx: dict[str, Any]) -> ExecResult:
        return ExecResult(
            ok=True,
            executor=self.id,
            detail="ollama_stub_defined",
            meta={"note": "HTTP generate 实现可分期"},
        )


class CliPlugin:
    id = "cli"

    def run(self, work_ctx: dict[str, Any]) -> ExecResult:
        spec = work_ctx.get("executor_spec") or {}
        argv = spec.get("args") or work_ctx.get("args") or []
        if not isinstance(argv, list) or not argv:
            return ExecResult(
                ok=True,
                executor=self.id,
                detail="cli_stub_no_args",
            )
        cwd = Path(work_ctx.get("cwd") or spec.get("cwd") or ".")
        t0 = time.time()
        try:
            proc = subprocess.run(
                [str(a) for a in argv],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=int(spec.get("timeout") or 120),
                check=False,
            )
        except Exception as exc:
            return ExecResult(
                ok=False,
                executor=self.id,
                exit_code=1,
                detail=str(exc)[:300],
                duration_s=time.time() - t0,
            )
        return ExecResult(
            ok=proc.returncode == 0,
            executor=self.id,
            exit_code=proc.returncode,
            stdout=(proc.stdout or "")[:8000],
            stderr=(proc.stderr or "")[:4000],
            duration_s=time.time() - t0,
        )


_REGISTRY: dict[str, ExecutorPlugin] = {
    "opencode": OpenCodePlugin(),
    "python": PythonPlugin(),
    "ollama": OllamaPlugin(),
    "cli": CliPlugin(),
}


def resolve_executor(executor_id: str | None, *, pipeline: str = "") -> ExecutorPlugin:
    eid = normalize_executor(executor_id, pipeline=pipeline)
    plugin = _REGISTRY.get(eid)
    if plugin is None:
        raise KeyError(f"unknown_executor:{eid}")
    return plugin


def run_executor(work_ctx: dict[str, Any]) -> ExecResult:
    eid = work_ctx.get("executor")
    pipeline = str(work_ctx.get("pipeline") or "")
    try:
        plugin = resolve_executor(eid, pipeline=pipeline)
    except KeyError:
        return ExecResult(
            ok=False,
            executor=str(eid or ""),
            exit_code=2,
            detail="unknown_executor",
        )
    return plugin.run(work_ctx)


def register_executor(plugin: ExecutorPlugin) -> None:
    """测试 / 扩展用。"""
    _REGISTRY[plugin.id] = plugin
