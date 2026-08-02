"""集群状态采集 — 独立实现，不依赖 qx-map / 外脑。

采集内容（默认只读巡检）：
1. 节点可达性（TCP 连接检测）
2. 端口监听状态
3. 服务进程状态

输出：写入 web/data/cluster.js（window.CLUSTER_DATA = {...}），供前端集群/运维页读取。

用法：
    from server.engine.cluster import collect_cluster_status, parse_cluster_targets

    ok, summary = collect_cluster_status(cfg)
    # ok=True, summary={"nodes": [...], "services": [...], "output": "..."}
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("ccc.engine.cluster")

# 默认输出路径（相对于项目根）
DEFAULT_OUTPUT = "server/web/data/cluster.js"

# 默认服务清单（名称 → 进程名关键词，不依赖外部 manifest）
DEFAULT_SERVICES: dict[str, str] = {
    "ccc-engine": "ccc-engine",
    "ccc-board-scheduler": "ccc-board-scheduler",
    "ccc-hub": "ccc-chat-server",
    "ccc-board-api": "ccc-board-server",
}


@dataclass
class NodeStatus:
    """单个节点状态。"""
    host: str
    port: int
    reachable: bool
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class ServiceStatus:
    """单个服务状态。"""
    name: str
    running: bool
    pid: int | None = None
    error: str | None = None


@dataclass
class ClusterSnapshot:
    """集群快照 — 一次采集的全部结果。"""
    nodes: list[NodeStatus] = field(default_factory=list)
    services: list[ServiceStatus] = field(default_factory=list)
    collected_at: str = ""


def parse_cluster_targets(cfg: dict[str, Any]) -> list[tuple[str, int]]:
    """从配置解析采集目标列表。

    CLUSTER_TARGETS 格式：逗号分隔 host:port，如 "localhost:PORT1,localhost:PORT2"
    空字符串返回空列表。
    """
    raw = cfg.get("CLUSTER_TARGETS", "").strip()
    if not raw:
        return []
    targets: list[tuple[str, int]] = []
    for segment in raw.split(","):
        segment = segment.strip()
        if not segment:
            continue
        parts = segment.rsplit(":", 1)
        if len(parts) != 2:
            logger.warning("无效采集目标格式（跳过）: %s", segment)
            continue
        try:
            host = parts[0].strip()
            port = int(parts[1].strip())
            targets.append((host, port))
        except ValueError:
            logger.warning("无效端口值（跳过）: %s", segment)
    return targets


def check_tcp_reachable(host: str, port: int, timeout: float = 3.0) -> NodeStatus:
    """TCP 连接检测节点可达性。"""
    import time
    start = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        elapsed = (time.monotonic() - start) * 1000  # ms
        return NodeStatus(host=host, port=port, reachable=True, latency_ms=round(elapsed, 1))
    except (OSError, socket.gaierror) as exc:
        elapsed = (time.monotonic() - start) * 1000
        return NodeStatus(
            host=host, port=port, reachable=False,
            latency_ms=round(elapsed, 1), error=str(exc),
        )


def check_service_status(process_keyword: str) -> ServiceStatus:
    """通过 pgrep 检查服务进程状态。"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", process_keyword],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().splitlines()
            return ServiceStatus(
                name=process_keyword, running=True,
                pid=int(pids[0]),
            )
        return ServiceStatus(name=process_keyword, running=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return ServiceStatus(
            name=process_keyword, running=False, error=str(exc),
        )


def collect_cluster_status(cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """采集集群状态并写入输出文件。

    返回 (ok, summary_dict)。
    """
    import datetime

    targets = parse_cluster_targets(cfg)
    nodes: list[NodeStatus] = []
    for host, port in targets:
        nodes.append(check_tcp_reachable(host, port))

    services: list[ServiceStatus] = []
    for name, keyword in DEFAULT_SERVICES.items():
        services.append(check_service_status(keyword))

    snapshot = ClusterSnapshot(
        nodes=nodes,
        services=services,
        collected_at=datetime.datetime.now().isoformat(timespec="seconds"),
    )

    # 写输出文件
    output_path = cfg.get("DATA_DIR", "")
    if output_path:
        output_file = Path(output_path) / "cluster.js"
    else:
        # fallback 到默认路径
        here = Path(__file__).resolve().parent.parent
        output_file = here / DEFAULT_OUTPUT
    output_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "nodes": [asdict(n) for n in snapshot.nodes],
        "services": [asdict(s) for s in snapshot.services],
        "collected_at": snapshot.collected_at,
        "config": {
            "scheduler_interval": int(cfg.get("SCHEDULER_INTERVAL", "60")),
            "scheduler_dispatch_dir": cfg.get("SCHEDULER_DISPATCH_DIR", ""),
            "data_dir": cfg.get("DATA_DIR", ""),
            "board_port": cfg.get("BOARD_PORT", ""),
            "web_port": cfg.get("WEB_PORT", ""),
        },
    }
    js_content = f"window.CLUSTER_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};\n"
    output_file.write_text(js_content, encoding="utf-8")

    summary = {
        "nodes_checked": len(nodes),
        "nodes_reachable": sum(1 for n in nodes if n.reachable),
        "services_checked": len(services),
        "services_running": sum(1 for s in services if s.running),
        "output": str(output_file),
    }
    logger.info("集群采集完成: %s", summary)
    return True, summary


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：单次采集集群状态并输出。"""
    import argparse
    from server.config.loader import load_config, ConfigError

    parser = argparse.ArgumentParser(description="CCC 集群状态采集（单次）")
    parser.add_argument("--config", required=True, help="config.env 路径")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 2

    ok, summary = collect_cluster_status(cfg)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())