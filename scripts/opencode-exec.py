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
import socket
import subprocess
import sys
import time
from pathlib import Path

# 进程池目录（pid 文件落点 + 残留检测标记）
PID_DIR = Path.home() / ".ccc" / "opencode-pids"
PID_DIR.mkdir(parents=True, exist_ok=True)

# v0.24.7 (A24-12): 长 prompt 临时文件落点（私有目录 + mode 0o600），防止 /tmp 下的非安全读取。
PROMPT_DIR = Path.home() / ".ccc" / "prompts"
PROMPT_DIR.mkdir(parents=True, exist_ok=True)

import sys as _sys

_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)
from _config import Config, get_logger
from _executor import resolve_opencode

_log = get_logger("opencode-exec")
_log.info("opencode-exec config: exec_timeout_default=%ds", Config().exec_timeout)


def build_opencode_run_cmd(
    opencode_bin: str,
    model: str,
    *,
    message: str | None = None,
    prompt_file: str | None = None,
    cwd: str | Path | None = None,
    pure: bool | None = None,
) -> list[str]:
    """构造 `opencode run` 命令；强制 ``--dir`` 绑定看板 workspace。

    漏洞根因（2026-07-17）：仅设进程 cwd 不够——OpenCode 1.18 用自有
    session.directory；Engine launchd WorkingDirectory=CCC 时，xy/qb 任务的
    session 会落到 CCC，把 smoke.sh 等写进 CCC 仓并 commit（实锤
    opencode.db session.directory=/Users/apple/program/CCC）。

    - ``cwd`` **必填**（缺则 raise）
    - ``--dir``：会话/工树绑定到目标仓
    - ``--auto``：R-13 默认开，自动批准写文件操作（否则非交互模式无法创建产物）
    - ``--pure``：R-13 默认关（opencode 1.17.13 --pure 导致 exit 255 无输出）
      如需启用设 CCC_OPENCODE_PURE=1
    - R-14: ``message=None`` 时不 append positional，prompt 走 stdin
      （opencode 1.17 长 prompt >2KB 作 positional 会被 SIGTERM，stdin 方式稳定）
    """
    from _workspace_isolation import require_cwd

    ws = require_cwd(cwd)
    if pure is None:
        pure = os.environ.get("CCC_OPENCODE_PURE", "0") in (
            "1",
            "true",
            "True",
            "yes",
        )
    cmd: list[str] = [opencode_bin, "run", "--model", model]
    if pure:
        cmd.append("--pure")
    # R-13: --auto 必须开启，否则非交互模式下 opencode 无法批准写文件操作
    auto = os.environ.get("CCC_OPENCODE_AUTO", "1") not in (
        "0",
        "false",
        "False",
        "no",
    )
    if auto:
        cmd.append("--auto")
    cmd.extend(["--dir", str(ws)])
    # R-14: message 为 None 时不 append positional，prompt 走 stdin
    if message is not None:
        cmd.append(message)
    return cmd


def _extract_core_action(prompt_text: str) -> str:
    """R-3: 从长 prompt 提取核心可执行动作作为短 message。

    避免 "Read attached file and execute the instructions inside." 在非交互
    一次性模式下卡死。提取策略：
    1. 优先找 "## 目标" / "## 目的" 节的第一行
    2. 其次找 "创建" / "实现" / "修复" / "审查" 等动词开头的第一行
    3. 兜底：取前 150 字符（去换行）

    返回 ≤200 字符的短可执行指令。
    """
    if not prompt_text:
        return "execute"
    lines = [l.strip() for l in prompt_text.splitlines() if l.strip()]
    # 策略 1：找 "## 目标" / "## 目的" 节
    in_target = False
    for line in lines:
        low = line.lstrip("#").strip().lower()
        if line.startswith("#"):
            in_target = low in ("目标", "目的", "goal", "objective", "任务")
            continue
        if in_target and not line.startswith("#"):
            candidate = line.lstrip("-*").strip()
            if candidate and len(candidate) >= 4:
                return candidate[:200]
    # 策略 2：找动词开头的第一行
    action_verbs = ("创建", "实现", "修复", "审查", "编写", "修改", "删除", "重构", "添加", "生成", "执行")
    for line in lines:
        if any(line.startswith(v) or line.lstrip("-*").startswith(v) for v in action_verbs):
            candidate = line.lstrip("-*").strip()
            if candidate:
                return candidate[:200]
    # 策略 3：兜底取前 150 字符（去换行）
    flat = " ".join(prompt_text.split())
    return (flat[:150] + "...") if len(flat) > 150 else flat


async def _kill_process_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError) as e:
        _log.warning("killpg sig=%s pid=%s failed: %s", sig, pgid, e)


