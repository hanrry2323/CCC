"""_executor.py — CCC 执行器抽象 (v0.19)

提供 Executor 协议和 OpenCodeExecutor 实现。
执行器负责运行指定 phase，返回执行结果。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TypedDict

from _config import Config, get_logger

_log = get_logger("executor")


def resolve_opencode() -> Optional[str]:
    """解析 opencode 可执行文件路径

    优先级: OPENCODE_BIN env > shutil.which > ~/.npm-global/bin/opencode
    launchd 的 PATH 不含 ~/.npm-global/bin，所以必须显式回退。
    """
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


# 中转站 / Claude CLI / OpenCode 必需的鉴权变量（剥光会导致假 "Not logged in"）
_LLM_ENV_ALLOWLIST = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_API_BASE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENCODE_MODEL",
        "OPENCODE_API_KEY",
    }
)


def _sanitized_env() -> dict:
    """Strip credential env vars to prevent subprocess leakage (CWE-522).

    Subprocess.Popen inherits the full environment by default, which exposes
    API keys/tokens/secrets to child processes. Filter out known patterns.

    v0.40.1: 确保 PATH 含 ~/.local/bin 等，避免 launchd 下找不到 claude/opencode。
    v0.42+: 保留 LLM 中转站 allowlist（ANTHROPIC_AUTH_TOKEN 等）。
      旧逻辑按 TOKEN/API_KEY 一刀切，launchd 继承的鉴权被剥掉 → claude -p
      输出 ``Not logged in · Please run /login``（与是否真的要 /login 无关）。
    """
    import os as _os

    original = _os.environ.copy()
    env = original.copy()
    _CREDENTIAL_PATTERNS = ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")
    keys_to_remove = [
        key
        for key in env
        if key not in _LLM_ENV_ALLOWLIST
        and any(pat in key.upper() for pat in _CREDENTIAL_PATTERNS)
    ]
    for key in keys_to_remove:
        env.pop(key, None)

    # 安全：子进程不得继承角色锁 bypass（生产不可旁路）
    env.pop("CCC_ROLE_LOCK_BYPASS", None)

    # 显式从原环境恢复 allowlist（防止模式误伤）
    for key in _LLM_ENV_ALLOWLIST:
        if key in original and original[key]:
            env[key] = original[key]

    # v0.40.1: PATH 前缀（claude / opencode / homebrew）
    try:
        from _claude_cli import claude_path_prefixes

        prefixes = claude_path_prefixes()
    except Exception:
        prefixes = []
    npm = str(Path.home() / ".npm-global" / "bin")
    if Path(npm).is_dir() and npm not in prefixes:
        prefixes.append(npm)
    old = env.get("PATH", "")
    parts = [p for p in prefixes if p]
    for p in old.split(":"):
        if p and p not in parts:
            parts.append(p)
    if parts:
        env["PATH"] = ":".join(parts)
    return env


def _claude_env(*, relay_url: str | None = None) -> dict:
    """product/reviewer 调 claude CLI 用的环境：sanitized + Anthropic 兼容出口。"""
    env = _sanitized_env()
    if relay_url:
        env["ANTHROPIC_BASE_URL"] = relay_url
    elif not env.get("ANTHROPIC_BASE_URL"):
        # 默认 MiniMax 直连（ai-loop-router :4000 已退役）
        env["ANTHROPIC_BASE_URL"] = "https://api.minimaxi.com/anthropic"
    # Phase3：Engine 私有配置家（禁止落到个人 ~/.claude）
    try:
        from _claude_cli import (
            default_engine_claude_config_dir,
            ensure_engine_claude_config_dir,
        )

        cfg = (env.get("CLAUDE_CONFIG_DIR") or "").strip()
        if not cfg or cfg.rstrip("/").endswith(".claude"):
            cfg = str(default_engine_claude_config_dir())
        ensure_engine_claude_config_dir(Path(cfg).expanduser())
        env["CLAUDE_CONFIG_DIR"] = str(Path(cfg).expanduser())
    except Exception:
        fallback = str(Path.home() / ".ccc" / "engine-claude")
        Path(fallback).mkdir(parents=True, exist_ok=True)
        env["CLAUDE_CONFIG_DIR"] = fallback
    return env


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
        import os as _os
        import signal as _sig
        import subprocess
        import time

        opencode_bin = self._resolve_opencode()
        if not opencode_bin:
            return ExecResult(
                phase_id=phase_id,
                exit_code=10,
                stdout="",
                stderr="opencode not found",
                duration_s=0,
                pid=0,
                killed=False,
            )

        model = model or self.config.model
        prompt_text = prompt.strip()
        tmp_path = None

        if not cwd:
            return ExecResult(
                phase_id=phase_id,
                exit_code=11,
                stdout="",
                stderr="cwd required for workspace isolation",
                duration_s=0,
                pid=0,
                killed=False,
            )

        # opencode-exec.py 文件名含连字符，用 importlib 加载 build_opencode_run_cmd
        import importlib.util

        _exec_py = Path(__file__).resolve().parent / "opencode-exec.py"
        _spec = importlib.util.spec_from_file_location("_ccc_opencode_exec", _exec_py)
        if _spec is None or _spec.loader is None:
            raise RuntimeError(f"cannot load opencode-exec from {_exec_py}")
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _build_cmd = _mod.build_opencode_run_cmd

        if len(prompt_text) > 200:
            pids_dir = Path.home() / ".ccc" / "pids"
            pids_dir.mkdir(parents=True, exist_ok=True)
            import uuid as _uuid

            tmp_path = str(pids_dir / f"prompt-{_uuid.uuid4().hex}.md")
            Path(tmp_path).write_text(prompt_text, encoding="utf-8")
            try:
                _os.chmod(tmp_path, 0o600)
            except OSError:
                pass
            cmd = _build_cmd(
                opencode_bin,
                model,
                message="Read attached file and execute the instructions inside.",
                prompt_file=tmp_path,
                cwd=cwd,
            )
        else:
            cmd = _build_cmd(
                opencode_bin,
                model,
                message=prompt_text or "execute",
                cwd=cwd,
            )

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
                env=_sanitized_env(),
                start_new_session=True,
            )
            pid_file.write_text(str(proc.pid))

            started = time.time()
            # task_id 从 phase_id 推断：tid 或 tid__pN
            _tid = phase_id.split("__")[0] if phase_id else ""
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                duration = time.time() - started
                out_s = stdout.decode("utf-8", errors="replace")
                err_s = stderr.decode("utf-8", errors="replace")
                try:
                    from _cost_telemetry import estimate_tokens, record_call

                    record_call(
                        role="executor",
                        provider_or_model=model or "opencode",
                        prompt_tokens=estimate_tokens(prompt_text),
                        completion_tokens=estimate_tokens(out_s + err_s),
                        latency_ms=int(duration * 1000),
                        ok=(proc.returncode == 0),
                        task_id=_tid,
                        phase_id=phase_id,
                    )
                except Exception:
                    pass
                return ExecResult(
                    phase_id=phase_id,
                    exit_code=proc.returncode,
                    stdout=out_s,
                    stderr=err_s,
                    duration_s=round(duration, 2),
                    pid=proc.pid,
                    killed=False,
                )
            except subprocess.TimeoutExpired:
                # 红线 X2: 超时必杀（killpg 级联到 process group）
                try:
                    _os.killpg(proc.pid, _sig.SIGTERM)
                except (ProcessLookupError, PermissionError) as e:
                    _log.warning("SIGTERM killpg failed pid=%s: %s", proc.pid, e)
                hard_deadline = started + timeout * 1.5
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        _os.killpg(proc.pid, _sig.SIGKILL)
                    except (ProcessLookupError, PermissionError) as e:
                        _log.warning("SIGKILL killpg failed pid=%s: %s", proc.pid, e)
                remaining = hard_deadline - time.time()
                if remaining > 0 and proc.poll() is None:
                    try:
                        proc.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        try:
                            _os.killpg(proc.pid, _sig.SIGKILL)
                        except (ProcessLookupError, PermissionError) as e:
                            _log.warning("hard SIGKILL failed pid=%s: %s", proc.pid, e)
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            _log.warning(
                                "proc.wait timeout after hard deadline pid=%s", proc.pid
                            )
                duration = time.time() - started
                try:
                    from _cost_telemetry import estimate_tokens, record_call

                    record_call(
                        role="executor",
                        provider_or_model=model or "opencode",
                        prompt_tokens=estimate_tokens(prompt_text),
                        completion_tokens=0,
                        latency_ms=int(duration * 1000),
                        ok=False,
                        task_id=_tid,
                        phase_id=phase_id,
                    )
                except Exception:
                    pass
                return ExecResult(
                    phase_id=phase_id,
                    exit_code=-1,
                    stdout="",
                    stderr=f"timeout after {timeout}s — killed",
                    duration_s=round(duration, 2),
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
                except OSError as e:
                    _log.warning("failed to unlink temp prompt %s: %s", tmp_path, e)

    def _resolve_opencode(self) -> Optional[str]:
        return resolve_opencode()
