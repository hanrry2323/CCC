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

    # Parallel probe projects for dynamic metrics
    project_metrics = {}

    def _probe_project(project_name: str, probe_func):
        try:
            project_metrics[project_name] = probe_func()
        except Exception:
            project_metrics[project_name] = {"status": "离线", "alive": False}

    def _probe_qb():
        host = "192.168.3.140"
        port = 8096
        alive = probe_port(host, port)
        return {
            "status": "运行中" if alive else "离线",
            "alive": alive,
        }

    def _probe_medio():
        host = "192.168.3.131"
        port = 3000
        alive = probe_port(host, port)
        return {
            "status": "已部署 / 运行中" if alive else "离线",
            "alive": alive,
        }

    def _probe_xianyu():
        return {
            "status": "等待开发",
            "alive": None,
        }

    project_threads = []
    project_probe_map = {
        "qb": _probe_qb,
        "medio-0": _probe_medio,
        "xianyu": _probe_xianyu,
    }
    for project_name, probe_func in project_probe_map.items():
        t = Thread(target=_probe_project, args=(project_name, probe_func))
        t.start()
        project_threads.append(t)
    for t in project_threads:
        t.join(timeout=2)

    for project in data["projects"]:
        name = project["name"]
        if name in project_metrics:
            project["metric"] = project_metrics[name]
        else:
            project["metric"] = {"status": "—", "alive": None}

    data["updated"] = datetime.now().strftime("%H:%M:%S")
    data["board"] = _fetch_board_summary()
    return data


def _fetch_board_summary() -> dict:
    """Fetch board column counts + KPI summary from board-server (:7777).

    Returns a dict ready for render_html, or None when board-server is offline.
    """
    base = "http://127.0.0.1:7777"
    workspace = "CCC"
    columns = {
        "backlog": 0,
        "planned": 0,
        "in_progress": 0,
        "testing": 0,
        "verified": 0,
        "released": 0,
        "abnormal": 0,
    }
    kpi = {
        "in_progress": 0,
        "abnormal": 0,
        "ready_to_release": 0,
        "today_released": 0,
        "today_fixed": 0,
    }
    workspaces = {}

    def _http_get_json(url: str):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    board = _http_get_json(
        f"{base}/api/board?workspace={urllib.parse.quote(workspace)}"
    )
    if isinstance(board, dict):
        cols = board.get("columns") or {}
        for k in columns:
            if k in cols:
                try:
                    columns[k] = int(cols[k])
                except (TypeError, ValueError):
                    pass
        ws = board.get("workspaces") or {}
        for name, path in ws.items():
            workspaces[name] = path

    dashboard = _http_get_json(
        f"{base}/api/dashboard?workspace={urllib.parse.quote(workspace)}"
    )
    if isinstance(dashboard, dict):
        d_kpi = dashboard.get("kpi") or {}
        if "in_progress" in d_kpi:
            try:
                kpi["in_progress"] = int(d_kpi["in_progress"])
            except (TypeError, ValueError):
                pass
        if "abnormal" in d_kpi:
            try:
                kpi["abnormal"] = int(d_kpi["abnormal"])
            except (TypeError, ValueError):
                pass
        if "ready_to_release" in d_kpi:
            try:
                kpi["ready_to_release"] = int(d_kpi["ready_to_release"])
            except (TypeError, ValueError):
                pass
        today = d_kpi.get("today") or {}
        if "released" in today:
            try:
                kpi["today_released"] = int(today["released"])
            except (TypeError, ValueError):
                pass
        if "fixed" in today:
            try:
                kpi["today_fixed"] = int(today["fixed"])
            except (TypeError, ValueError):
                pass
        if not workspaces:
            ws = dashboard.get("workspaces") or {}
            for name, path in ws.items():
                workspaces[name] = path

    if board is None and dashboard is None:
        return None

    return {
        "columns": columns,
        "kpi": kpi,
        "workspaces": workspaces,
        "last_updated": datetime.now().strftime("%H:%M"),
    }


BOARD_COLUMN_COLORS = {
    "backlog": "#9aa0a6",
    "planned": "#1976d2",
    "in_progress": "#b25000",
    "testing": "#6a1b9a",
    "verified": "#1a7d1a",
    "released": "#0d5d0d",
    "abnormal": "#c62828",
}
BOARD_COLUMN_LABELS = {
    "backlog": "Backlog",
    "planned": "Planned",
    "in_progress": "进行中",
    "testing": "Testing",
    "verified": "Verified",
    "released": "Released",
    "abnormal": "异常",
}


