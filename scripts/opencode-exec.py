#!/usr/bin/env python3
"""opencode-exec.py — OpenCode CLI 执行器（单 phase）

职责：接收一个 phase prompt 文件，调用 `opencode exec` 子进程执行，
      捕获 stdout/stderr/exit_code/duration，输出结构化 JSON。

CLI 模式（v0.8 定案）：只用 `opencode exec` 子进程调用，不走 HTTP/serve。

红线（v0.8 配套）：
  - X1: 不允许全局 opencode 进程 > 3 并发（由 opencode-pool 控制）
  - X2: 每 phase 必杀（finally 兜底 + opencode-watchdog.sh 二重兜底）
  - X3: 启动前必须先跑 opencode-watchdog.sh（残留扫描）

用法：
  python3 opencode-exec.py --phase <id> --prompt <file> [--timeout 1800] [--cwd <dir>]

退出码：
  0  = phase 执行成功（exit 0）
  10 = opencode 二进制不存在
  11 = prompt 文件不存在
  12 = watchdog 检查失败
  20 = opencode exec 超时（已被 kill）
  30 = opencode exec 异常崩溃
  非 0 = opencode 本身非零退出（stderr 透传）
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# 进程池目录（pid 文件落点 + 残留检测标记）
PID_DIR = Path.home() / ".ccc" / "opencode-pids"
PID_DIR.mkdir(parents=True, exist_ok=True)


import sys as _sys
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)
from _executor import resolve_opencode


def check_residual_watchdog(script_dir: Path) -> bool:
    """跑 watchdog 验残留"""
    wd = script_dir / "opencode-watchdog.sh"
    if not wd.exists():
        print(f"[opencode-exec] 缺 watchdog: {wd}", file=sys.stderr)
        return False
    rc = subprocess.run(["bash", str(wd)], capture_output=True, text=True).returncode
    # watchdog 退出码：0=干净 / 3=已自清 / 其它=失败
    return rc in (0, 3)


async def run_opencode(
    phase_id: str,
    prompt_text: str,
    timeout: int,
    cwd: None = None,
    cmd: None = None,
    opencode_bin: str = "opencode",
) -> dict:
    """起 opencode run 子进程，prompt 走 positionals（opencode 1.17 协议）

    cmd 参数：可注入自定义命令（测试用）。默认调 opencode run --model code。
    """
    tmp_path = None
    if cmd is None:
        # opencode 1.17 run 协议：message 走 positionals（不是 stdin）
        # 截断 prompt 到 200 字符（防命令行超长）；长 prompt 走 prompt_file
        # 自动任务走 code 通道（oppencode 原生默认），不走 flash
        # 如需切换可设 OPENCODE_MODEL 环境变量
        model = os.environ.get("OPENCODE_MODEL", "code")
        prompt_text = prompt_text.strip()
        if len(prompt_text) > 200:
            # 长 prompt：写临时文件，用 --file 附件 + 短指令
            # Lesson 33 实证：positionals 截断会让模型只看到半句 prompt
            # Bug 1+3 修：临时文件必须在 run 完 unlink（finally 兜底）
            import tempfile
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, encoding="utf-8"
            )
            tmp.write(prompt_text)
            tmp.close()
            tmp_path = tmp.name
            # 短 message 必须在 --file 前（opencode 1.17 参数顺序约束）
            cmd = [
                opencode_bin, "run",
                "--model", model,
                "Read attached file and execute the instructions inside.",
                "--file", tmp_path,
            ]
        else:
            short_prompt = prompt_text if prompt_text else "execute"
            cmd = [opencode_bin, "run", "--model", model, short_prompt]
    # 红线 X2 修（v0.11b-fix）：用 process group 启动
    # 这样 kill pgid 会级联到 opencode 起的 node 孙子进程
    import os as _os
    import signal as _sig
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,  # 显式不吃 stdin
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        start_new_session=True,  # 新 session, pgid = pid
    )

    pid_file = PID_DIR / f"{phase_id}.pid"
    pid_file.write_text(str(proc.pid))
    # 注：先启动进程再写 pid，窗口极小。若在此间隙 pool 或 watchdog 扫描，
    # 可能误判为无人认领的残留。接受此竞态，换一种顺序（先写 pid 再创建
    # 进程）则需预知 pid，不可行。

    started = time.time()
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        duration = time.time() - started
        return {
            "phase_id": phase_id,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "duration_s": round(duration, 2),
            "pid": proc.pid,
            "killed": False,
        }
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        # 红线 X2: 超时/取消必杀（用 killpg 级联到整个 process group）
        try:
            _os.killpg(proc.pid, _sig.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            try:
                _os.killpg(proc.pid, _sig.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass  # best-effort, 不阻塞
        killed_reason = "cancelled" if isinstance(exc, asyncio.CancelledError) else f"timeout after {timeout}s"
        return {
            "phase_id": phase_id,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"{killed_reason} — killed",
            "duration_s": round(time.time() - started, 2),
            "pid": proc.pid,
            "killed": True,
        }
    finally:
        # 红线 X2: 不管成功失败都清 pid
        if pid_file.exists():
            pid_file.unlink()
        # Bug 1+3 修：长 prompt 临时文件必须 unlink
        # 否则磁盘泄漏 + 隐私（prompt 可能含密钥）
        if tmp_path is not None and Path(tmp_path).exists():
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass  # best-effort, 不阻断


async def main() -> int:
    ap = argparse.ArgumentParser(description="OpenCode CLI 执行器（单 phase）")
    ap.add_argument("--phase", required=True, help="phase ID（用于 pid 文件）")
    ap.add_argument("--prompt", required=True, help="prompt 文件路径（文件读取）")
    ap.add_argument("--timeout", type=int, default=1800, help="超时秒数，默认 1800")
    ap.add_argument("--cwd", default=None, help="工作目录")
    ap.add_argument("--skip-watchdog", action="store_true", help="跳过残留扫描（仅调试）")
    args = ap.parse_args()

    # 二进制检查
    opencode_bin = resolve_opencode()
    if not opencode_bin:
        print(json.dumps({"error": "opencode not found (try: set OPENCODE_BIN env)"}), file=sys.stderr)
        return 10

    # prompt 文件检查
    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        print(json.dumps({"error": f"prompt not found: {args.prompt}"}), file=sys.stderr)
        return 11

    # watchdog 残留扫描
    if not args.skip_watchdog:
        script_dir = Path(__file__).parent.resolve()
        if not check_residual_watchdog(script_dir):
            print(json.dumps({"error": "watchdog FAIL — 残留进程未清理"}), file=sys.stderr)
            return 12

    prompt_text = prompt_path.read_text(encoding="utf-8")
    result = await run_opencode(args.phase, prompt_text, args.timeout, args.cwd, opencode_bin=opencode_bin)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
