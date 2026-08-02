"""engine._stats_server_impl — stats HTTP

Extracted from ccc-engine.py (min-pipeline refactor 2026-07-31).
Loaded into ccc_engine host namespace via engine.stats_server.attach().
"""
# flake8: noqa
# This file is exec'd into ccc_engine.__dict__; do not import symbols directly.

def _update_stats(
    active_count: int,
    current_task: str | None = None,
    current_phase: int | None = None,
    phase_status: str | None = None,
    workspace_name: str | None = None,
) -> None:
    global _stats_started_at
    now = now_iso()
    now_ts = time.time()
    with _stats_lock:
        if _stats_started_at is None:
            _stats_started_at = now_ts
            _stats_data["uptime_sec"] = 0
        else:
            _stats_data["uptime_sec"] = max(0.001, now_ts - _stats_started_at)
        _stats_data["current_task"] = current_task
        _stats_data["current_phase"] = current_phase
        _stats_data["phase_status"] = phase_status or ("running" if active_count else "done")
        _stats_data["in_progress_count"] = active_count
        _stats_data["last_tick_at"] = now
        if workspace_name:
            _stats_data["workspace"] = workspace_name


class _StatsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        engine_log(
            "[stats-api] %s - [%s] %s",
            self.address_string(),
            self.log_date_time_string(),
            format % args,
        )

    def do_GET(self):
        if self.path == "/api/stats":
            try:
                with _stats_lock:
                    payload = json.dumps(_stats_data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as exc:
                engine_log(f"[stats-api] 响应失败: {exc}")
                try:
                    self.send_response(500)
                    self.end_headers()
                except Exception as exc:
                    _log.debug("[stats-api] error response failed: %s", exc)
        else:
            self.send_response(404)
            self.end_headers()


def _stats_snapshot() -> dict:
    """HTTP 线程用的快照方法：与 _update_stats 共享锁。"""
    with _stats_lock:
        return dict(_stats_data)


def _run_stats_server(port: int) -> None:
    """在独立线程跑轻量 HTTP 服务，仅 127.0.0.1。"""
    try:
        server = HTTPServer(("127.0.0.1", port), _StatsHandler)
    except OSError as exc:
        engine_log(f"Stats HTTP 启动失败 (port={port}): {exc}")
        return
    engine_log(f"Stats HTTP 服务启动在 http://127.0.0.1:{port}/api/stats")

    def _serve():
        try:
            while not _engine_shutdown:
                server.handle_request()
        except Exception as exc:
            engine_log(f"Stats HTTP 服务异常: {exc}")
        finally:
            try:
                server.server_close()
            except Exception as exc:
                _log.debug("[stats-api] server_close failed: %s", exc)
            engine_log("Stats HTTP 服务关闭")

    t = threading.Thread(target=_serve, name="ccc-stats-http", daemon=True)
    t.start()
