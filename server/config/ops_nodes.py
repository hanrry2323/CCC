"""运维节点表加载 — KNOWN_SERVICES / PORTALS 单一来源（批D 项3）。

数据真值：``server/config/ops-nodes.json``（结构 = 旧双份内嵌表合并）。
加载失败（文件缺失/JSON 损坏）回落内嵌默认表（= 现值），保证生产行为等价。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_OPS_NODES_PATH = Path(__file__).resolve().parent / "ops-nodes.json"

# 内嵌默认表（= 现值，文件缺失/损坏时回落）
_DEFAULT_OPS_NODES: dict[str, Any] = {
    "services": {
        "com.ccc.web-server": {"name": "CCC Web", "port": 7788, "url": "http://192.168.3.116:7788"},
        "com.ccc.engine": {"name": "CCC Engine", "port": 0, "url": ""},
        "com.ccc.scheduler": {"name": "CCC Scheduler", "port": 0, "url": ""},
        "com.ccc.board-scheduler": {"name": "Board Scheduler", "port": 0, "url": ""},
        "com.deepseek.dsh-web": {"name": "DSH Web", "port": 3080, "url": "http://192.168.3.116:3080"},
        "com.deepseek.dsh-web-watchdog": {"name": "DSH Watchdog", "port": 0, "url": ""},
        "com.xianyu.worker": {"name": "Xianyu Worker", "port": 0, "url": ""},
        "com.qb.data-engine": {"name": "QB Data Engine", "port": 8091, "url": "http://127.0.0.1:8091"},
        "com.qb.order-gateway": {"name": "QB Order Gateway", "port": 0, "url": ""},
        "com.ccc.sync-skills": {"name": "Sync Skills", "port": 0, "url": ""},
    },
    "portals": [
        {"name": "CCC 控制台", "machine": "Mac2017", "port": 7788, "url": "http://192.168.3.116:7788"},
        {"name": "DSH Web", "machine": "Mac2017", "port": 3080, "url": "http://192.168.3.116:3080"},
        {"name": "xy Admin", "machine": "Mac2017", "port": 8765, "url": "http://192.168.3.116:8765"},
        {"name": "QB Data Engine", "machine": "Mac2017", "port": 8091, "url": "http://127.0.0.1:8091"},
        {"name": "HP MCP Server", "machine": "HP", "port": 8083, "url": "http://192.168.3.131:8083/mcp"},
        {"name": "HP Memory Store", "machine": "HP", "port": 8082, "url": "http://192.168.3.131:8082"},
        {"name": "HP PostgreSQL", "machine": "HP", "port": 5432, "url": ""},
        {"name": "M1 PostgreSQL", "machine": "M1", "port": 5432, "url": ""},
        {"name": "QuantHive API", "machine": "HK", "port": 8000, "url": "http://127.0.0.1:8000"},
        {"name": "QuantHive Gateway", "machine": "HK", "port": 443, "url": "https://124.156.166.72"},
    ],
}


def load_known_services() -> dict[str, dict[str, Any]]:
    """返回 KNOWN_SERVICES 表（label → name/port/url）。"""
    return dict(load_ops_nodes()["services"])


def load_portals() -> list[dict[str, Any]]:
    """返回 PORTALS 表（name/machine/port/url）。"""
    return list(load_ops_nodes()["portals"])


def load_ops_nodes() -> dict[str, Any]:
    """加载 ops-nodes.json；文件缺失/损坏回落内嵌默认表。"""
    try:
        data = json.loads(_OPS_NODES_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("services"), dict) and isinstance(data.get("portals"), list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return _DEFAULT_OPS_NODES
