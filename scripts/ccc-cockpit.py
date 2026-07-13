#!/usr/bin/env python3
"""ccc-cockpit.py — CCC 总控台 (v0.1)

读取 .ccc/infrastructure.md 并在浏览器中展示所有机器、端口、项目状态。
绑定 :7778，零外部依赖。

用法:
    python3 scripts/ccc-cockpit.py
    浏览器打开 http://localhost:7778
"""

import json
import os
import re
import socket
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread

# ── Config ──
PORT = int(os.environ.get("CCC_COCKPIT_PORT", "7778"))
HOST = os.environ.get("CCC_COCKPIT_HOST", "0.0.0.0")
INFRA_FILE = Path(__file__).resolve().parent.parent / ".ccc" / "infrastructure.md"

# ── Colors for the Cockpit UI ──
THEME = {
    "bg": "#f5f5f7",
    "surface": "#ffffff",
    "text": "#1d1d1f",
    "muted": "#86868b",
    "accent": "#0066cc",
    "border": "#d2d2d7",
    "green": "#1a7d1a",
    "red": "#c62828",
    "yellow": "#b25000",
}


def parse_infra() -> dict:
    """Parse infrastructure.md into a structured dict."""
    if not INFRA_FILE.exists():
        return {"error": f"infrastructure.md not found at {INFRA_FILE}"}

    text = INFRA_FILE.read_text(encoding="utf-8")

    result = {
        "machines": [],
        "ports": {},
        "projects": [],
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    current_section = None
    current_machine = None
    current_ports = []
    current_projects = []

    for line in text.splitlines():
        # Section headers - capture full section name
        m = re.match(r"^## (.+)", line)
        if m:
            current_section = m.group(1).strip()
            continue

        # Machine list table
        m = re.match(r"^\| (\w[\w ]+?)\s+\| (\d+\.\d+\.\d+\.\d+)\s+\| (\w+)", line)
        if m and current_section == "机器清单":
            result["machines"].append(
                {"name": m.group(1), "ip": m.group(2), "role": m.group(3)}
            )

        # Port table (| 4000 | 中转站 Anthropic | ...)
        m = re.match(r"^\| (\d+)\s+\| ([^|]+)\s+\|", line)
        if (
            m
            and current_section
            and any(x in current_section for x in ["端口", "生产机", "编译站"])
        ):
            port = int(m.group(1))
            name = m.group(2).strip()
            result["ports"][port] = {
                "name": name,
                "host": _get_section_host(current_section, result),
                "alive": None,  # filled by probe
                "machine": _get_section_machine(current_section),
            }

    # Parse project status table
    in_projects = False
    for line in text.splitlines():
        m = re.match(r"^\| ([\w/-]+)\s+\| (v[\w.]+)\s+\| (.+?) \s+\|", line)
        if m and "项目状态" in text and _is_project_table(line, text):
            result["projects"].append(
                {
                    "name": m.group(1),
                    "version": m.group(2),
                    "status": m.group(3).strip(),
                }
            )

    # Try to parse project table more simply
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("| 项目 | 版本"):
            for j in range(i + 3, len(lines)):
                if not lines[j].startswith("|"):
                    break
                parts = [p.strip() for p in lines[j].split("|") if p.strip()]
                if len(parts) >= 3:
                    result["projects"].append(
                        {
                            "name": parts[0],
                            "version": parts[1],
                            "status": parts[2],
                        }
                    )

    return result


def _get_section_host(section: str, result: dict) -> str:
    for m in result["machines"]:
        if m["name"].lower() in section.lower():
            return m["ip"]
    return "127.0.0.1"


def _get_section_machine(section: str) -> str:
    for m_name in ["M1", "Mac 2017", "feiniu"]:
        if m_name in section:
            return m_name
    return "unknown"


def _is_project_table(line: str, text: str) -> bool:
    """Check if we're in the project status table section."""
    idx = text.find(line)
    before = text[max(0, idx - 200) : idx]
    return "项目状态" in before


def probe_port(host: str, port: int) -> bool:
    """Check if a TCP port is open."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def probe_http(host: str, port: int) -> tuple:
    """Check if an HTTP endpoint responds. Returns (alive, status_code, label)."""
    try:
        req = urllib.request.Request(f"http://{host}:{port}/", method="HEAD")
        req.timeout = 3
        with urllib.request.urlopen(req) as resp:
            return (True, resp.status, "正常")
    except urllib.error.HTTPError as e:
        # 404/401 still means the server is alive
        return (True, e.code, "运行中")
    except Exception:
        return (False, 0, "未响应")


def build_cockpit_data() -> dict:
    """Build the full cockpit data with live probes."""
    data = parse_infra()

    # Parallel probe all ports using threads
    results = {}

    def _probe_one(port: int, info: dict):
        host = info.get("host", "127.0.0.1")
        alive = probe_port(host, port)
        if alive:
            http_result = probe_http(host, port)
            results[port] = {
                "alive": http_result[0],
                "http_status": http_result[1],
                "label": http_result[2],
            }
        else:
            results[port] = {"alive": False, "http_status": 0, "label": "未响应"}

    threads = []
    for port, info in data["ports"].items():
        t = Thread(target=_probe_one, args=(port, info))
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=5)

    for port, info in data["ports"].items():
        if port in results:
            info.update(results[port])
        else:
            info["alive"] = None
            info["http_status"] = 0
            info["label"] = "探测超时"

    data["updated"] = datetime.now().strftime("%H:%M:%S")
    return data


def render_html(data: dict) -> str:
    """Render the full Cockpit HTML page."""
    machines_html = ""
    for m in data.get("machines", []):
        badge_color = THEME["green"] if m["name"] == "M1" else THEME["accent"]
        machines_html += f"""
        <div class="machine-chip" style="border-left:3px solid {badge_color}">
            <strong>{m["name"]}</strong>
            <span class="ip">{m["ip"]}</span>
            <span class="role">{m["role"]}</span>
        </div>"""

    # Group ports by machine
    ports_by_machine: dict[str, list] = {"M1": [], "Mac 2017": [], "feiniu": []}
    for port in sorted(data.get("ports", {}).keys()):
        info = data["ports"][port]
        machine = info.get("machine", "M1")
        if machine not in ports_by_machine:
            ports_by_machine[machine] = []
        ports_by_machine[machine].append((port, info))

    def _machine_port_table(machine_name: str, entries: list) -> str:
        if not entries:
            return '<div style="color:#86868b;padding:10px;font-size:13px">无端口信息</div>'
        rows = ""
        for port, info in entries:
            alive = info.get("alive")
            if alive is True:
                dot = f'<span class="dot dot-green"></span>'
                status_text = info.get("label", "运行中")
            elif alive is False:
                dot = f'<span class="dot dot-red"></span>'
                status_text = "离线"
            else:
                dot = f'<span class="dot dot-gray"></span>'
                status_text = "待检测"
            host = info.get("host", "127.0.0.1")
            url = f"http://{host}:{port}"
            rows += f"""
            <tr>
                <td class="num"><a href="{url}" target="_blank" class="port-link">:{port}</a></td>
                <td>{info["name"]}</td>
                <td class="host">{host}</td>
                <td>{dot} {status_text}</td>
            </tr>"""
        return f"""<div class="tbl-wrap" style="margin-bottom:8px">
          <table>
            <thead><tr><th>端口</th><th>服务</th><th>主机</th><th>状态</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    ports_sections = ""
    for m_name in ["M1", "Mac 2017", "feiniu"]:
        entries = ports_by_machine.get(m_name, [])
        ports_sections += f"""
      <div class="sec-title" style="margin-top:12px">{m_name}</div>
      {_machine_port_table(m_name, entries)}"""

    projects_html = ""
    for p in data.get("projects", []):
        status = p["status"]
        if "运行" in status:
            badge = f'<span class="badge badge-green">{status}</span>'
        elif "开发" in status or "等待" in status:
            badge = f'<span class="badge badge-yellow">{status}</span>'
        elif "排除" in status:
            badge = f'<span class="badge badge-gray">{status}</span>'
        else:
            badge = f'<span class="badge">{status}</span>'
        projects_html += f"""
        <tr>
            <td><strong>{p["name"]}</strong></td>
            <td class="num">{p["version"]}</td>
            <td>{badge}</td>
        </tr>"""

    script_html = """<script>
  function checkAlerts() {
   fetch('/api/alive')
   .then(function(res) { return res.json(); })
   .then(function(data) {
    var ports = data.ports || {};
    var offlinePorts = Object.entries(ports).filter(function(entry) { var _ref = entry, port = _ref[0], info = _ref[1]; return !info.alive; });
    if (offlinePorts.length > 0) {
     var banner = document.getElementById('alert-banner');
     var countSpan = document.getElementById('alert-count');
     var detailsDiv = document.getElementById('alert-details');
     countSpan.textContent = offlinePorts.length;
     detailsDiv.innerHTML = '<table width="100%" border-collapse:collapse;font-size:12px><thead><tr style="background:#ffebee"><th>端口</th><th>服务</th><th>主机</th></tr></thead><tbody>' + offlinePorts.map(function(entry) { var _ref = entry, port = _ref[0], info = _ref[1]; return '<tr><td>:' + port + '</td><td>' + info.name + '</td><td>' + info.host + '</td></tr>'; }).join('') + '</tbody></table>';
     banner.style.display = 'block';
     banner.onclick = function() {
      var isShown = detailsDiv.style.display === 'block';
      detailsDiv.style.display = isShown ? 'none' : 'block';
     };
         } else {
      document.getElementById('alert-banner').style.display = 'none';
     }
    })
    .catch(function(err) { console.error('Failed to check alerts:', err); });
}
function kbSearch() {
    var query = document.getElementById('kb-query').value.trim();
    var resultsDiv = document.getElementById('kb-results');
    if (!query) {
        resultsDiv.innerHTML = '<span style="color:#86868b">请输入关键词</span>';
        return;
    }
    resultsDiv.innerHTML = '<span style="color:#86868b">搜索中…</span>';
    fetch('/api/kb/search?q=' + encodeURIComponent(query))
        .then(function(res) {
            if (!res.ok) {
                throw new Error('Search failed');
            }
            return res.json();
        })
        .then(function(data) {
            if (data.error) {
                resultsDiv.innerHTML = '<span style="color:#c62828">搜索失败，请稍后重试</span>';
                return;
            }
            var results = data.results || [];
            if (results.length === 0) {
                resultsDiv.innerHTML = '<span style="color:#86868b">未找到相关结果</span>';
                return;
            }
            var html = '<table width="100%" border-collapse:collapse;font-size:12px">';
            html += '<thead><tr style="background:#fafafa"><th>标题</th><th>链接</th><th>摘要</th></tr></thead>';
            html += '<tbody>';
            results.forEach(function(item) {
                var title = item.title || item.name || item.path || '';
                var link = item.url || item.path || '#';
                var snippet = item.snippet || item.description || item.content || '';
                var safeTitle = title.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                var safeSnippet = snippet.substring(0, 100).replace(/</g, '&lt;').replace(/>/g, '&gt;');
                html += '<tr><td><a href="' + link + '" target="_blank" style="color:#0066cc;text-decoration:none">' + safeTitle + '</a></td>';
                html += '<td style="color:#86868b">' + link + '</td>';
                html += '<td style="color:#86868b;max-width:300px">' + safeSnippet + '…</td></tr>';
            });
            html += '</tbody></table>';
            resultsDiv.innerHTML = html;
        })
        .catch(function(err) {
            console.error('KB search error:', err);
            resultsDiv.innerHTML = '<span style="color:#c62828">搜索失败，请稍后重试</span>';
        });
}
  setInterval(checkAlerts, 15000);
  checkAlerts();
 </script>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CCC Cockpit — 总控台</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:{THEME["bg"]};color:{THEME["text"]};font-size:14px;line-height:1.5}}
.wrap{{max-width:1100px;margin:0 auto;padding:20px}}
.hdr{{display:flex;justify-content:space-between;align-items:center;padding-bottom:16px;border-bottom:2px solid {THEME["border"]};margin-bottom:20px}}
.hdr h1{{font-size:22px;font-weight:600}}
.hdr .ts{{color:{THEME["muted"]};font-size:12px}}
.sec-title{{font-size:13px;font-weight:600;color:{THEME["muted"]};text-transform:uppercase;letter-spacing:.04em;margin:24px 0 10px}}
.machines{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px}}
.machine-chip{{background:{THEME["surface"]};border:1px solid {THEME["border"]};border-radius:10px;padding:10px 14px;display:flex;gap:12px;align-items:center;font-size:13px}}
.machine-chip .ip{{color:{THEME["accent"]};font-family:ui-monospace,monospace}}
.machine-chip .role{{color:{THEME["muted"]};font-size:12px}}
.tbl-wrap{{overflow-x:auto;border:1px solid {THEME["border"]};border-radius:8px;background:{THEME["surface"]}}}
table{{width:100%;border-collapse:collapse;min-width:500px}}
th,td{{padding:8px 14px;text-align:left;border-bottom:1px solid #f0f0f2;vertical-align:middle}}
th{{font-size:11px;font-weight:600;color:{THEME["muted"]};background:#fafafa;white-space:nowrap}}
tr:last-child td{{border-bottom:none}}
.num{{font-family:ui-monospace,monospace;white-space:nowrap}}
.host{{font-family:ui-monospace,monospace;font-size:12px;color:{THEME["muted"]}}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;vertical-align:middle;margin-right:4px}}
.dot-green{{background:{THEME["green"]}}}
.dot-red{{background:{THEME["red"]}}}
.dot-gray{{background:{THEME["border"]}}}
.badge{{font-size:11px;padding:2px 8px;border-radius:10px;background:#f0f0f2}}
.badge-green{{background:#e8f5e9;color:{THEME["green"]}}}
.badge-yellow{{background:#fff3e0;color:{THEME["yellow"]}}}
.badge-gray{{background:#f0f0f2;color:{THEME["muted"]}}}
.port-link{{color:{THEME["accent"]};text-decoration:none}}
.port-link:hover{{text-decoration:underline}}
.quick-links{{display:flex;gap:10px;flex-wrap:wrap;margin:4px 0 8px}}
.quick-links a{{background:{THEME["surface"]};border:1px solid {THEME["border"]};border-radius:8px;padding:8px 16px;text-decoration:none;color:{THEME["text"]};font-size:13px}}
.quick-links a:hover{{background:#f0f4ff;border-color:{THEME["accent"]}}}
.foot{{margin-top:20px;font-size:11px;color:{THEME["muted"]};text-align:center}}
@media(max-width:640px){{.wrap{{padding:12px}}.machine-chip{{width:100%}}}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>  CCC Cockpit</h1>
    <span class="ts">{datetime.now().strftime("%H:%M")}</span>
  </div>

  <div class="sec-title">机器</div>
  <div class="machines">{machines_html}</div>

  <div class="sec-title" style="margin-top:16px">快速跳转</div>
          <div class="quick-links">
    <a href="http://192.168.3.140:7777/" target="_blank">CCC 看板</a>
    <a href="http://192.168.3.140:8084" target="_blank">CCC Chat</a>
    <a href="http://192.168.3.140:8096" target="_blank">qb Dashboard</a>
    <a href="http://192.168.3.140:4000/dashboard" target="_blank">中转站</a>
    <a href="http://192.168.3.131:3000" target="_blank">Medio-0 (HP)</a>
          </div>

    <div class="sec-title">知识库搜索</div>
    <div class="kb-search-wrap" style="background:{THEME["surface"]};border:1px solid {THEME["border"]};border-radius:8px;padding:12px;margin-bottom:8px">
        <div style="display:flex;gap:8px;margin-bottom:8px">
            <input type="text" id="kb-query" placeholder="搜索关键词…" style="flex:1;padding:8px 12px;border:1px solid {THEME["border"]};border-radius:6px;font-size:13px">
            <button onclick="kbSearch()" style="padding:8px 16px;background:{THEME["accent"]};border:none;color:white;border-radius:6px;font-size:13px;cursor:pointer">搜索</button>
        </div>
        <div id="kb-results" style="font-size:12px;line-height:1.6"></div>
    </div>

    <div class="sec-title">端口 & 服务</div>
  {ports_sections}

  <div class="sec-title">项目</div>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr><th>项目</th><th>版本</th><th>状态</th></tr>
      </thead>
      <tbody>{projects_html or '<tr><td colspan="3" style="text-align:center;color:#86868b">无数据</td></tr>'}</tbody>
    </table>
  </div>

  <div class="foot" id="foot">
   数据来源: .ccc/infrastructure.md · 端口探测 · 最后刷新 <span id="ts">{data.get("updated", "")}</span>
  </div>
 </div>

 <div id="alert-banner" style="display:none;background:#ffebee;border:2px solid #c62828;color:#c62828;padding:12px;border-radius:8px;margin-bottom:16px;cursor:pointer;font-size:13px">
  <span id="alert-count">0</span> 个服务离线 — 点击查看详情
  <div id="alert-details" style="display:none;margin-top:8px;background:white;padding:10px;border-radius:4px;border:1px solid #c62828"></div>
 </div>

 {script_html}
</body>
</html>"""


class CockpitHandler(BaseHTTPRequestHandler):
    """HTTP handler for Cockpit."""

    def do_GET(self):
        # Parse path without query string
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/" or path == "/cockpit":
            data = build_cockpit_data()
            html = render_html(data)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        elif path == "/api/alive":
            # API endpoint for live probes (used by auto-refresh)
            data = build_cockpit_data()
            # Strip HTML-only fields
            result = {
                "ports": {
                    str(k): {
                        "alive": v["alive"],
                        "name": v["name"],
                        "host": v.get("host", "127.0.0.1"),
                    }
                    for k, v in data["ports"].items()
                },
                "projects": data["projects"],
                "updated": data["updated"],
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
        elif path == "/api/kb/search":
            # KB search proxy endpoint
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get("q", [""])[0] if params.get("q") else ""
            kb_url = (
                f"http://127.0.0.1:8082/memories?query={urllib.parse.quote_plus(query)}"
            )
            try:
                request = urllib.request.Request(kb_url, method="GET")
                request.timeout = 3
                with urllib.request.urlopen(request) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"results": result}).encode("utf-8"))
            except urllib.error.URLError as e:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": "KB search failed", "detail": str(e)}).encode(
                        "utf-8"
                    )
                )
            except Exception:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "error": "KB search failed",
                            "detail": "Timeout or network error",
                        }
                    ).encode("utf-8")
                )
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def log_message(self, format, *args):
        # Suppress default log output, keep it clean
        pass


def main():
    server = HTTPServer((HOST, PORT), CockpitHandler)
    print(f"  CCC Cockpit 启动")
    print(f"  地址: http://localhost:{PORT}")
    print(f"  来源: {INFRA_FILE}")
    print(f"  按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Cockpit 已停止")
        server.server_close()


if __name__ == "__main__":
    main()
