#!/usr/bin/env python3
"""CCC Hub Ops probes — 只读聚合（infrastructure / ports / resources / git / risks）。

供 chat_server/routers/ops.py 与日审调度复用。禁止复活 cluster-bus。
"""

from __future__ import annotations

import dataclasses
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

from _logger import get_logger

_log = get_logger("ops_probe")

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
    # CCC Relay 2026-07-25:中转站回归(:4000 anthropic/:4002 openai-chat),纳入 CCC 端口组健康探针
    ("CCC", (4000, 4002, 7775, 7777, 7778)),
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


def _empty_router_tiers() -> dict[str, dict[str, int]]:
    # CCC Relay 2026-07-25:三档契约 flash/Pro/code(大写 P)
    return {
        "flash": {"requests_today": 0, "tokens_today": 0},
        "Pro": {"requests_today": 0, "tokens_today": 0},
        "code": {"requests_today": 0, "tokens_today": 0},
    }


def fetch_router_usage(
    *,
    host: str = "127.0.0.1",
    port: int = 4000,
    timeout: float = 2.5,
    use_cache: bool = True,
) -> dict:
    """CCC Relay:真拉 relay :4000/admin/stats（含 healthy/upstreams）,30s 缓存。

    旧 /admin/usage 只有 by_tier.n/tk，Desktop 运维会显示全 0；改读 /admin/stats。
    返回三档键统一为 flash / Pro / code（relay 内部 pro 小写映射到 Pro）。
    """
    cache_key = ("router_usage", host, port)
    now = time.monotonic()
    if use_cache and cache_key in _CACHE:
        ts, val = _CACHE[cache_key]
        if (now - ts) < 30.0:
            return val
    url = f"http://{host}:{port}/admin/stats"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        tiers_in = (payload or {}).get("tiers") or {}
        tiers_out: dict[str, dict[str, int]] = {}
        for display, aliases in (
            ("flash", ("flash",)),
            ("Pro", ("Pro", "pro")),
            ("code", ("code",)),
        ):
            td: dict = {}
            for a in aliases:
                if a in tiers_in:
                    td = tiers_in.get(a) or {}
                    break
            tiers_out[display] = {
                "requests_today": int(td.get("requests_today") or 0),
                "tokens_today": int(td.get("tokens_today") or 0),
                "upstreams": int(td.get("upstreams") or 0),
                "healthy": int(td.get("healthy") or 0),
            }
        total_in = (payload or {}).get("total") or {}
        result = {
            "ok": True,
            "tiers": tiers_out,
            "total": {
                "upstreams": int(total_in.get("upstreams") or 0),
                "healthy": int(total_in.get("healthy") or 0),
                "requests_today": int(total_in.get("requests_today") or 0),
                "tokens_today": int(total_in.get("tokens_today") or 0),
            },
            "source": "relay",
            "host": host,
            "port": port,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "tiers": _empty_router_tiers(),
            "requested": _empty_router_tiers(),
            "attribution": None,
            "source": "relay_down",
            "error": f"relay {host}:{port} unreachable: {exc!r}"[:200],
            "host": host,
            "port": port,
        }
    _CACHE[cache_key] = (now, result)
    return result


# ── Phase 1: per-upstream 日统计 ────────────────────────────────
# 2026-07-26 从 relay persistent usage.json 计算每上游今日统计。
# 数据源: ~/.ccc/relay/usage.json(relay 每 60s 落盘;保留最近 100k 条)。
# 不通过 relay admin API(admin 不暴露 per-upstream latency/success)。

_RELAY_USAGE_DIR = str(Path.home() / ".ccc" / "relay")


def _today_start_ts() -> int:
    """今天 00:00 UTC 的时间戳(毫秒)。"""
    from datetime import datetime, timezone
    return int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)


def _load_usage_file(path: str | None = None) -> list[dict]:
    """从 usage.json 加载原始请求记录。"""
    fp = path or os.path.join(_RELAY_USAGE_DIR, "usage.json")
    if not os.path.isfile(fp):
        return []
    try:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _today_records(records: list[dict]) -> list[dict]:
    """筛选今日记录。"""
    ts = _today_start_ts()
    return [r for r in records if r.get("timestamp", 0) >= ts]


def fetch_router_upstream_daily(
    *,
    host: str = "127.0.0.1",
    port: int = 4000,
    timeout: float = 2.5,
    use_cache: bool = True,
    usage_path: str | None = None,
) -> dict:
    """CCC Relay 2026-07-26:每上游今日调用量+token。

    从 relay /admin/usage?period=1d 取 by_upstream(调用数+token)，
    再读本地 usage.json 补充每上游成功率+平均延迟+今日成本。

    返回结构:
    {
        "ok": true,
        "upstreams": [
            {
                "name": "opencode-go",
                "tier": "flash",
                "requests_today": 12,
                "tokens_today": 15600,
                "success_rate": 1.0,
                "avg_latency_ms": 2850,
                "cost_usd": 0.007,
            },
            ...
        ],
        "tier_totals": {"flash": {"requests": 12, "tokens": 15600}},
        "total_requests": 12,
        "total_tokens": 15600,
        "total_cost": 0.007,
    }
    """
    cache_key = ("upstream_daily", host, port)
    now = time.monotonic()
    if use_cache and cache_key in _CACHE:
        ts, val = _CACHE.get(cache_key, (0, None))
        if val is not None and (now - ts) < 30.0:
            return val

    # 1) 从 relay admin API 拿 by_upstream + tiers
    url = f"http://{host}:{port}/admin/usage?period=1d"
    usage_relay = None
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            usage_relay = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        pass

    by_upstream_api: dict[str, dict] = {}
    tier_map: dict[str, str] = {}
    if usage_relay and usage_relay.get("by_upstream"):
        by_upstream_api = usage_relay["by_upstream"]
        # Build tier_map 从 relay upstreams
        try:
            up_url = f"http://{host}:{port}/admin/upstreams"
            with urllib.request.urlopen(up_url, timeout=timeout) as resp:
                upstreams = json.loads(resp.read().decode("utf-8", errors="replace"))
            if isinstance(upstreams, list):
                for u in upstreams:
                    if isinstance(u, dict) and u.get("name"):
                        tier_map[u["name"]] = u.get("tier", "unknown")
        except Exception:
            pass

    # 2) 从本地 usage.json 补成功率+延迟
    records = _load_usage_file(usage_path)
    today = _today_records(records)

    # 聚合 per-upstream 今日统计
    today_by_up: dict[str, dict] = {}
    for r in today:
        name = r.get("upstream", "unknown")
        if name not in today_by_up:
            today_by_up[name] = {
                "n": 0, "tokens": 0, "fail": 0, "latency_sum": 0, "latency_count": 0,
            }
        d = today_by_up[name]
        d["n"] += 1
        d["tokens"] += r.get("total_tokens", 0) or 0
        if not r.get("success"):
            d["fail"] += 1
        lat = r.get("latency_ms")
        if isinstance(lat, (int, float)) and lat > 0:
            d["latency_sum"] += lat
            d["latency_count"] += 1

    # 3) 合并两个来源
    all_names = set(by_upstream_api.keys()) | set(today_by_up.keys())
    upstreams_out = []
    for name in sorted(all_names):
        raw = by_upstream_api.get(name, {})
        hist = today_by_up.get(name, {})
        n = raw.get("n", 0) or hist.get("n", 0)
        tokens = raw.get("tk", 0) or hist.get("tokens", 0)
        fail = hist.get("fail", 0)
        success_rate = 1.0 - (fail / max(n, 1))
        avg_lat = round(hist["latency_sum"] / max(hist["latency_count"], 1), 1) if hist.get("latency_count") else None
        upstreams_out.append({
            "name": name,
            "tier": tier_map.get(name, "unknown"),
            "requests_today": n,
            "tokens_today": tokens,
            "success_rate": round(success_rate, 4),
            "avg_latency_ms": avg_lat,
        })

    # tier 聚合
    tier_totals: dict[str, dict] = {}
    for u in upstreams_out:
        t = u["tier"]
        if t not in tier_totals:
            tier_totals[t] = {"requests": 0, "tokens": 0}
        tier_totals[t]["requests"] += u["requests_today"]
        tier_totals[t]["tokens"] += u["tokens_today"]

    result = {
        "ok": True,
        "upstreams": upstreams_out,
        "tier_totals": tier_totals,
        "total_requests": sum(u["requests_today"] for u in upstreams_out),
        "total_tokens": sum(u["tokens_today"] for u in upstreams_out),
    }
    _CACHE[cache_key] = (now, result)
    return result