async def _terminate_zombie(proc, pgid: int, timeout: int, started: float) -> None:
    """SIGTERM 后等待至 hard_deadline（timeout*1.5）再 SIGKILL 兜底僵死进程。"""
    import signal as _sig

    hard_deadline = started + timeout * 1.5
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
        return
    except TimeoutError:
        await _kill_process_group(pgid, _sig.SIGKILL)
    remaining = hard_deadline - time.time()
    if remaining > 0 and proc.returncode is None:
        try:
            await asyncio.wait_for(proc.wait(), timeout=remaining)
        except TimeoutError:
            await _kill_process_group(pgid, _sig.SIGKILL)
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except TimeoutError:
                _log.warning("proc.wait timeout after hard SIGKILL pgid=%s", pgid)


def _relay_4002_up(host: str = "127.0.0.1", port: int = 4002, timeout: float = 1.0) -> bool:
    """CCC Relay 2026-07-25:opencode-exec 探活 :4002,失败时切直连。

    短超时(1s)+ 静默失败;只在 spawn 前调一次,绝不阻塞任务。
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_residual_watchdog(script_dir: Path) -> bool:
    """跑 watchdog 验残留"""
    wd = script_dir / "opencode-watchdog.sh"
    if not wd.exists():
        _log.warning("缺 watchdog: %s", wd)
        return False
    rc = subprocess.run(["bash", str(wd)], capture_output=True, text=True).returncode
    # watchdog 退出码：0=干净 / 3=已自清 / 其它=失败
    return rc in (0, 3)


async def _warmup_opencode(opencode_bin: str, model: str, cwd: Path | None) -> bool:
    """R-WARMUP: opencode 冷启动预热 — 跑极短 prompt 让模型加载/session 初始化。

    带 30s 短超时，失败静默（不阻塞主流程）。
    成功后 opencode 后续启动走热路径，避免 rc=247。
    """
    proc = None
    try:
        warmup_cmd = build_opencode_run_cmd(
            opencode_bin, model, message="ok", cwd=cwd
        )
        proc = await asyncio.create_subprocess_exec(
            *warmup_cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            start_new_session=True,
        )
        await asyncio.wait_for(proc.wait(), timeout=30)
        _log.info("[warmup] ok (rc=%s)", proc.returncode)
        return True
    except (TimeoutError, asyncio.CancelledError):
        _log.warning("[warmup] timeout (30s)，继续主流程")
        if proc is not None:
            try:
                import signal as _sig
                await _kill_process_group(proc.pid, _sig.SIGKILL)
            except Exception:
                pass
        return False
    except Exception as exc:
        _log.warning("[warmup] 失败: %s，继续主流程", exc)
        return False


async def run_opencode(
    phase_id: str,
    prompt_text: str,
    timeout: int,
    cwd: Path | None = None,
    cmd: list[str] | None = None,
    opencode_bin: str = "opencode",
    cfg: Config | None = None,
) -> dict:
    """起 opencode run 子进程，prompt 走 stdin（R-14）

    cmd 参数：可注入自定义命令（测试用）。默认调 opencode run --model code。
    R-14: 默认走 stdin 传 prompt（长 positional 会导致 opencode 1.17 SIGTERM）
    """
    tmp_path = None
    # R-14: full_prompt 用于 stdin 传入；cmd 注入模式下不走 stdin
    full_prompt = prompt_text.strip() if prompt_text else "execute"
    _use_stdin = cmd is None  # 仅默认（非注入）路径走 stdin
    if cmd is None:
        # opencode 1.17 run 协议：message 走 positionals（不是 stdin）
        # 截断 prompt 到 200 字符（防命令行超长）；长 prompt 走 prompt_file
        # CCC Relay 2026-07-28:默认 loop/flash（:4002 → flash 同池）
        # fail-open 时(OPENCODE_FAIL_OPEN=1 或 relay down)切直连配置里的模型
        # 直连降级用 OPENCODE_CONFIG 指 ~/.config/opencode/opencode.direct.json
        model = os.environ.get("OPENCODE_MODEL", Config().model)
        if model.startswith("loop/") and os.environ.get("OPENCODE_FAIL_OPEN") != "1":
            # 探活 relay :4002 失败 → 切直连(opencode.direct.json)
            direct_cfg = Path.home() / ".config" / "opencode" / "opencode.direct.json"
            if not _relay_4002_up():
                if direct_cfg.exists():
                    # 直连配置可能仍写 xfyun/zhipu；尊重该文件 model，否则退回 zhipu/flash
                    try:
                        import json as _json
                        _d = _json.loads(direct_cfg.read_text(encoding="utf-8"))
                        model = str(_d.get("model") or "zhipu/flash")
                    except Exception:
                        model = "zhipu/flash"
                    os.environ["OPENCODE_CONFIG"] = str(direct_cfg)
                    _log.warning(
                        "[fail-open] relay :4002 不可达, 切直连 model=%s config=%s",
                        model, direct_cfg,
                    )
                else:
                    _log.warning(
                        "[fail-open] relay :4002 不可达且 %s 不存在, 仍尝试 %s",
                        direct_cfg, model,
                    )
        prompt_text = prompt_text.strip()
        if cfg is None:
            cfg = Config()
        # R-14: prompt 走 stdin（不传 message positional）
        # R-13 的 positional message 策略在长 prompt（>2KB）下导致 opencode SIGTERM
        # 实测 2026-08-01：cat prompt.md | opencode run --auto --dir <ws> 正常工作
        # 而 opencode run --auto --dir <ws> "$LONG_PROMPT" 会在 ~10s 后 exit -15
        # 根因：opencode 1.17.13 CLI 在长 positional 参数下有未知的 SIGTERM bug
        # stdin 方式：opencode 无 message positional 时自动从 stdin 读 prompt
        cmd = build_opencode_run_cmd(
            opencode_bin,
            model,
            message=None,  # R-14: 不传 positional，走 stdin
            cwd=cwd,
        )
    # R-WARMUP: 冷启动预热 — stdin 模式下先跑短 prompt 让 opencode session 初始化
    if _use_stdin and full_prompt:
        await _warmup_opencode(opencode_bin, model, cwd)

    # 红线 X2 修（v0.11b-fix）：用 process group 启动
    # 这样 kill pgid 会级联到 opencode 起的 node 孙子进程
    import signal as _sig

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE if _use_stdin else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        start_new_session=True,  # 新 session, pgid = pid
    )

    pid_file = PID_DIR / f"{phase_id}.pid"
    # 修复 stability-audit-2026-07-24 类别①（H3）：先 O_CREAT|O_EXCL 占位
    # 让 watchdog 在 Popen→write_text 间隙也能识别 "有进程在启动中"
    # 避免误判为无人认领的残留而 SIGTERM 新进程（Lesson 44 实锤）
    # 修复 diff-review-2026-07-24 中风险 #4：FileExistsError 占位残留 retry-once
    # （之前残留的占位文件会让后续同 phase_id 启动永久 FileExistsError）
    _placeholder_ok = False
    for _attempt in (1, 2):
        try:
            placeholder_fd = os.open(
                str(pid_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
            )
            os.close(placeholder_fd)
            _placeholder_ok = True
            break
        except FileExistsError:
            if _attempt == 1:
                # 第一次失败：可能是上次残留（finally 未跑的崩溃），
                # 清理一次后再试
                try:
                    pid_file.unlink()
                    continue
                except OSError as e:
                    _log.debug("opencode-exec pid_file unlink retry %s: %s", pid_file, e)
            # 第二次仍失败：真有并发跑，abort
            # 修复 diff-review-2026-07-24 #2：先 SIGTERM 等 3s 让 proc
            # 做 cleanup，再 SIGKILL 兜底（旧版直接 SIGKILL 不给机会）
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3)
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
            except (ProcessLookupError, OSError) as e:
                _log.debug("opencode-exec kill on pid_file race %s: %s", pid_file, e)
            return {
                "phase_id": phase_id,
                "error": f"pid_file exists: {pid_file.name}",
                "exit_code": -1,
                "stdout": "",
                "stderr": "concurrent launch aborted",
                "duration_sec": 0.0,
            }
    if not _placeholder_ok:  # 防御性 — 实际 unreachable
        proc.kill()
        await proc.wait()
        return {
            "phase_id": phase_id,
            "error": "pid_file placeholder failed",
            "exit_code": -1,
            "stdout": "",
            "stderr": "placeholder retry exhausted",
            "duration_sec": 0.0,
        }
    pid_file.write_text(str(proc.pid))

    started = time.time()
    result: dict | None = None
    try:
        # R-14: prompt 通过 stdin 传给 opencode（避免长 positional SIGTERM bug）
        stdin_input = full_prompt.encode("utf-8") if _use_stdin and full_prompt else None
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin_input),
            timeout=timeout,
        )
        duration = time.time() - started
        result = {
            "phase_id": phase_id,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "duration_s": round(duration, 2),
            "pid": proc.pid,
            "killed": False,
        }
        # R-COLD: opencode 冷启动 rc=247 显式标记，供 bucket 分类使用
        if proc.returncode == 247:
            result["cold_start"] = True
            _log.warning("[opencode] rc=247 cold-start timeout detected")
        return result
    except (TimeoutError, asyncio.CancelledError) as exc:
        # 红线 X2: 超时/取消必杀（用 killpg 级联到整个 process group）
        await _kill_process_group(proc.pid, _sig.SIGTERM)
        await _terminate_zombie(proc, proc.pid, timeout, started)
        # v0.29: 防御性 cfg 初始化（C3），确保 except 路径也有 cfg
        if cfg is None:
            cfg = Config()
        killed_reason = (
            "cancelled"
            if isinstance(exc, asyncio.CancelledError)
            else f"timeout after {cfg.exec_timeout}s"
        )
        result = {
            "phase_id": phase_id,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"{killed_reason} — killed",
            "duration_s": round(time.time() - started, 2),
            "pid": proc.pid,
            "killed": True,
        }
        return result
    finally:
        # 成功路径也收尸：opencode CLI 退出后 node 孙子常残留，占同仓槽
        try:
            await _kill_process_group(proc.pid, _sig.SIGTERM)
            await asyncio.sleep(0.4)
            await _kill_process_group(proc.pid, _sig.SIGKILL)
        except Exception as e:
            _log.warning("post-run killpg failed pid=%s: %s", proc.pid, e)
        if cwd is not None:
            try:
                from _opencode_reap import reap_opencode_workspace

                left = reap_opencode_workspace(
                    Path(cwd),
                    max_age_sec=0,
                    exclude_pids=set(),
                    grace_sec=0.3,
                )
                if left:
                    _log.warning(
                        "post-run reap leftover opencode pids=%s cwd=%s",
                        left,
                        cwd,
                    )
            except Exception as e:
                _log.warning("post-run workspace reap failed: %s", e)
        # 红线 X2: 不管成功失败都清 pid
        if pid_file.exists():
            pid_file.unlink()
        # Bug 1+3 修：长 prompt 临时文件必须 unlink
        # 否则磁盘泄漏 + 隐私（prompt 可能含密钥）
        if tmp_path is not None and Path(tmp_path).exists():
            try:
                Path(tmp_path).unlink()
            except OSError as e:
                _log.warning("temp prompt unlink failed %s: %s", tmp_path, e)


async def main() -> int:
    """CLI 入口：解析参数、做前置检查、调用 run_opencode 并打印结构化结果。

    Returns:
        进程退出码：0 成功；10 缺 opencode；11 缺 prompt；12 watchdog 失败；其他为 opencode 自身退出码。
    """
    ap = argparse.ArgumentParser(description="OpenCode CLI 执行器（单 phase）")
    ap.add_argument("--phase", required=True, help="phase ID（用于 pid 文件）")
    ap.add_argument("--prompt", required=True, help="prompt 文件路径（文件读取）")
    ap.add_argument(
        "--timeout",
        type=int,
        default=Config().exec_timeout,
        help="超时秒数，默认 Config.exec_timeout",
    )
    ap.add_argument("--cwd", required=True, help="工作目录（必填，workspace 隔离）")
    ap.add_argument(
        "--skip-watchdog", action="store_true", help="跳过残留扫描（仅调试）"
    )
    ap.add_argument(
        "--result-file",
        default="",
        help="写纯 JSON 结果到此路径（日志仍走 stderr；避免污染 result.json）",
    )
    args = ap.parse_args()

    # 二进制检查
    opencode_bin = resolve_opencode()
    if not opencode_bin:
        print(
            json.dumps({"error": "opencode not found (try: set OPENCODE_BIN env)"}),
            file=sys.stderr,
        )
        return 10

    # prompt 文件检查
    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        print(
            json.dumps({"error": f"prompt not found: {args.prompt}"}), file=sys.stderr
        )
        return 11

    # watchdog 残留扫描
    if not args.skip_watchdog:
        script_dir = Path(__file__).parent.resolve()
        if not check_residual_watchdog(script_dir):
            print(
                json.dumps({"error": "watchdog FAIL — 残留进程未清理"}), file=sys.stderr
            )
            return 12

    prompt_text = prompt_path.read_text(encoding="utf-8")

    _log.info(
        "opencode-exec run phase=%s timeout=%ds cwd=%s skip_watchdog=%s",
        args.phase,
        args.timeout,
        args.cwd,
        bool(args.skip_watchdog),
    )

    result = await run_opencode(
        args.phase,
        prompt_text,
        args.timeout,
        args.cwd,
        opencode_bin=opencode_bin,
        cfg=Config(),
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.result_file:
        try:
            rf = Path(args.result_file)
            rf.parent.mkdir(parents=True, exist_ok=True)
            rf.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            print(
                json.dumps({"error": f"result-file write failed: {exc}"}),
                file=sys.stderr,
            )
            return 13
        # 不把 JSON 打到 stdout（runner 会把 stdout 接到 exec.log）
        print(f"[opencode-exec] wrote result → {args.result_file}", file=sys.stderr)
    else:
        print(payload)
    return result["exit_code"]


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
