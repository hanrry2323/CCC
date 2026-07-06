#!/usr/bin/env python3
"""cluster-bus.py — CCC v1.0 cluster bus + node registry + heartbeat.

P0-1 of v1.0 automation plan.

Endpoints:
  POST /api/node/register     — register a node with capabilities
  POST /api/node/heartbeat    — 30s ping, exp 90s
  GET  /api/node/list         — list active nodes (heartbeat fresh)
  GET  /api/node/{node_id}    — inspect single node
  GET  /api/health            — bus liveness

Persistence: in-memory dict, checkpoint to /tmp/ccc-cluster-bus.json every 60s.
(Anti-restart-loss: bus can rebuild by accepting heartbeats from active nodes.

Borrowed from: clawmed-ai T1.2_worker_analysis heartbeat protocol
  (30s ping / 90s timeout), plus agentmesh community consensus
  (TCP service registration + capability-based routing).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

# --- Config (CLI overridable) -------------------------------------------
_parser = argparse.ArgumentParser(description="CCC cluster bus")
_parser.add_argument("--port", type=int, default=9100, help="listen port")
_parser.add_argument("--host", type=str, default="0.0.0.0", help="bind address")
# Parse known args only so pytest can import the module without --port
_args, _ = _parser.parse_known_args()
PORT = _args.port
HOSTBIND = _args.host

HEARTBEAT_TTL_SECONDS = 90
CHECKPOINT_PATH = Path("/tmp/ccc-cluster-bus.json")

# --- In-memory state ---------------------------------------------------
state_lock = threading.Lock()
nodes: dict[str, dict] = {}  # node_id -> node_state


# --- Schemas -----------------------------------------------------------
class Capabilities(BaseModel):
    """Free-form capability tags. Convention: L1=shell|git|python, L2=claude-p|glm-5|deepseek-v4-flash, L3=browser|gpu|cron|ssh-remote."""
    tags: list[str] = Field(default_factory=list)


class RegisterRequest(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=64)
    host: str = Field(..., pattern=r"^[\w.\-:]+$")
    port: int = Field(..., ge=1, le=65535)
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class HeartbeatRequest(BaseModel):
    node_id: str
    load: float = Field(0.0, ge=0.0, le=100.0)  # current load 0-100


class NodeRecord(BaseModel):
    node_id: str
    host: str
    port: int
    capabilities: list[str]
    load: float
    last_heartbeat_age_s: float
    registered_at: float
    metadata: dict = Field(default_factory=dict)


# --- FastAPI app -------------------------------------------------------
app = FastAPI(title="ccc-cluster-bus", version="0.1.0")


def _now() -> float:
    return time.time()


def _is_active(node: dict, now: float | None = None) -> bool:
    now = now or _now()
    return (now - node["last_heartbeat"]) < HEARTBEAT_TTL_SECONDS


@app.get("/api/health")
def health() -> dict:
    with state_lock:
        active = sum(1 for n in nodes.values() if _is_active(n))
    return {
        "status": "ok",
        "service": "ccc-cluster-bus",
        "version": "0.1.0",
        "active_nodes": active,
        "total_nodes": len(nodes),
        "server_time": _now(),
    }


@app.post("/api/node/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest) -> dict:
    now = _now()
    with state_lock:
        if req.node_id in nodes:
            nodes[req.node_id].update({
                "host": req.host,
                "port": req.port,
                "capabilities": req.capabilities,
                "metadata": req.metadata,
                "last_heartbeat": now,  # reset hb on re-register
                "load": 0.0,
            })
            return {"node_id": req.node_id, "status": "re-registered", "at": now}
        nodes[req.node_id] = {
            "node_id": req.node_id,
            "host": req.host,
            "port": req.port,
            "capabilities": req.capabilities,
            "metadata": req.metadata,
            "registered_at": now,
            "last_heartbeat": now,
            "load": 0.0,
        }
    return {"node_id": req.node_id, "status": "registered", "at": now}


@app.post("/api/node/heartbeat")
def heartbeat(req: HeartbeatRequest) -> dict:
    now = _now()
    with state_lock:
        if req.node_id not in nodes:
            raise HTTPException(
                status_code=404, detail=f"node {req.node_id!r} not registered; POST /api/node/register first"
            )
        nodes[req.node_id]["last_heartbeat"] = now
        nodes[req.node_id]["load"] = req.load
    return {"node_id": req.node_id, "ack_at": now}


@app.get("/api/node/list")
def list_nodes(
    active_only: bool = True,
    include_stale: bool = False,
) -> dict:
    """Returns active nodes (last_heartbeat < 90s) by default.

    Query params:
      - active_only=true  (default): exclude stale nodes
      - active_only=false            : include all known nodes
      - include_stale=true           : alias for active_only=false (used by ccc-dispatch)

    Both controls are kept for back-compat; `include_stale` is the canonical name
    going forward (plan: cluster-bus-bugfixes Phase 2).
    """
    now = _now()
    effective_active_only = active_only and not include_stale
    with state_lock:
        items = [
            {
                "node_id": n["node_id"],
                "host": n["host"],
                "port": n["port"],
                "capabilities": n["capabilities"],
                "load": n["load"],
                "last_heartbeat_age_s": round(now - n["last_heartbeat"], 1),
                "registered_at": n["registered_at"],
            }
            for n in nodes.values()
            if (not effective_active_only) or _is_active(n, now)
        ]
    return {
        "count": len(items),
        "active_only": effective_active_only,
        "include_stale": include_stale,
        "nodes": items,
    }


@app.get("/api/node/{node_id}")
def get_node(node_id: str) -> dict:
    with state_lock:
        if node_id not in nodes:
            raise HTTPException(status_code=404, detail=f"node {node_id!r} not found")
        n = nodes[node_id]
    return {
        "node_id": n["node_id"],
        "host": n["host"],
        "port": n["port"],
        "capabilities": n["capabilities"],
        "load": n["load"],
        "last_heartbeat_age_s": round(_now() - n["last_heartbeat"], 1),
        "registered_at": n["registered_at"],
    }


# --- Checkpoint helpers ------------------------------------------------
def _write_checkpoint():
    with state_lock:
        data = {"nodes": dict(nodes), "written_at": _now()}
    import tempfile
    tmp = CHECKPOINT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.rename(CHECKPOINT_PATH)


def _checkpoint_loop():
    while True:
        time.sleep(60)
        try:
            _write_checkpoint()
        except Exception:
            pass


@app.on_event("startup")
def _startup():
    if CHECKPOINT_PATH.exists():
        try:
            data = json.loads(CHECKPOINT_PATH.read_text())
            with state_lock:
                nodes.update(data.get("nodes", {}))
            print(f"[cluster-bus] restored {len(nodes)} nodes from {CHECKPOINT_PATH}")
        except Exception as e:
            print(f"[cluster-bus] restore failed: {e}", file=sys.stderr)

    # GC stale nodes on startup (Bug 3 fix): remove nodes whose last_heartbeat
    # is older than HEARTBEAT_TTL_SECONDS * 10 (= 900s = 15 min).
    # Rationale: stale entries accumulate on disk/memory from killed sessions
    # (e.g. previous zcode-debug nodes). Without GC, restart pollution persists.
    gc_threshold_s = HEARTBEAT_TTL_SECONDS * 10
    now = _now()
    gc_count = 0
    with state_lock:
        for node_id, node in list(nodes.items()):
            age = now - node.get("last_heartbeat", 0)
            if age > gc_threshold_s:
                print(f"[cluster-bus] GC stale node {node_id} (age={age:.0f}s)")
                del nodes[node_id]
                gc_count += 1
    if gc_count > 0:
        print(f"[cluster-bus] GC removed {gc_count} stale nodes on startup")

    threading.Thread(target=_checkpoint_loop, daemon=True).start()


# --- Main --------------------------------------------------------------
if __name__ == "__main__":
    # Use h11 instead of httptools to avoid macOS connection accumulation issues
    # httptools can stall after ~900 rapid keep-alive requests (macOS asyncio quirk)
    uvicorn.run(app, host=HOSTBIND, port=PORT, log_level="info", http="h11")