def _render_board_section(board) -> str:
    """Render the board overview section. Returns HTML string."""
    if not board:
        return '<div style="background:{surface};border:1px solid {border};border-radius:8px;padding:14px;font-size:13px;color:{muted}">看板服务离线</div>'.format(
            surface=THEME["surface"], border=THEME["border"], muted=THEME["muted"]
        )

    cols = board.get("columns") or {}
    kpi = board.get("kpi") or {}

    cards_html = ""
    for key in [
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ]:
        count = cols.get(key, 0)
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 0
        color = BOARD_COLUMN_COLORS.get(key, THEME["muted"])
        label = BOARD_COLUMN_LABELS.get(key, key)
        opacity = "1" if count > 0 else "0.45"
        cards_html += (
            f'<div class="board-card" style="border-left:3px solid {color};opacity:{opacity}">'
            f'<div class="board-card-label">{label}</div>'
            f'<div class="board-card-count" style="color:{color}">{count}</div>'
            f"</div>"
        )

    def _kpi_pair(label: str, value) -> str:
        try:
            v = int(value)
        except (TypeError, ValueError):
            v = 0
        color = "#1a7d1a" if v == 0 else "#b25000"
        if label == "异常":
            color = "#c62828" if v > 0 else "#1a7d1a"
        return f'<div class="kpi-pill"><span class="kpi-lbl">{label}</span><span class="kpi-val" style="color:{color}">{v}</span></div>'

    kpi_html = (
        _kpi_pair("进行中", kpi.get("in_progress", 0))
        + _kpi_pair("异常", kpi.get("abnormal", 0))
        + _kpi_pair("待发布", kpi.get("ready_to_release", 0))
        + _kpi_pair("今日发布", kpi.get("today_released", 0))
        + _kpi_pair("今日修复", kpi.get("today_fixed", 0))
    )

    last_updated = board.get("last_updated", "")
    return (
        '<div style="background:{surface};border:1px solid {border};border-radius:8px;padding:14px">'
        '<div class="board-cards">{cards}</div>'
        '<div class="board-kpi">{kpi}</div>'
        '<div class="board-meta">数据更新时间：{ts}</div>'
        "</div>"
    ).format(
        surface=THEME["surface"],
        border=THEME["border"],
        cards=cards_html,
        kpi=kpi_html,
        ts=last_updated or "—",
    )


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

        # Build metric column
        metric = p.get("metric", {})
        metric_status = metric.get("status", "—")
        metric_alive = metric.get("alive")
        if metric_alive is True:
            metric_dot = f'<span class="dot dot-green"></span>'
            metric_html = f"{metric_dot} {metric_status}"
        elif metric_alive is False:
            metric_dot = f'<span class="dot dot-red"></span>'
            metric_html = f"{metric_dot} {metric_status}"
        else:
            metric_html = metric_status

        projects_html += f"""
        <tr>
            <td><strong>{p["name"]}</strong></td>
            <td class="num">{p["version"]}</td>
            <td>{badge}</td>
            <td>{metric_html}</td>
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
:root {{
  --bg: #f5f5f7;
  --surface: #ffffff;
  --text: #1d1d1f;
  --muted: #86868b;
  --accent: #0066cc;
  --accent-hover: #0052a3;
  --border: #d2d2d7;
  --green: #1a7d1a;
  --green-hover: #146614;
  --red: #c62828;
  --red-hover: #a51f1f;
  --yellow: #b25000;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 14px;
  --space-lg: 20px;
  --space-xl: 24px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5}}
.wrap{{max-width:1100px;margin:0 auto;padding:var(--space-xl)}}
.hdr{{display:flex;justify-content:space-between;align-items:center;padding-bottom:var(--space-md);border-bottom:2px solid var(--border);margin-bottom:var(--space-lg)}}
.hdr h1{{font-size:22px;font-weight:600}}
.hdr .ts{{color:var(--muted);font-size:12px}}
.sec-title{{font-size:13px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin:var(--space-xl) 0 var(--space-sm)}}
.machines{{display:flex;gap:var(--space-md);flex-wrap:wrap;margin-bottom:var(--space-sm)}}
.machine-chip{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:var(--space-sm) var(--space-md);display:flex;gap:var(--space-md);align-items:center;font-size:13px}}
.machine-chip .ip{{color:var(--accent);font-family:ui-monospace,monospace}}
.machine-chip .role{{color:var(--muted);font-size:12px}}
.tbl-wrap{{overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--surface)}}
table{{width:100%;border-collapse:collapse;min-width:500px}}
th,td{{padding:var(--space-sm) var(--space-md);text-align:left;border-bottom:1px solid #f0f0f2;vertical-align:middle}}
th{{font-size:11px;font-weight:600;color:var(--muted);background:#fafafa;white-space:nowrap}}
tr:last-child td{{border-bottom:none}}
.num{{font-family:ui-monospace,monospace;white-space:nowrap}}
.host{{font-family:ui-monospace,monospace;font-size:12px;color:var
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

  <div class="sec-title">看板概览</div>
  {_render_board_section(data.get("board"))}

  <div class="sec-title">项目</div>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr><th>项目</th><th>版本</th><th>状态</th><th>关键指标</th></tr>
      </thead>
      <tbody>{projects_html or '<tr><td colspan="4" style="text-align:center;color:#86868b">无数据</td></tr>'}</tbody>
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
        elif path == "/api/board":
            board = _fetch_board_summary()
            if board is None:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": "board server unavailable"}).encode("utf-8")
                )
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(board).encode("utf-8"))
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