def fetch_router_upstream_trend(
    *,
    host: str = "127.0.0.1",
    port: int = 4000,
    days: int = 7,
    timeout: float = 2.5,
    use_cache: bool = True,
) -> dict:
    """CCC Relay 2026-07-26:近 N 天每上游每日趋势。

    从 relay /admin/usage?period={days}d 拿 trend(日 token 总量)
    和 by_upstream 的每日调用明细。
    """
    cache_key = ("upstream_trend", host, port, days)
    now = time.monotonic()
    if use_cache and cache_key in _CACHE:
        ts, val = _CACHE.get(cache_key, (0, None))
        if val is not None and (now - ts) < 60.0:
            return val

    url = f"http://{host}:{port}/admin/usage?period={days}d"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        trend = (payload or {}).get("trend", [])
        # trend 结构: [{date: "2026-07-25", tokens: N}, ...]
        by_upstream = (payload or {}).get("by_upstream", {})
        total = (payload or {}).get("total", 0)
        result = {
            "ok": True,
            "period_days": days,
            "trend": trend,
            "total_requests": total,
            "by_upstream": by_upstream,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "error": f"relay trend fetch failed: {exc!r}"[:200],
        }
    _CACHE[cache_key] = (now, result)
    return result


# ── Phase 3: 成本估算 ─────────────────────────────────────────
# 2026-07-26 根据 token 量和模型单价估算每日消耗。
# 成本目录 ~/.ccc/cost-catalog.json（可覆盖），默认价参考 _cost_telemetry._COST_MAP。
# 由于 usage.json 只有 total_tokens（无 prompt/completion 拆分），使用 blended $/M tokens。


@dataclasses.dataclass
class CostCatalog:
    """每上游 $/M tokens（blended rate，假设 prompt:completion ≈ 3:1）。"""

    # upstream 名称前缀 → blended $/M tokens
    rates: dict[str, float] = dataclasses.field(default_factory=lambda: {
        "opencode-go-paid": 6.0,     # claude-sonnet
        "opencode-go": 0.26,         # deepseek-v4（含 -b ~ -g 副本）
        "xfyun-code": 0.42,          # xfyun-code
        "zhipu-glm4": 0.0,           # 免费
        "minimax-m3": 0.88,          # minimax-m3
        "gemini-flash": 0.18,        # gemini-flash
        "claude-haiku": 0.50,        # haiku
        "claude-sonnet": 6.0,        # sonnet
        "default": 0.30,             # fallback
    })

    @classmethod
    def load(cls, path: str | None = None) -> "CostCatalog":
        """从 ~/.ccc/cost-catalog.json 加载，不存在则用默认值。"""
        fp = path or os.path.join(str(Path.home()), ".ccc", "cost-catalog.json")
        if not os.path.isfile(fp):
            return cls()
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "rates" in data:
                return cls(rates={**cls().rates, **data["rates"]})
            return cls()
        except (OSError, json.JSONDecodeError):
            return cls()

    def rate_for(self, upstream_name: str) -> float:
        """根据 upstream 名称前缀查找 blended $/M tokens。"""
        name = upstream_name.lower()
        # 精确匹配优先
        for prefix, rate in sorted(self.rates.items(), key=lambda x: -len(x[0])):
            if prefix == "default":
                continue
            if name.startswith(prefix) or name == prefix:
                return rate
        return self.rates.get("default", 0.30)


_COST_CATALOG_CACHE: CostCatalog | None = None
_COST_CATALOG_MTIME: float = 0


def _get_cost_catalog() -> CostCatalog:
    """带 mtime 缓存的 CostCatalog 加载。"""
    global _COST_CATALOG_CACHE, _COST_CATALOG_MTIME
    fp = os.path.join(str(Path.home()), ".ccc", "cost-catalog.json")
    try:
        mtime = os.path.getmtime(fp) if os.path.isfile(fp) else 0
    except OSError:
        mtime = 0
    if _COST_CATALOG_CACHE is None or mtime != _COST_CATALOG_MTIME:
        _COST_CATALOG_CACHE = CostCatalog.load()
        _COST_CATALOG_MTIME = mtime
    return _COST_CATALOG_CACHE


