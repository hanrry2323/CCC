"""_executor.py — CCC 执行器抽象 (v0.19)

提供 Executor 协议和 OpenCodeExecutor 实现。
执行器负责运行指定 phase，返回执行结果。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, TypedDict

from _board_store import FileBoardStore
from _config import Config


class ExecResult(TypedDict):
    """执行结果结构"""
    phase_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    pid: int
    killed: bool


class Executor:
    """执行器协议

    所有执行器必须实现 execute 方法。
    当前：OpenCodeExecutor（CLI 进程）
    未来：ContainerExecutor（Docker）/ SSHExecutor（远程）
    """

    def execute(
        self,
        phase_id: str,
        prompt: str,
        timeout: int,
        cwd: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ExecResult:
        """执行一个 phase

        Args:
            phase_id: phase 标识
            prompt: 执行 prompt
            timeout: 超时秒数
            cwd: 工作目录
            model: 模型名，默认使用 Config().model
        """
        raise NotImplementedError


class OpenCodeExecutor(Executor):
    """当前执行器：opencode CLI 子进程调用

    包装 opencode-exec.py 的 run_opencode 协程，提供同步接口。
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def execute(
        self,
        phase_id: str,
        prompt: str,
        timeout: int,
        cwd: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ExecResult:
        """调 opencode-exec.py 的 run_opencode 执行"""
        import asyncio
        import os as _os
        import signal as _sig
        import subprocess
        import time

        opencode_bin = self._resolve_opencode()
        if not opencode_bin:
            return ExecResult(
                phase_id=phase_id, exit_code=10,
                stdout="", stderr="opencode not found",
                duration_s=0, pid=0, killed=False,
            )

        model = model or self.config.model
        prompt_text = prompt.strip()
        tmp_path = None

        if len(prompt_text) > 200:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, encoding="utf-8"
            )
            tmp.write(prompt_text)
            tmp.close()
            tmp_path = tmp.name
            cmd = [
                opencode_bin, "run",
                "--model", model,
                "Read attached file and execute the instructions inside.",
                "--file", tmp_path,
            ]
        else:
            cmd = [opencode_bin, "run", "--model", model, prompt_text or "execute"]

        proc = None
        pid_file = Path.home() / ".ccc" / "opencode-pids" / f"{phase_id}.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                start_new_session=True,
            )
            pid_file.write_text(str(proc.pid))

            started = time.time()
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                duration = time.time() - started
                return ExecResult(
                    phase_id=phase_id,
                    exit_code=proc.returncode,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    duration_s=round(duration, 2),
                    pid=proc.pid,
                    killed=False,
                )
            except subprocess.TimeoutExpired:
                # 红线 X2: 超时必杀（killpg 级联到 process group）
                try:
                    _os.killpg(proc.pid, _sig.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        _os.killpg(proc.pid, _sig.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
                return ExecResult(
                    phase_id=phase_id,
                    exit_code=-1,
                    stdout="",
                    stderr=f"timeout after {timeout}s — killed",
                    duration_s=round(time.time() - started, 2),
                    pid=proc.pid,
                    killed=True,
                )
        finally:
            # 清 pid 文件 + 临时文件
            if pid_file.exists():
                pid_file.unlink()
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink()
                except OSError:
                    pass

    @staticmethod
    def _resolve_opencode() -> Optional[str]:
        """解析 opencode 可执行文件路径"""
        import os as _os
        from shutil import which
        from os.path import expanduser

        env_bin = _os.environ.get("OPENCODE_BIN")
        if env_bin:
            resolved = which(env_bin) or (
                env_bin if "/" in env_bin and Path(env_bin).exists() else None
            )
            if resolved:
                return resolved

        path = which("opencode")
        if path:
            return path

        npm_path = expanduser("~/.npm-global/bin/opencode")
        if Path(npm_path).exists():
            return npm_path

        return None
