#!/usr/bin/env python3
"""CCC Hub Ops probes — 只读聚合（infrastructure / ports / resources / git / risks）。

供 chat_server/routers/ops.py 与日审调度复用。禁止复活 cluster-bus。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
CCC_HOME = SCRIPTS.parent
INFRA_FILE = CCC_HOME / ".ccc" / "infrastructure.md"
PATROL_STATE = Path.home() / ".ccc" / "patrol-state.json"

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCK = Lock()
_PORT_CACHE_TTL = 30.0
_RUN_DEBOUNCE: dict[str, float] = {}
_RUN_LOCK = Lock()

PORT_GROUPS = (
    ("CCC", (7775, 7777, 7778)),
    ("模型中转", (4000, 4002)),
    ("HP", (8080, 8082, 8083)),
    ("qb", (8095, 8096)),
)

ROLE_LABELS = {
    "开发机": "开发",
    "编译站": "编译",
    "生产机": "生产",
    "CCC Server": "CCC Server",
    "**CCC Server**": "CCC Server",
}


def _strip_md(s: str) -> str:
    """Strip light markdown emphasis from table cells."""
    t = (s or "").strip()
    t = re.sub(r"^\*\*(.+?)\*\*$", r"\1", t)
    t = re.sub(r"^__(.+?)__$", r"\1", t)
    t = re.sub(r"^\*(.+?)\*$", r"\1", t)
    return t.strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def _cache_get(key: str, ttl: float) -> Any | None:
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if not hit:
            return None
        ts, val = hit
        if time.time() - ts > ttl:
            return None
        return val


def _cache_set(key: str, val: Any) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), val)


def parse_infra(path: Path | None = None) -> dict:
    """Parse infrastructure.md into machines / ports / projects."""
    infra = path or INFRA_FILE
    if not infra.is_file():
        return {"error": f"missing {infra}", "machines": [], "ports": {}, "projects": []}

    text = infra.read_text(encoding="utf-8")
    result: dict[str, Any] = {
        "machines": [],
        "ports": {},
        "projects": [],
        "infra_path": str(infra),
        "updated": _now_iso(),
    }
    current_section = None

    for line in text.splitlines():
        m = re.match(r"^## (.+)", line)
        if m:
            current_section = m.group(1).strip()
            continue

        # Allow **bold** host names (e.g. **Mac 2017**) — \w alone misses them.
        m = re.match(
            r"^\|+\s*(.+?)\s*\|\s*(\d+\.\d+\.\d+\.\d+)\s*\|\s*([^|]+)\|",
            line,
        )
        if m and current_section == "机器清单":
            name = _strip_md(m.group(1))
            if name.lower() in ("主机", "host", "---") or set(name) <= {"-"}:
                continue
            role_raw = _strip_md(m.group(3))
            result["machines"].append(
                {
                    "name": name,
                    "ip": m.group(2).strip(),
                    "role": ROLE_LABELS.get(role_raw, role_raw),
                    "role_raw": role_raw,
                }
            )

        m = re.match(r"^\| (\*?\*?~?\d+~?\*?\*?)\s+\| ([^|]+)\s+\|", line)
        if (
            m
            and current_section
            and any(
                x in current_section
                for x in (
                    "端口",
                    "生产机",
                    "编译站",
                    "CCC Server",
                    "Server",
                    "Mac 2017",
                    "Mac2017",
                )
            )
        ):
            raw_port = re.sub(r"[^\d]", "", m.group(1))
            if not raw_port:
                continue
            port = int(raw_port)
            # skip strikethrough deprecated ports in markdown ~~8084~~
            if "~~" in m.group(1):
                continue
            name = m.group(2).strip()
            result["ports"][port] = {
                "name": name,
                "host": _section_host(current_section, result["machines"]),
                "machine": _section_machine(current_section),
                "alive": None,
            }

    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("| 项目 | 版本"):
            for j in range(i + 2, len(lines)):
                if not lines[j].startswith("|"):
                    break
                if re.match(r"^\|\s*-+", lines[j]):
                    continue
                parts = [p.strip() for p in lines[j].split("|") if p.strip()]
                if len(parts) >= 3:
                    result["projects"].append(
                        {
                            "name": parts[0],
                            "version": parts[1],
                            "status": parts[2],
                        }
                    )
            break

    return result


def _section_host(section: str, machines: list[dict]) -> str:
    low = section.lower()
    for m in machines:
        if m["name"].lower() in low or m["name"].replace(" ", "").lower() in low.replace(
            " ", ""
        ):
            return m["ip"]
    return "127.0.0.1"


def _section_machine(section: str) -> str:
    for name in ("M1", "Mac 2017", "Mac2017", "feiniu"):
        if name.lower().replace(" ", "") in section.lower().replace(" ", ""):
            return name if name != "Mac2017" else "Mac 2017"
    return "unknown"


def probe_port(host: str, port: int, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_http(host: str, port: int, timeout: float = 1.2) -> tuple[bool, int, str]:
    try:
        req = urllib.request.Request(f"http://{host}:{port}/", method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, int(getattr(resp, "status", 200) or 200), "HTTP OK"
    except urllib.error.HTTPError as e:
        # 401/404 still means listener alive
        return True, int(e.code), f"HTTP {e.code}"
    except Exception:
        return False, 0, "未响应"


def probe_ports(infra: dict | None = None, *, use_cache: bool = True) -> dict:
    cached = _cache_get("ports", _PORT_CACHE_TTL) if use_cache else None
    if cached is not None:
        return cached

    data = infra or parse_infra()
    ports = dict(data.get("ports") or {})
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _one(port: int, info: dict) -> tuple[int, dict]:
        host = info.get("host") or "127.0.0.1"
        # Prefer localhost for M1 services when probing from M1
        if info.get("machine") in ("M1", "unknown") and host.startswith("192.168."):
            # Try 127.0.0.1 first for local ports
            local_ok = probe_port("127.0.0.1", port)
            if local_ok:
                http_ok, status, label = probe_http("127.0.0.1", port)
                return port, {
                    **info,
                    "alive": True,
                    "http_status": status if http_ok else 0,
                    "label": label if http_ok else "TCP open",
                    "probed_host": "127.0.0.1",
                }
        alive = probe_port(host, port)
        probed = host
        if not alive and host.startswith("192.168."):
            # Same-host services may bind 127.0.0.1 only (e.g. Board :7775)
            if probe_port("127.0.0.1", port):
                alive = True
                probed = "127.0.0.1"
        if alive:
            http_ok, status, label = probe_http(probed, port)
            return port, {
                **info,
                "alive": True,
                "http_status": status if http_ok else 0,
                "label": label if http_ok else "TCP open",
                "probed_host": probed,
            }
        return port, {
            **info,
            "alive": False,
            "http_status": 0,
            "label": "未响应",
            "probed_host": host,
        }

    out: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = [pool.submit(_one, p, info) for p, info in ports.items()]
        for fut in as_completed(futs):
            port, info = fut.result()
            out[port] = info

    grouped: list[dict] = []
    assigned: set[int] = set()
    for gname, plist in PORT_GROUPS:
        items = []
        for p in plist:
            if p in out:
                items.append({"port": p, **out[p]})
                assigned.add(p)
        grouped.append({"group": gname, "ports": items})
    other = [{"port": p, **info} for p, info in sorted(out.items()) if p not in assigned]
    if other:
        grouped.append({"group": "其他", "ports": other})

    result = {
        "ports": {str(k): v for k, v in out.items()},
        "groups": grouped,
        "infra_path": data.get("infra_path"),
        "generated_at": _now_iso(),
        "cache_ttl_s": _PORT_CACHE_TTL,
    }
    _cache_set("ports", result)
    return result


def overview() -> dict:
    infra = parse_infra()
    ports = probe_ports(infra)
    machines = []
    for m in infra.get("machines") or []:
        # machine online if any of its ports alive, or TCP to SSH-ish / ping via first port
        mine = [
            p
            for p, info in (ports.get("ports") or {}).items()
            if (info or {}).get("machine") == m["name"]
            or (info or {}).get("host") == m["ip"]
        ]
        alive_n = sum(
            1
            for p in mine
            if (ports["ports"].get(p) or {}).get("alive")
        )
        # fallback: probe host:22 or just mark reachable if any port on IP works
        reachable = alive_n > 0
        if not reachable and m["ip"]:
            # quick TCP probe common ports on that host
            for probe_p in (22, 7777, 3000, 11434):
                if probe_port(m["ip"], probe_p, timeout=0.4):
                    reachable = True
                    break
        machines.append(
            {
                **m,
                "reachable": reachable,
                "alive_ports": alive_n,
                "port_count": len(mine),
            }
        )

    down = [
        {"port": int(p), **info}
        for p, info in (ports.get("ports") or {}).items()
        if not info.get("alive")
    ]
    return {
        "machines": machines,
        "alert_count": len(down),
        "down_ports": down[:20],
        "projects": infra.get("projects") or [],
        "infra_path": infra.get("infra_path"),
        "generated_at": _now_iso(),
    }


def local_resources() -> dict:
    load1 = load5 = load15 = None
    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        pass

    mem = {}
    try:
        # macOS: vm_stat
        out = subprocess.check_output(["vm_stat"], text=True, timeout=3)
        page = 4096
        m = re.search(r"page size of (\d+)", out)
        if m:
            page = int(m.group(1))
        free = inactive = wired = active = 0
        for line in out.splitlines():
            if "Pages free" in line:
                free = int(re.sub(r"\D", "", line.split(":")[-1]) or 0)
            elif "Pages inactive" in line:
                inactive = int(re.sub(r"\D", "", line.split(":")[-1]) or 0)
            elif "Pages wired" in line:
                wired = int(re.sub(r"\D", "", line.split(":")[-1]) or 0)
            elif "Pages active" in line:
                active = int(re.sub(r"\D", "", line.split(":")[-1]) or 0)
        total_pages = free + inactive + wired + active
        used = (wired + active) * page
        total = total_pages * page if total_pages else None
        mem = {
            "used_bytes": used,
            "total_bytes": total,
            "used_pct": round(100.0 * used / total, 1) if total else None,
        }
    except Exception:
        mem = {"error": "vm_stat unavailable"}

    disk = {}
    try:
        usage = shutil.disk_usage(str(Path.home()))
        disk = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_pct": round(100.0 * usage.used / usage.total, 1),
        }
    except Exception as e:
        disk = {"error": str(e)}

    return {
        "host": socket.gethostname(),
        "load": {"1": load1, "5": load5, "15": load15},
        "memory": mem,
        "disk": disk,
        "generated_at": _now_iso(),
    }


def _git(ws: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(ws), *args],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return 1, str(e)


def workspace_summaries(workspaces: dict[str, str]) -> list[dict]:
    rows = []
    for ws_id, path in workspaces.items():
        if str(ws_id).startswith("."):
            continue
        root = Path(path).expanduser()
        row: dict[str, Any] = {
            "id": ws_id,
            "path": str(root),
            "exists": root.is_dir(),
        }
        if not root.is_dir():
            rows.append(row)
            continue
        rc, branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
        row["branch"] = branch if rc == 0 else None
        rc, status = _git(root, "status", "--porcelain")
        dirty_lines = [ln for ln in status.splitlines() if ln.strip()] if rc == 0 else []
        row["dirty"] = len(dirty_lines)
        row["dirty_sample"] = dirty_lines[:12]
        rc, ab = _git(root, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
        ahead = behind = 0
        if rc == 0 and ab:
            parts = ab.split()
            if len(parts) >= 2:
                behind, ahead = int(parts[0] or 0), int(parts[1] or 0)
        row["ahead"] = ahead
        row["behind"] = behind
        rows.append(row)
    return rows


def list_daily_reviews(workspaces: dict[str, str], limit: int = 20) -> dict:
    reports: list[dict] = []
    for ws_id, path in workspaces.items():
        root = Path(path).expanduser()
        rdir = root / ".ccc" / "reports"
        if not rdir.is_dir():
            continue
        for p in sorted(rdir.glob("daily-review-*.md"), reverse=True):
            reports.append(
                {
                    "workspace": ws_id,
                    "path": str(p),
                    "name": p.name,
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat(
                        timespec="seconds"
                    ),
                    "size": p.stat().st_size,
                }
            )
    reports.sort(key=lambda r: r.get("mtime") or "", reverse=True)
    latest = reports[0] if reports else None
    latest_body = None
    if latest:
        try:
            latest_body = Path(latest["path"]).read_text(encoding="utf-8")[:12000]
        except OSError:
            latest_body = None
    return {
        "reports": reports[:limit],
        "latest": latest,
        "latest_body": latest_body,
        "generated_at": _now_iso(),
    }


def run_daily_review(
    workspace_path: Path,
    *,
    apply: bool = False,
    debounce_s: float = 15.0,
) -> dict:
    key = str(workspace_path.resolve())
    with _RUN_LOCK:
        last = _RUN_DEBOUNCE.get(key, 0)
        now = time.time()
        if now - last < debounce_s:
            return {
                "ok": False,
                "error": "debounced",
                "retry_after_s": round(debounce_s - (now - last), 1),
            }
        _RUN_DEBOUNCE[key] = now

    script = SCRIPTS / "ccc-daily-diff-review.py"
    cmd = ["python3", str(script), "--workspace", str(workspace_path)]
    if apply:
        cmd.append("--apply")
    else:
        cmd.append("--dry-run")
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(SCRIPTS),
            env={**os.environ, "PYTHONPATH": str(SCRIPTS)},
        )
        out = (r.stdout or "").strip()
        try:
            payload = json.loads(out) if out.startswith("{") else {"raw": out}
        except json.JSONDecodeError:
            payload = {"raw": out[-4000:]}
        return {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "result": payload,
            "stderr": (r.stderr or "")[-2000:],
            "apply": apply,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "apply": apply}


def kb_health() -> dict:
    targets = [
        {"name": "HP Proxy", "port": 8080, "url": "http://127.0.0.1:8080/"},
        {"name": "HP Memory Store", "port": 8082, "url": "http://127.0.0.1:8082/"},
        {"name": "HP Bridge", "port": 8083, "url": "http://127.0.0.1:8083/"},
    ]
    services = []
    for t in targets:
        alive = probe_port("127.0.0.1", t["port"])
        http_ok, status, label = (False, 0, "down")
        if alive:
            http_ok, status, label = probe_http("127.0.0.1", t["port"])
        services.append(
            {
                **t,
                "alive": alive or http_ok,
                "http_status": status,
                "label": label,
                "deep_link": t["url"],
            }
        )
    return {
        "services": services,
        "ok": all(s["alive"] for s in services),
        "generated_at": _now_iso(),
        "note": "HP 业务 UI 不嵌在 Hub；仅探活 + 深链",
    }


def deploy_targets() -> dict:
    """Read-only deploy perspective for Mac2017 / feiniu."""
    infra = parse_infra()
    by_name = {m["name"]: m for m in infra.get("machines") or []}
    targets = []
    for name, meta in (
        (
            "Mac 2017",
            {
                "role": "CCC Server",
                "checks": [
                    (7777, "Hub"),
                    (4000, "router-anthropic"),
                    (4002, "router-openai"),
                    (22, "ssh"),
                ],
                "notes": "唯一生产：Hub/Board/Engine/中转/业务仓（见 docs/deploy/topology.md）",
            },
        ),
        (
            "feiniu",
            {
                "role": "业务生产",
                "checks": [(3000, "medio-0"), (11434, "ollama"), (18080, "Money Printer")],
                "notes": "HP/medio 等业务机；非 CCC 控制面",
            },
        ),
    ):
        m = by_name.get(name) or {}
        ip = m.get("ip")
        checks = []
        for port, label in meta["checks"]:
            if port is None or not ip:
                continue
            ok = probe_port(ip, port, timeout=0.5)
            checks.append({"port": port, "label": label, "alive": ok})
        reachable = any(c["alive"] for c in checks) if checks else False
        if not reachable and ip:
            reachable = probe_port(ip, 22, timeout=0.4)
        targets.append(
            {
                "name": name,
                "ip": ip,
                "role": meta["role"],
                "reachable": reachable,
                "checks": checks,
                "notes": meta["notes"],
                "readonly": True,
            }
        )
    m1 = by_name.get("M1") or {}
    return {
        "dev": {
            "name": "M1",
            "ip": m1.get("ip"),
            "role": "Client / 对话面",
            "notes": "Desktop + sidecar；Hub/Engine 在 Mac 2017，不在本机",
        },
        "targets": targets,
        "generated_at": _now_iso(),
    }


def _patrol_alert_item(a: Any) -> dict | None:
    if isinstance(a, dict):
        return {
            "source": "patrol",
            "severity": a.get("severity") or a.get("level") or "warn",
            "title": a.get("title") or a.get("message") or str(a)[:120],
            "detail": a.get("detail") or a.get("reason") or "",
        }
    if isinstance(a, str) and a.strip():
        return {
            "source": "patrol",
            "severity": "warn",
            "title": a.strip()[:120],
            "detail": "",
        }
    return None


def _patrol_alerts() -> list[dict]:
    """Parse ~/.ccc/patrol-state.json — dict 或 list（历史轮次）均可。"""
    if not PATROL_STATE.is_file():
        return []
    try:
        state = json.loads(PATROL_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    alerts: list[dict] = []

    # Shape A: list of rounds [{ts, boards: {ws: {ab: N, ...}}, alerts?: []}, ...]
    if isinstance(state, list):
        last = state[-1] if state else None
        if isinstance(last, dict):
            for a in last.get("alerts") or last.get("issues") or []:
                item = _patrol_alert_item(a)
                if item:
                    alerts.append(item)
            boards = last.get("boards") or {}
            if isinstance(boards, dict):
                for ws, counts in boards.items():
                    if not isinstance(counts, dict):
                        continue
                    ab = int(counts.get("ab") or counts.get("abnormal") or 0)
                    if ab > 0:
                        alerts.append(
                            {
                                "source": "patrol",
                                "severity": "medium",
                                "title": f"patrol: {ws} 有 {ab} 个异常列任务",
                                "detail": f"ts={last.get('ts') or ''}",
                            }
                        )
        return alerts[:20]

    if not isinstance(state, dict):
        return []

    # Shape B: dict with alerts / rounds / history
    for key in ("alerts", "last_alerts", "issues"):
        raw = state.get(key)
        if isinstance(raw, list):
            for a in raw[:30]:
                item = _patrol_alert_item(a)
                if item:
                    alerts.append(item)
    rounds = state.get("rounds") or state.get("history")
    if isinstance(rounds, list) and rounds and not alerts:
        last = rounds[-1]
        if isinstance(last, dict):
            for a in last.get("alerts") or last.get("issues") or []:
                item = _patrol_alert_item(a)
                if item:
                    alerts.append(item)
    return alerts[:20]


def collect_risks(
    workspaces: dict[str, str],
    *,
    board_abnormal: list[dict] | None = None,
    engine_running: bool | None = None,
    control_mode: str | None = None,
) -> dict:
    risks: list[dict] = []

    if engine_running is False:
        risks.append(
            {
                "id": "engine-down",
                "severity": "high",
                "source": "engine",
                "title": "Engine 未运行",
                "detail": "控制台/运维可启动 Engine",
            }
        )
    if control_mode and control_mode not in ("enabled",):
        risks.append(
            {
                "id": "control-mode",
                "severity": "medium",
                "source": "control",
                "title": f"控制面 mode={control_mode}",
                "detail": "Engine 仅在 enabled 下消费队列",
            }
        )

    for t in board_abnormal or []:
        risks.append(
            {
                "id": f"abn-{(t.get('id') or '')[:40]}",
                "severity": "high",
                "source": "board",
                "title": f"异常任务: {t.get('title') or t.get('id')}",
                "detail": t.get("human_reason") or t.get("reason") or "",
                "workspace": t.get("workspace"),
            }
        )

    for ws_id, path in workspaces.items():
        root = Path(path).expanduser()
        if not root.is_dir():
            continue
        rc, status = _git(root, "status", "--porcelain")
        if rc != 0:
            continue
        dirty = [ln for ln in status.splitlines() if ln.strip()]
        if len(dirty) >= 30:
            risks.append(
                {
                    "id": f"dirty-{ws_id}",
                    "severity": "medium",
                    "source": "git",
                    "title": f"{ws_id} 脏树过大 ({len(dirty)} files)",
                    "detail": "建议提交或清理后再跑日审",
                    "workspace": ws_id,
                }
            )

    # latest daily-review security decision D
    reviews = list_daily_reviews(workspaces, limit=5)
    body = reviews.get("latest_body") or ""
    if "decision: **D**" in body or "decision: D" in body or "possible secret" in body.lower():
        risks.append(
            {
                "id": "daily-D",
                "severity": "high",
                "source": "daily-review",
                "title": "日审安全类决策 D",
                "detail": "仅告警，不自动建开发卡",
            }
        )

    risks.extend(_patrol_alerts())

    # down ports
    ports = probe_ports()
    critical = {7775, 7777, 4000}
    for p, info in (ports.get("ports") or {}).items():
        try:
            pi = int(p)
        except ValueError:
            continue
        if pi in critical and not info.get("alive"):
            risks.append(
                {
                    "id": f"port-{pi}",
                    "severity": "high",
                    "source": "ports",
                    "title": f"关键端口 {pi} 未响应 ({info.get('name')})",
                    "detail": info.get("label") or "",
                }
            )

    sev_rank = {"high": 0, "medium": 1, "low": 2, "warn": 1, "info": 3}
    risks.sort(key=lambda r: sev_rank.get(str(r.get("severity")), 9))
    return {
        "count": len(risks),
        "high": sum(1 for r in risks if r.get("severity") == "high"),
        "risks": risks,
        "generated_at": _now_iso(),
    }


def list_ops_auto_tasks(workspaces: dict[str, str]) -> list[dict]:
    """Backlog cards tagged ops-auto / daily-review."""
    out = []
    try:
        from _board_store import FileBoardStore
    except ImportError:
        return out
    for ws_id, path in workspaces.items():
        root = Path(path).expanduser()
        if not root.is_dir():
            continue
        try:
            store = FileBoardStore(root)
            for t in store.list_tasks("backlog"):
                tags = t.get("tags") or []
                if not isinstance(tags, list):
                    tags = []
                tag_s = [str(x) for x in tags]
                if "ops-auto" in tag_s or "daily-review" in tag_s:
                    out.append(
                        {
                            **{k: t.get(k) for k in ("id", "title", "description", "created_at", "tags")},
                            "workspace": ws_id,
                            "origin": "ops-auto"
                            if "ops-auto" in tag_s
                            else "daily-review",
                        }
                    )
        except Exception:
            continue
    out.sort(key=lambda t: t.get("created_at") or "", reverse=True)
    return out


def docs_debt_scan(workspaces: dict[str, str]) -> dict:
    """Lightweight docs debt hints (Phase 3/5)."""
    findings: list[dict] = []
    infra = parse_infra()
    ports_live = probe_ports(infra)
    # infrastructure drift: ports in md that are down (hint only)
    for p, info in (ports_live.get("ports") or {}).items():
        if not info.get("alive") and info.get("machine") == "M1":
            findings.append(
                {
                    "severity": "low",
                    "kind": "infra-drift",
                    "title": f"infrastructure 登记端口 {p} 当前未响应",
                    "path": infra.get("infra_path"),
                    "suggestion": "核对服务是否应启动，或更新 .ccc/infrastructure.md",
                }
            )

    for ws_id, path in workspaces.items():
        root = Path(path).expanduser()
        if not root.is_dir():
            continue
        readme = root / "README.md"
        agents = root / "AGENTS.md"
        changelog = root / "CHANGELOG.md"
        if not readme.is_file():
            findings.append(
                {
                    "severity": "medium",
                    "kind": "missing-readme",
                    "workspace": ws_id,
                    "title": f"{ws_id} 缺少 README.md",
                    "suggestion": "补充项目说明",
                }
            )
        if ws_id == "CCC" and not agents.is_file():
            # AGENTS optional
            pass
        if changelog.is_file():
            # stale if older than 30 days and there are recent tags
            age_days = (time.time() - changelog.stat().st_mtime) / 86400
            rc, tags = _git(root, "tag", "--sort=-creatordate")
            if rc == 0 and tags and age_days > 30:
                findings.append(
                    {
                        "severity": "low",
                        "kind": "changelog-stale",
                        "workspace": ws_id,
                        "title": f"{ws_id} CHANGELOG 超过 30 天未更新",
                        "suggestion": f"最近 tag: {tags.splitlines()[0] if tags else '?'}",
                    }
                )

    return {
        "findings": findings[:40],
        "count": len(findings),
        "generated_at": _now_iso(),
    }


def quality_summary(workspaces: dict[str, str]) -> dict:
    """Phase 5: light daily quality digest from recent commits + released sample."""
    digests = []
    for ws_id, path in list(workspaces.items())[:8]:
        root = Path(path).expanduser()
        if not root.is_dir():
            continue
        rc, log = _git(root, "log", "--since=24 hours", "--oneline", "-n", "15")
        commits = log.splitlines() if rc == 0 and log else []
        released_n = 0
        try:
            from _board_store import FileBoardStore

            store = FileBoardStore(root)
            released_n = len(store.list_tasks("released"))
        except Exception:
            pass
        digests.append(
            {
                "workspace": ws_id,
                "commits_24h": len(commits),
                "commit_sample": commits[:8],
                "released_total": released_n,
                "hint": "抽样；完整回归走 regress 角色",
            }
        )
    return {
        "workspaces": digests,
        "generated_at": _now_iso(),
        "note": "质量日审摘要（轻量）；深度测试由 regress/tester 负责",
    }


def adopt_suggestion(
    workspace_path: Path,
    *,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
) -> dict:
    """Create backlog card from ops suggestion (ops-auto). Not invent."""
    from board.context import set_workspace
    from _board_store import FileBoardStore

    set_workspace(workspace_path)
    store = FileBoardStore(workspace_path)
    tid = f"ops-adopt-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    tag_list = list(tags or [])
    if "ops-auto" not in tag_list:
        tag_list.append("ops-auto")
    if "adopted" not in tag_list:
        tag_list.append("adopted")
    task = {
        "id": tid,
        "title": (title or tid)[:200],
        "description": description or "",
        "status": "backlog",
        "card_kind": "epic",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "schema_version": "1.2",
        "complexity": "medium",
        "tags": tag_list,
    }
    ok = store.create_task(task, column="backlog")
    wake = None
    if ok:
        try:
            from _engine_wake import ensure_engine_for_task

            wake = ensure_engine_for_task(reason="ops_adopt", task_id=tid)
        except Exception as e:
            wake = {"error": str(e)}
    return {"ok": ok, "task_id": tid, "engine_wake": wake, "tags": tag_list}