def enrich_upstream_cost(
    upstreams: list[dict],
    usage_records: list[dict] | None = None,
) -> list[dict]:
    """给每上游添加 cost_usd 字段。

    Args:
        upstreams: fetch_router_upstream_daily() 返回的 upstreams 列表。
        usage_records: _today_records(_load_usage_file()) 的原始记录（可选，精确计算用）。

    返回:
        增加了 cost_usd 字段的 upstreams 列表（就地修改并返回）。
    """
    catalog = _get_cost_catalog()

    # 如果有原始记录，从记录逐条求和（更精确）
    if usage_records:
        cost_by_upstream: dict[str, float] = {}
        for r in usage_records:
            name = r.get("upstream", "unknown")
            rate = catalog.rate_for(name)
            tokens = r.get("total_tokens", 0) or 0
            cost_by_upstream[name] = cost_by_upstream.get(name, 0.0) + tokens * rate / 1_000_000

    for u in upstreams:
        name = u.get("name", "unknown")
        tokens = u.get("tokens_today", 0) or 0

        if usage_records:
            cost = round(cost_by_upstream.get(name, 0.0), 6)
        else:
            rate = catalog.rate_for(name)
            cost = round(tokens * rate / 1_000_000, 6)

        u["cost_usd"] = cost

    return upstreams


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
                    "ok": True,  # Desktop / envelope contract (alive alias)
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
                "ok": True,
                "http_status": status if http_ok else 0,
                "label": label if http_ok else "TCP open",
                "probed_host": probed,
            }
        return port, {
            **info,
            "alive": False,
            "ok": False,
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
    except OSError as e:
        _log.debug("ops_probe getloadavg: %s", e)

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

    load_ratio = (
        round(float(load1) / _ncpu_safe(), 3) if load1 is not None else None
    )
    mem_pct = mem.get("used_pct") if isinstance(mem, dict) else None
    disk_pct = disk.get("used_pct") if isinstance(disk, dict) else None
    return {
        "host": socket.gethostname(),
        "ncpu": _ncpu_safe(),
        "load": {"1": load1, "5": load5, "15": load15},
        "load_ratio": load_ratio,
        # Desktop OpsResourcesResp: cpu=0..1 ratio; mem/disk as percent 0..100
        "cpu": load_ratio,
        "mem_pct": mem_pct,
        "disk_pct": disk_pct,
        "memory": mem,
        "disk": disk,
        "generated_at": _now_iso(),
    }


def _ncpu_safe() -> int:
    try:
        return int(os.cpu_count() or 1)
    except Exception:
        return 1


def host_resources_history(n: int = 120) -> dict:
    """Time series + headroom for Ops / parallelism decisions."""
    try:
        from _host_resources import read_recent, summarize, sparkline, HOST_RESOURCES_PATH
    except ImportError:
        return {"error": "host_resources module missing", "samples": []}
    rows = read_recent(n)
    loads = []
    mems = []
    for r in rows:
        lr = r.get("load_ratio")
        if lr is None:
            load1 = (r.get("load") or {}).get("1")
            cpus = r.get("ncpu") or 1
            lr = (float(load1) / float(cpus)) if load1 is not None else None
        loads.append(lr)
        mems.append((r.get("memory") or {}).get("used_pct"))
    return {
        "path": str(HOST_RESOURCES_PATH),
        "samples": rows,
        "sparklines": {
            "load_ratio": sparkline(loads),
            "mem_pct": sparkline(mems),
        },
        "summary": summarize(rows),
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
    """Per-ws git + active board column counts (Desktop Ops chips)."""
    from _board_visibility import is_active_board_task, load_task_head

    rows = []
    for ws_id, path in workspaces.items():
        if str(ws_id).startswith("."):
            continue
        root = Path(path).expanduser()
        row: dict[str, Any] = {
            "id": ws_id,
            "workspace": ws_id,  # Desktop OpsWorkspaceSummary.workspace
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

        board = root / ".ccc" / "board"
        counts = {
            "backlog": 0,
            "planned": 0,
            "in_progress": 0,
            "testing": 0,
            "verified": 0,
            "released": 0,
            "abnormal": 0,
        }
        epic_count = 0
        last_event = None
        if board.is_dir():
            for col in counts:
                d = board / col
                if not d.is_dir():
                    continue
                for p in d.glob("*.jsonl"):
                    data = load_task_head(p)
                    if not is_active_board_task(data):
                        # still count released/verified for fleet chips
                        if col not in ("released", "verified"):
                            continue
                    counts[col] = counts.get(col, 0) + 1
                    if data and str(data.get("card_kind") or "") == "epic":
                        epic_count += 1
            ev_dir = board / "events"
            if ev_dir.is_dir():
                newest = None
                newest_mtime = 0.0
                for p in ev_dir.glob("*.jsonl"):
                    try:
                        mt = p.stat().st_mtime
                    except OSError:
                        continue
                    if mt > newest_mtime:
                        newest_mtime = mt
                        newest = p
                if newest is not None:
                    try:
                        lines = newest.read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                        if lines:
                            last_event = lines[-1][:160]
                    except OSError as e:
                        _log.debug("ops_probe events tail read: %s", e)
        row.update(counts)
        row["epic_count"] = epic_count
        row["last_event"] = last_event
        rows.append(row)
    return rows


def control_runtime_snapshot() -> dict[str, Any]:
    """Control plane + Engine for Ops status strip / ready_to_dispatch."""
    out: dict[str, Any] = {
        "mode": None,
        "invent_hard_disabled": True,
        "engine_running": None,
        "hub_port_7777": None,
        "generated_at": _now_iso(),
    }
    try:
        from _ccc_control import INVENT_HARD_DISABLED, get_mode, status_dict

        out["mode"] = get_mode()
        out["invent_hard_disabled"] = bool(INVENT_HARD_DISABLED)
        try:
            st = status_dict()
            if isinstance(st, dict):
                out["control"] = {
                    k: st.get(k)
                    for k in (
                        "mode",
                        "invent_hard_disabled",
                        "queue_consumer_only",
                        "engine_allowed",
                        "updated_at",
                    )
                }
        except Exception as e:
            _log.debug("ops_probe control_policy inner: %s", e)
    except Exception as exc:
        out["control_error"] = str(exc)[:120]
    try:
        from _engine_wake import is_engine_running

        out["engine_running"] = bool(is_engine_running())
    except Exception as exc:
        out["engine_error"] = str(exc)[:120]
    # Hub listens on 7777 on this host (tunnel is M1-side; Desktop infers via fetch OK)
    try:
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.4)
        try:
            out["hub_port_7777"] = s.connect_ex(("127.0.0.1", 7777)) == 0
        finally:
            s.close()
    except OSError:
        out["hub_port_7777"] = None
    return out


def recent_failures_fleet(
    workspaces: dict[str, str], *, per_ws: int = 5, limit: int = 30
) -> list[dict[str, Any]]:
    """Tail failures.jsonl across apps for Ops (no Console hop)."""
    from _failure_ledger import read_failures

    rows: list[dict[str, Any]] = []
    for ws_id, path in workspaces.items():
        if str(ws_id).startswith("."):
            continue
        root = Path(path).expanduser()
        if not root.is_dir():
            continue
        try:
            for fr in read_failures(root, last=per_ws):
                item = dict(fr) if isinstance(fr, dict) else {}
                item["workspace"] = ws_id
                rows.append(item)
        except Exception:
            continue
    rows.sort(key=lambda r: str(r.get("ts") or r.get("at") or ""), reverse=True)
    return rows[:limit]


def abnormal_cards_fleet(
    workspaces: dict[str, str], *, limit: int = 40
) -> list[dict[str, Any]]:
    """Active abnormal cards for Ops reopen list."""
    from _board_visibility import is_active_board_task, load_task_head

    rows: list[dict[str, Any]] = []
    for ws_id, path in workspaces.items():
        if str(ws_id).startswith("."):
            continue
        root = Path(path).expanduser()
        abn = root / ".ccc" / "board" / "abnormal"
        if not abn.is_dir():
            continue
        for p in sorted(abn.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
            data = load_task_head(p)
            if not is_active_board_task(data):
                continue
            tid = str((data or {}).get("id") or p.stem)
            rows.append(
                {
                    "workspace": ws_id,
                    "id": tid,
                    "task_id": tid,
                    "title": (data or {}).get("title") or tid,
                    "note": str((data or {}).get("note") or "")[:200],
                    "card_kind": (data or {}).get("card_kind"),
                    "parent_id": (data or {}).get("parent_id"),
                    "status": "abnormal",
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def ready_to_dispatch(
    *,
    control: dict[str, Any] | None = None,
    risks: dict[str, Any] | None = None,
    workspaces: list[dict] | None = None,
    resources_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose go/no-go for Desktop Ops (read-only)."""
    ctrl = control or control_runtime_snapshot()
    blockers: list[str] = []
    mode = ctrl.get("mode")
    if ctrl.get("engine_running") is False:
        blockers.append("Engine 未运行")
    if mode and mode != "enabled":
        blockers.append(f"控制面 mode={mode}（须 enabled）")
    if ctrl.get("hub_port_7777") is False:
        blockers.append("本机 Hub :7777 未监听")
    high = int((risks or {}).get("high") or 0)
    if high > 0:
        blockers.append(f"运维红灯 {high}")
    abn = 0
    for w in workspaces or []:
        try:
            abn += int(w.get("abnormal") or 0)
        except (TypeError, ValueError) as e:
            _log.debug("ops_probe abn count parse: %s", e)
    if abn > 0:
        blockers.append(f"舰队 abnormal={abn}")
    summary = (resources_history or {}).get("summary") or {}
    verdict = summary.get("verdict")
    if verdict == "saturated":
        blockers.append("主机 saturated（先治挂死再加任务）")
    ok = len(blockers) == 0
    if ok:
        reason = "可下达：Engine 活、enabled、无红灯、无 abnormal"
    else:
        reason = "暂缓下达：" + "；".join(blockers)
    return {
        "ok": ok,
        "reason": reason,
        "blockers": blockers,
        "invent_hard_disabled": bool(ctrl.get("invent_hard_disabled", True)),
        "mode": mode,
        "engine_running": ctrl.get("engine_running"),
        "resource_verdict": verdict,
        "fleet_abnormal": abn,
        "generated_at": _now_iso(),
    }


_SEVERITY_RANK = {"green": 0, "amber": 1, "red": 2}


def _copy_payload(
    *,
    alert_id: str,
    title: str,
    detail: str,
    source: str,
    impact: str = "暂缓项目开发与下达",
    suggest: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """Agent-facing paste blob for Desktop「复制给 Agent」."""
    lines = [
        "【CCC 运维红灯】请排查并修复（系统/配置问题，不是业务意图）",
        f"标题：{title}",
        f"影响：{impact}",
        f"来源：{source}",
        f"详情：{(detail or '').strip() or '（无）'}",
    ]
    if suggest:
        lines.append(f"建议：{suggest}")
    meta = {"id": alert_id, "source": source}
    if extra:
        meta.update(extra)
    lines.append(f"机器字段：{meta}")
    return "\n".join(lines)


def _alert_suggest(alert_id: str, source: str) -> str:
    sid = (alert_id or "").lower()
    src = (source or "").lower()
    if "engine" in sid or src == "engine":
        return "在 Mac2017 查 com.ccc.engine / `bash scripts/ccc-autostart-guard.sh status`"
    if "7777" in sid or "hub" in sid or src == "hub":
        return "确认 Hub :7777 监听；M1 查 com.ccc.hub-tunnel → 127.0.0.1:17777"
    if "port" in sid or src == "ports":
        return "对照 `.ccc/infrastructure.md` 与 `GET /api/ops/ports`，重启对应 launchd"
    if "patrol" in src or "authority" in sid:
        return "读 `~/.ccc/alerts/` 与 `python3 scripts/ccc-authority-patrol.py`"
    if "saturated" in sid or src == "capacity":
        return "查 OpenCode 残留 / `python3 scripts/ccc-host-resources.py summary`；先 reap 再加并发"
    if "abn-" in sid or src == "board":
        return "经 Hub reopen 或复制本条让 Agent 核账 abnormal；禁重复盲目下达"
    if "daily" in src or sid.startswith("daily"):
        return "读最新 daily-review；安全类 D 只告警不建卡"
    if "control" in sid or src == "control":
        return "控制面须 `enabled`（`bash scripts/ccc-autostart-guard.sh enable --start`）"
    if "mcp" in sid or src == "mcp":
        return "核对 ~/.config/opencode/opencode.json mcp 段与远端 URL；本机 MCP 查 command 是否在 PATH"
    return "按标题与机器字段在 Cursor/对话 Agent 侧排查平台组件"


def _port_ok(info: Any) -> bool | None:
    """Map probe_ports alive→ok for Desktop / envelope (ok preferred)."""
    if not isinstance(info, dict):
        return None
    if "ok" in info and info.get("ok") is not None:
        return bool(info.get("ok"))
    if "alive" in info and info.get("alive") is not None:
        return bool(info.get("alive"))
    return None


def _load_mcp_entries() -> list[dict[str, Any]]:
    """Collect MCP server entries from local OpenCode / Cursor configs."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(name: str, raw: dict[str, Any], *, source: str) -> None:
        key = f"{source}:{name}"
        if key in seen:
            return
        seen.add(key)
        if not isinstance(raw, dict):
            return
        enabled = raw.get("enabled")
        if enabled is False:
            return
        entries.append(
            {
                "name": name,
                "source": source,
                "type": str(raw.get("type") or ("remote" if raw.get("url") else "local")),
                "url": raw.get("url") or raw.get("serverUrl"),
                "command": raw.get("command"),
                "enabled": True if enabled is None else bool(enabled),
            }
        )

    oc = Path.home() / ".config" / "opencode" / "opencode.json"
    if oc.is_file():
        try:
            data = json.loads(oc.read_text(encoding="utf-8"))
            mcp = data.get("mcp") if isinstance(data, dict) else None
            if isinstance(mcp, dict):
                for name, raw in mcp.items():
                    if isinstance(raw, dict):
                        _add(str(name), raw, source="opencode")
        except Exception as e:
            _log.debug("ops_probe load opencode mcp: %s", e)

    cursor_mcp = Path.home() / ".cursor" / "mcp.json"
    if cursor_mcp.is_file():
        try:
            data = json.loads(cursor_mcp.read_text(encoding="utf-8"))
            servers = None
            if isinstance(data, dict):
                servers = data.get("mcpServers") or data.get("mcp")
            if isinstance(servers, dict):
                for name, raw in servers.items():
                    if isinstance(raw, dict):
                        _add(str(name), raw, source="cursor")
        except Exception as e:
            _log.debug("ops_probe load cursor mcp: %s", e)

    return entries


def _probe_mcp_url(url: str, *, timeout: float = 1.5) -> tuple[bool, str]:
    """TCP/HTTP probe for remote MCP URL. 401/404 still count as reachable."""
    u = (url or "").strip()
    if not u:
        return False, "empty url"
    try:
        from urllib.parse import urlparse

        parsed = urlparse(u if "://" in u else f"http://{u}")
        host = parsed.hostname or ""
        port = parsed.port
        if port is None:
            port = 443 if (parsed.scheme or "").lower() == "https" else 80
        if not host:
            return False, "bad host"
        if not probe_port(host, int(port), timeout=min(timeout, 0.8)):
            return False, f"TCP {host}:{port} refused"
        # Prefer HTTP HEAD on http(s); ignore TLS detail failures if TCP open
        if (parsed.scheme or "http").lower() in ("http", "https"):
            try:
                req = urllib.request.Request(u, method="HEAD")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return True, f"HTTP {int(getattr(resp, 'status', 200) or 200)}"
            except urllib.error.HTTPError as e:
                return True, f"HTTP {int(e.code)}"
            except Exception as e:
                # TCP already open — treat as reachable (TLS/path quirks)
                return True, f"TCP open ({type(e).__name__})"
        return True, "TCP open"
    except Exception as e:
        return False, str(e)[:120]


def _probe_mcp_local_command(command: Any) -> tuple[bool, str]:
    """Local MCP: verify argv[0] exists (do not spawn the server)."""
    if isinstance(command, str):
        argv0 = command.strip()
    elif isinstance(command, list) and command:
        argv0 = str(command[0] or "").strip()
    else:
        return False, "missing command"
    if not argv0:
        return False, "empty command"
    if "/" in argv0 or argv0.startswith("~"):
        p = Path(argv0).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return True, "binary ok"
        if p.is_file():
            return True, "file exists"
        return False, f"missing binary: {argv0}"
    found = shutil.which(argv0)
    if found:
        return True, f"PATH {found}"
    return False, f"not on PATH: {argv0}"


def probe_agent_mcp(*, entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Probe local MCP inventory for domains.agent_mcp.

    Rules (Desktop Ops P0):
    - mcp_probed always True after this runs
    - no configured servers → ok=None (灰/未配置，非红)
    - configured + all reachable → ok=True
    - configured + any disconnect/probe failure → ok=False (caller push_red)
    """
    items = entries if entries is not None else _load_mcp_entries()
    servers: list[dict[str, Any]] = []
    failed: list[str] = []

    for ent in items:
        name = str(ent.get("name") or "mcp")
        typ = str(ent.get("type") or "local").lower()
        url = ent.get("url")
        row: dict[str, Any] = {
            "name": name,
            "source": ent.get("source"),
            "type": typ,
            "ok": None,
            "detail": "",
        }
        if typ == "remote" or url:
            ok, detail = _probe_mcp_url(str(url or ""))
            row["url"] = url
            row["ok"] = ok
            row["detail"] = detail
            if not ok:
                failed.append(name)
        else:
            ok, detail = _probe_mcp_local_command(ent.get("command"))
            row["ok"] = ok
            row["detail"] = detail
            if not ok:
                failed.append(name)
        servers.append(row)

    if not servers:
        return {
            "ok": None,
            "mcp_probed": True,
            "servers": [],
            "list": [],
            "failed": [],
            "note": "未配置 MCP（非红）",
        }

    all_ok = len(failed) == 0
    return {
        "ok": all_ok,
        "mcp_probed": True,
        "servers": servers,
        "list": [s.get("name") for s in servers],
        "failed": failed,
        "note": (
            f"{len(servers)} 个 MCP 正常"
            if all_ok
            else f"{len(failed)}/{len(servers)} 个 MCP 探测失败"
        ),
    }


def _is_ccc_control_port_down(dp: dict[str, Any]) -> bool:
    """True = CCC 控制面宕口（可升红）；False = 业务机/旁路（仅橙）。"""
    machine = str(dp.get("machine") or "")
    name = str(dp.get("name") or "")
    host = str(dp.get("host") or "")
    try:
        port = int(dp.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    # 明确非 CCC
    if machine in ("feiniu", "M1") or "生产机" in machine:
        return False
    if any(
        k in name.lower()
        for k in ("money printer", "medio", "ollama", "xianyu")
    ):
        return False
    if host.startswith("192.168.3.131"):  # feiniu
        return False
    # CCC 编排口 / Mac2017
    if port in (7775, 7776, 7777, 7778, 4000, 4002):
        return True
    if "Mac 2017" in machine or "CCC" in machine or "CCC" in name:
        return True
    # 未知默认不当红（避免外机拉红总灯）
    return False


def ops_health_envelope(
    *,
    control: dict[str, Any] | None = None,
    risks: dict[str, Any] | None = None,
    ready: dict[str, Any] | None = None,
    logistics: dict[str, Any] | None = None,
    resources_history: dict[str, Any] | None = None,
    ports: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    relay_usage: dict[str, Any] | None = None,
    bg_sessions: list[dict] | None = None,  # v0.62.0 阶段 3
    agent_mcp: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Desktop 运维总灯：severity green|amber|red + 仅红 alerts[].copy_payload。

    Hub 侧合成；M1 sidecar 仍可由 Desktop 本机合并。MCP 清单由 Hub 探本机配置。
    """
    ctrl = control if isinstance(control, dict) else {}
    risk_blob = risks if isinstance(risks, dict) else {}
    ready_blob = ready if isinstance(ready, dict) else {}
    logi = logistics if isinstance(logistics, dict) else {}
    hist = resources_history if isinstance(resources_history, dict) else {}
    ports_blob = ports if isinstance(ports, dict) else {}
    ov = overview if isinstance(overview, dict) else {}

    alerts: list[dict[str, Any]] = []
    seen: set[str] = set()
    amber_notes: list[str] = []

    def push_red(
        alert_id: str,
        title: str,
        detail: str,
        source: str,
        *,
        impact: str = "暂缓项目开发与下达",
        extra: dict[str, Any] | None = None,
    ) -> None:
        aid = (alert_id or title)[:80]
        if aid in seen:
            return
        seen.add(aid)
        suggest = _alert_suggest(aid, source)
        alerts.append(
            {
                "id": aid,
                "title": title,
                "detail": (detail or "")[:400],
                "source": source,
                "severity": "red",
                "copy_payload": _copy_payload(
                    alert_id=aid,
                    title=title,
                    detail=detail or "",
                    source=source,
                    impact=impact,
                    suggest=suggest,
                    extra=extra,
                ),
            }
        )

    # --- red from high risks ---
    for r in risk_blob.get("risks") or []:
        if not isinstance(r, dict):
            continue
        sev = str(r.get("severity") or "").lower()
        if sev == "high":
            push_red(
                str(r.get("id") or r.get("title") or "risk"),
                str(r.get("title") or "运维红灯"),
                str(r.get("detail") or ""),
                str(r.get("source") or "risk"),
                extra={"workspace": r.get("workspace")} if r.get("workspace") else None,
            )
        elif sev in ("medium", "warn", "low"):
            amber_notes.append(str(r.get("title") or "中度风险")[:80])

    # --- red from ready blockers not already covered ---
    if ready_blob.get("ok") is False:
        for b in ready_blob.get("blockers") or []:
            bs = str(b)
            if "红灯" in bs:
                continue  # already from risks.high
            bid = f"ready-{hash(bs) & 0xFFFF:x}"
            push_red(bid, bs, ready_blob.get("reason") or bs, "ready")

    # --- red from critical CCC ports down (ok preferred; alive→ok) ---
    port_map = ports_blob.get("ports") if isinstance(ports_blob.get("ports"), dict) else {}
    for pnum in (7775, 7777):
        info = port_map.get(str(pnum)) or port_map.get(pnum)
        if _port_ok(info) is False:
            push_red(
                f"port-{pnum}",
                f"端口 :{pnum} 不通",
                str(
                    (info or {}).get("detail")
                    or (info or {}).get("error")
                    or (info or {}).get("label")
                    or "probe failed"
                ),
                "ports",
                extra={"port": pnum, "host": (info or {}).get("host")},
            )
    down = ov.get("down_ports") or []
    ccc_down: list[Any] = []
    if isinstance(down, list):
        for dp in down[:12]:
            if isinstance(dp, dict):
                if not _is_ccc_control_port_down(dp):
                    # feiniu / Money Printer 等非 CCC 控制面 → 橙，不拉总红
                    pn = dp.get("port") or dp.get("name")
                    host = dp.get("host") or dp.get("machine") or ""
                    amber_notes.append(f"非CCC端口 {pn}@{host} 未响应")
                    continue
                ccc_down.append(dp)
                pn = dp.get("port") or dp.get("name")
                push_red(
                    f"down-{pn}",
                    f"端口异常: {pn}",
                    str(dp.get("detail") or dp.get("host") or ""),
                    "ports",
                    extra={"port": pn},
                )
            elif dp:
                push_red(f"down-{dp}", f"端口异常: {dp}", "", "ports")
                ccc_down.append(dp)

    # --- capacity ---
    summary = hist.get("summary") if isinstance(hist.get("summary"), dict) else {}
    verdict = summary.get("verdict")
    if verdict == "saturated":
        push_red(
            "capacity-saturated",
            "主机资源 saturated",
            str(summary.get("note") or summary.get("reason") or "先治挂死"),
            "capacity",
        )
    elif verdict and verdict not in ("headroom", "ok", "unknown", None):
        amber_notes.append(f"资源 {verdict}")

    # --- MCP probe (Hub-local config); unconfigured = not red ---
    mcp_domain = (
        agent_mcp if isinstance(agent_mcp, dict) else probe_agent_mcp()
    )
    if mcp_domain.get("mcp_probed") and mcp_domain.get("ok") is False:
        failed = mcp_domain.get("failed") or []
        detail = mcp_domain.get("note") or ""
        if failed:
            detail = f"失败: {', '.join(str(x) for x in failed[:8])}. {detail}"
        push_red(
            "mcp-probe-failed",
            "MCP 探针失败",
            detail[:400],
            "mcp",
            extra={
                "failed": failed[:12],
                "list": (mcp_domain.get("list") or [])[:20],
            },
        )

    if logi.get("needs_attention") is True and not alerts:
        amber_notes.append(str(logi.get("headline") or "后勤需关注")[:80])
    elif logi.get("needs_attention") is True:
        # already red from something else — keep amber note only if no red
        pass

    # control soft: invent open is amber (should stay hard-off)
    if ctrl.get("invent_hard_disabled") is False:
        amber_notes.append("invent 硬关被打开")

    severity = "green"
    if alerts:
        severity = "red"
    elif amber_notes:
        severity = "amber"

    if severity == "green":
        human_line = "系统健康 · 可以放心开发和下任务"
    elif severity == "amber":
        human_line = "有轻度提示，不挡开发 · " + "；".join(amber_notes[:2])
    else:
        human_line = f"请交给 Agent · {len(alerts)} 项红灯"

    # domain digests for Desktop expand (not homepage noise)
    ccc_ports = []
    for pnum in (7775, 7777, 7778):
        info = port_map.get(str(pnum)) or port_map.get(pnum) or {}
        ccc_ports.append(
            {
                "port": pnum,
                "ok": _port_ok(info),
            }
        )
    domains = {
        "cluster": {
            "engine_running": ctrl.get("engine_running"),
            "mode": ctrl.get("mode"),
            "hub_port_7777": ctrl.get("hub_port_7777"),
            "ports": ccc_ports,
            # 宕口计数只认 CCC 控制面，避免 feiniu 业务口拉红集群灯
            "down_ports_n": len(ccc_down),
            "alert_count": len(ccc_down),
        },
        "agent_mcp": mcp_domain,
        # CCC Relay 2026-07-25:三档 tier 用量 + 健康 + cache 命中率
        # 灯:ok=true green;ok=false amber(降级直连但仍可用)
        "relay": _build_relay_domain(relay_usage),
        # v0.62.0 阶段 3:claude --bg 长 session 跟踪(Engine tick 30s 更新)
        "bg_sessions": _build_bg_sessions_domain(bg_sessions),
        "capacity": {
            "verdict": verdict,
            "note": summary.get("note") or summary.get("reason"),
        },
    }

    return {
        "severity": severity,
        "human_line": human_line,
        "alerts": alerts,
        "amber_notes": amber_notes[:8],
        "domains": domains,
        "ready_ok": ready_blob.get("ok"),
        "generated_at": _now_iso(),
    }


def _build_relay_domain(relay_usage: dict[str, Any] | None) -> dict[str, Any]:
    """CCC Relay 2026-07-25:envelope.domains.relay 子域;展示三档 + 健康。

    relay_usage: fetch_router_usage() 的输出;None 表示未拉取,返回 ok=null 兜底。
    """
    if not relay_usage:
        return {
            "ok": None,
            "source": "unknown",
            "tiers": {},
            "note": "relay_usage 未拉取",
        }
    if not relay_usage.get("ok"):
        return {
            "ok": False,
            "source": relay_usage.get("source", "relay_down"),
            "tiers": {},
            "error": relay_usage.get("error"),
            "note": "relay 不可达 — 客户端 fail-open 直连",
        }
    tiers_in = relay_usage.get("tiers") or {}
    return {
        "ok": True,
        "source": "relay",
        "host": relay_usage.get("host"),
        "port": relay_usage.get("port"),
        "tiers": tiers_in,
        "total": relay_usage.get("total") or {},
        "note": "三档 flash/Pro/code",
    }


def _build_bg_sessions_domain(sessions: list[dict] | None) -> dict[str, Any]:
    """v0.62.0 阶段 3:envelope.domains.bg_sessions 子域。

    sessions: list_long_lived_sessions() 的输出;None 表示未拉取,返 ok=null 兜底。
    """
    if not sessions:
        return {
            "ok": None,
            "count": 0,
            "sessions": [],
            "note": "bg_sessions 未拉取",
        }
    # ok=true 全活;ok=false 全死;ok=None 部分活(混合)
    alive_count = sum(1 for s in sessions if s.get("alive"))
    if alive_count == len(sessions):
        ok = True
    elif alive_count == 0:
        ok = False
    else:
        ok = None
    return {
        "ok": ok,
        "count": len(sessions),
        "alive_count": alive_count,
        "sessions": sessions,
        "note": "claude --bg 长 session(Engine 跟踪)/Desktop UI 可看",
    }


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
    all_apps: bool = False,
) -> dict:
    key = "all-apps" if all_apps else str(workspace_path.resolve())
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
    cmd = ["python3", str(script)]
    if all_apps:
        cmd.append("--all-apps")
    else:
        cmd.extend(["--workspace", str(workspace_path)])
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
            "all_apps": all_apps,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "apply": apply, "all_apps": all_apps}


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
                    (7775, "Board"),
                    (22, "ssh"),
                ],
                "notes": "唯一生产：Hub/Board/Engine/业务仓在 Mac2017；模型出口=CCC Relay（见 docs/deploy/topology.md）",
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
    critical = {7775, 7777}
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
    """Lightweight docs debt hints (Phase 3/5).

    Desktop contract: ``items`` with workspace/file/issue.
    SPA compat: ``findings`` alias (same list, richer fields kept).
    """
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
                    "file": infra.get("infra_path") or f"port:{p}",
                    "issue": f"infrastructure 登记端口 {p} 当前未响应",
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
                    "file": "README.md",
                    "issue": f"{ws_id} 缺少 README.md",
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
                        "file": "CHANGELOG.md",
                        "issue": f"{ws_id} CHANGELOG 超过 30 天未更新",
                        "suggestion": f"最近 tag: {tags.splitlines()[0] if tags else '?'}",
                    }
                )

    items = findings[:40]
    return {
        "items": items,
        "findings": items,  # SPA alias
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
        except Exception as e:
            _log.debug("ops_probe workspace digest %s: %s", ws_id, e)
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


def _plist_ops_status() -> dict[str, Any]:
    """Whether com.ccc.ops-* agents are loaded and whether apply-ammo is configured."""
    home = Path.home()
    labels = ("com.ccc.ops-daily-diff", "com.ccc.ops-docs-review")
    agents: list[dict[str, Any]] = []
    for label in labels:
        loaded = False
        try:
            r = subprocess.run(
                ["launchctl", "list", label],
                capture_output=True,
                text=True,
                timeout=3,
            )
            loaded = r.returncode == 0
        except Exception:
            loaded = False
        plist_paths = [
            home / "Library" / "LaunchAgents" / f"{label}.plist",
            home / "Library" / "LaunchAgents" / "disabled-ccc" / f"{label}.plist",
        ]
        plist_path = next((p for p in plist_paths if p.is_file()), None)
        apply_ammo = False
        if plist_path and plist_path.is_file():
            try:
                text = plist_path.read_text(encoding="utf-8")
                apply_ammo = ">--apply<" in text or ">--apply</string>" in text
            except OSError as e:
                _log.debug("ops_probe plist read %s: %s", plist_path, e)
        agents.append(
            {
                "label": label,
                "loaded": loaded,
                "plist": str(plist_path) if plist_path else None,
                "apply_ammo": apply_ammo,
            }
        )
    return {
        "agents": agents,
        "any_loaded": any(a["loaded"] for a in agents),
        "any_apply_ammo": any(a["apply_ammo"] for a in agents),
    }


def logistics_heartbeat(workspaces: dict[str, str] | None = None) -> dict:
    """Read-only Ops logistics pulse for Hub/Desktop (no new action buttons)."""
    spaces = workspaces or {}
    ammo = list_ammo_workspaces()
    day = datetime.now().strftime("%Y-%m-%d")
    latest_daily: list[dict] = []
    latest_docs: list[dict] = []
    spawn_hint = 0

    roots: list[tuple[str, Path]] = [(a["workspace"], Path(a["path"])) for a in ammo]
    for ws_id, path in spaces.items():
        p = Path(path).expanduser()
        if p.is_dir() and not any(p.resolve() == r.resolve() for _, r in roots):
            roots.append((ws_id, p))

    for ws_id, root in roots[:16]:
        reports = root / ".ccc" / "reports"
        daily = reports / f"daily-review-{day}.md"
        docs = reports / f"docs-review-{day}.md"
        wm = root / ".ccc" / "stats" / "daily-review-watermark.json"
        if daily.is_file():
            body = daily.read_text(encoding="utf-8", errors="replace")[:2000]
            dec = ""
            m = re.search(r"decision:\s*\*\*([A-J])\*\*", body)
            if m:
                dec = m.group(1)
            if "spawn" in body and '"created": true' in body.lower().replace(" ", ""):
                spawn_hint += 1
            elif re.search(r'"created":\s*true', body):
                spawn_hint += 1
            latest_daily.append(
                {
                    "workspace": ws_id,
                    "path": str(daily),
                    "decision": dec or None,
                    "mtime": datetime.fromtimestamp(
                        daily.stat().st_mtime
                    ).isoformat(timespec="seconds"),
                }
            )
        if docs.is_file():
            latest_docs.append(
                {
                    "workspace": ws_id,
                    "path": str(docs),
                    "mtime": datetime.fromtimestamp(
                        docs.stat().st_mtime
                    ).isoformat(timespec="seconds"),
                }
            )
        wm_sha = None
        if wm.is_file():
            try:
                wm_sha = json.loads(wm.read_text(encoding="utf-8")).get("sha")
            except (OSError, json.JSONDecodeError) as e:
                _log.debug("ops_probe watermark read %s: %s", wm, e)
            if latest_daily and latest_daily[-1].get("workspace") == ws_id:
                latest_daily[-1]["watermark"] = wm_sha

    auto_n = 0
    try:
        auto_n = len(list_ops_auto_tasks(spaces or {a["workspace"]: a["path"] for a in ammo}))
    except Exception:
        auto_n = 0

    plist = _plist_ops_status()
    headline_parts: list[str] = []
    needs_attention = False
    if not ammo:
        headline_parts.append("无弹药仓")
        needs_attention = True
    else:
        headline_parts.append(f"{len(ammo)}仓可供弹")
    if not plist.get("any_loaded"):
        headline_parts.append("plist未启用")
        needs_attention = True
    elif not plist.get("any_apply_ammo"):
        headline_parts.append("plist dry-run")
    else:
        headline_parts.append("plist apply-ammo")
    if latest_daily:
        from collections import Counter

        counts = Counter((x.get("decision") or "?") for x in latest_daily)
        dec_s = " ".join(f"{k}×{v}" for k, v in sorted(counts.items()))
        headline_parts.append(f"今日日审 {dec_s}")
    else:
        headline_parts.append("今日无日审")
    if auto_n:
        headline_parts.append(f"ops-auto {auto_n}")
    if spawn_hint:
        headline_parts.append(f"spawn提示 {spawn_hint}")

    return {
        "ammo_workspaces": ammo,
        "daily_today": latest_daily,
        "docs_today": latest_docs,
        "spawn_hint_today": spawn_hint,
        "ops_auto_backlog": auto_n,
        "plist": plist,
        "headline": " · ".join(headline_parts),
        "needs_attention": needs_attention,
        "note": "后勤心跳只读；供弹仅 engine-eligible；定时见 install-ops-plist.sh",
        "generated_at": _now_iso(),
    }


def resolve_ammo_workspace(
    workspace: str | Path | None,
    *,
    registry: Path | None = None,
) -> dict[str, Any]:
    """Resolve ops-auto / daily-review ammo target.

    Must be registry engine-eligible (app). CCC orch is forbidden — Engine
    never consumes orch boards (ops-ammo-orch-forbidden).
    """
    from _workspace_registry import (
        entry_engine_eligible,
        is_orch_path,
        list_engine_paths,
        lookup_entry,
        orch_home,
    )

    raw = (str(workspace).strip() if workspace is not None else "") or ""
    if not raw:
        return {
            "ok": False,
            "error": "workspace required (engine-eligible app; not CCC orch)",
            "code": "ops-ammo-workspace-required",
        }

    entry = lookup_entry(raw, registry=registry)
    path: Path | None = None
    name: str | None = None
    if entry:
        path = Path(entry["path"])
        name = str(entry.get("name") or path.name)
        if not entry_engine_eligible(entry):
            return {
                "ok": False,
                "error": (
                    f"ops ammo forbidden for non-engine workspace "
                    f"{name!r} (role={entry.get('role')}, engine={entry.get('engine')}); "
                    "engine-eligible apps only"
                ),
                "code": "ops-ammo-orch-forbidden",
                "workspace": name,
                "path": str(path),
            }
    else:
        try:
            path = Path(raw).expanduser().resolve()
        except OSError as e:
            return {
                "ok": False,
                "error": f"invalid workspace path: {e}",
                "code": "ops-ammo-workspace-invalid",
            }
        name = path.name
        if is_orch_path(path) or path == orch_home().resolve():
            return {
                "ok": False,
                "error": "ops ammo forbidden on CCC orch (engine-eligible apps only)",
                "code": "ops-ammo-orch-forbidden",
                "workspace": name,
                "path": str(path),
            }
        # Unregistered path: allow only if it is already an engine-eligible path
        eligible = {str(p.resolve()) for p in list_engine_paths(registry)}
        if str(path) not in eligible:
            return {
                "ok": False,
                "error": (
                    f"workspace {name!r} not engine-eligible in registry; "
                    "register an app with engine=true"
                ),
                "code": "ops-ammo-not-eligible",
                "workspace": name,
                "path": str(path),
            }

    if not path or not path.is_dir():
        return {
            "ok": False,
            "error": f"workspace path missing: {path}",
            "code": "ops-ammo-path-missing",
            "workspace": name,
        }
    return {
        "ok": True,
        "path": path,
        "workspace": name or path.name,
        "code": "ok",
    }


def list_ammo_workspaces(registry: Path | None = None) -> list[dict[str, str]]:
    """Engine-eligible apps suitable for ops ammo / daily review."""
    from _workspace_registry import entry_engine_eligible, list_registered_entries

    out: list[dict[str, str]] = []
    for e in list_registered_entries(registry):
        if not entry_engine_eligible(e):
            continue
        out.append({"workspace": str(e["name"]), "path": str(e["path"])})
    return out


def adopt_suggestion(
    workspace_path: Path | str,
    *,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
) -> dict:
    """Create backlog card from ops suggestion (ops-auto). Not invent.

    Target must be engine-eligible; CCC orch rejected (ops-ammo-orch-forbidden).
    """
    resolved = resolve_ammo_workspace(workspace_path)
    if not resolved.get("ok"):
        return {
            "ok": False,
            "error": resolved.get("error"),
            "code": resolved.get("code") or "ops-ammo-orch-forbidden",
            "workspace": resolved.get("workspace"),
        }

    path = Path(resolved["path"])
    from board.context import set_workspace
    from _board_store import FileBoardStore

    set_workspace(path)
    store = FileBoardStore(path)
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
    return {
        "ok": ok,
        "task_id": tid,
        "engine_wake": wake,
        "tags": tag_list,
        "workspace": resolved.get("workspace"),
        "path": str(path),
    }
