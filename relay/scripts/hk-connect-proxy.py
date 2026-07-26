#!/usr/bin/env python3
"""极简 HTTP CONNECT 代理 — 香港机 127.0.0.1:18080（仅本机）。"""
from __future__ import annotations

import os
import select
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = os.environ.get("CCC_HK_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("CCC_HK_PROXY_PORT", "18080"))


def _pipe(a: socket.socket, b: socket.socket) -> None:
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 300)
            if not r:
                break
            for s in r:
                other = b if s is a else a
                data = s.recv(65536)
                if not data:
                    return
                other.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # quieter
        if os.environ.get("CCC_HK_PROXY_VERBOSE"):
            super().log_message(fmt, *args)

    def do_CONNECT(self) -> None:  # noqa: N802
        host_port = self.path
        try:
            host, port_s = host_port.rsplit(":", 1)
            port = int(port_s)
        except ValueError:
            self.send_error(400, "Bad CONNECT target")
            return
        try:
            upstream = socket.create_connection((host, port), timeout=30)
        except OSError as e:
            self.send_error(502, f"Upstream connect failed: {e}")
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        client = self.connection
        t = threading.Thread(target=_pipe, args=(client, upstream), daemon=True)
        t.start()
        # keep handler thread until pipe ends
        t.join()

    def do_GET(self) -> None:  # noqa: N802
        self.send_error(400, "CONNECT only")


def main() -> None:
    httpd = HTTPServer((HOST, PORT), Handler)
    print(f"[hk-connect-proxy] listening {HOST}:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
