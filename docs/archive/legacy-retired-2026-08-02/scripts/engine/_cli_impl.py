"""engine._cli_impl — main() CLI entry.

Loaded via engine.cli.attach().
"""
# flake8: noqa

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CCC Engine — multi-workspace scheduler")
    parser.add_argument(
        "--port",
        type=int,
        default=_STATS_PORT,
        help=f"Stats HTTP 端点端口（默认 {_STATS_PORT}）",
    )
    args = parser.parse_args(argv)

    program_dir = Path.home() / "program"
    workspaces = _discover_workspaces()
    if not workspaces:
        engine_log("未找到任何 workspace（需 ~/program/*/.ccc/board/）")
        sys.exit(1)

    labels = [_ws_label(w, program_dir) for w in workspaces]
    engine_log(f"发现 {len(workspaces)} 个 workspace: {labels}")

    if _check_last_exit_was_kill():
        engine_log("⚠️ 上次退出为强制杀死（无正常日志），可能是 OOM 或信号中断")

    def _handle_signal(signum, frame):
        global _engine_shutdown
        if _engine_shutdown:
            return
        _engine_shutdown = True
        signal_names = {
            signal.SIGTERM: "SIGTERM",
            signal.SIGINT: "SIGINT",
            signal.SIGHUP: "SIGHUP",
            signal.SIGQUIT: "SIGQUIT",
        }
        name = signal_names.get(signum, f"SIG{signum}")
        engine_log(f"收到 {name}, 优雅关闭中...")
        _write_engine_restart("shutdown", name)

    def _final_restart_log():
        _write_engine_restart("stopped", "normal_exit")

    atexit.register(_final_restart_log)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
        try:
            signal.signal(sig, _handle_signal)
        except (OSError, ValueError) as exc:
            _log.warning("[signal_register] %s: %s", sig, exc)

    _run_stats_server(args.port)

    try:
        try:
            engine_loop(workspaces)
        except KeyboardInterrupt:
            engine_log("Engine 关闭")
            _write_engine_restart("shutdown", "KeyboardInterrupt")
        except SystemExit as e:
            code = e.code if e.code else 0
            if code != 0:
                _write_engine_restart("stopped", f"SystemExit({code})")
            _log.debug(f"engine exiting via SystemExit({code})")
        except Exception as e:
            engine_log(f"Engine 异常退出: {e}")
            _write_engine_restart("stopped", f"exception: {type(e).__name__}: {e}")
            tb_text = _traceback.format_exc()
            engine_log(f"{tb_text[:3000]}")
    finally:
        _engine_shutdown = True
        n = _graceful_kill_active_tasks()
        if n:
            engine_log(f"[shutdown] killed {n} active task subprocess(es)")
    engine_log("Engine 终止")


