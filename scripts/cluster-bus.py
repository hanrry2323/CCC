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
import json
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

# --- Config ------------------------------------------------------------
PORT = 9100
HOSTBIND = "0.0.0.0"
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
    last_heartbeat: float
    registered_at: float


# --- App ---------------------------------------------------------------
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
def list_nodes(active_only: bool = True) -> dict:
    """Returns active nodes (last_heartbeat < 90s) by default. Set active_only=false for all-known."""
    now = _now()
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
            if (not active_only) or _is_active(n, now)
        ]
    return {"count": len(items), "active_only": active_only, "nodes": items}


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
            "active": _is_active(n),
            "last_heartbeat_age_s": round(_now() - n["last_heartbeat"], 1),
            "registered_at": n["registered_at"],
        }


# --- Background checkpoint (anti-restart-loss) --------------------------
def _checkpoint_loop():
    while True:
        time.sleep(60)
        try:
            with state_lock:
                snapshot = json.loads(json.dumps(nodes))  # deep copy
            tmp = CHECKPOINT_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(snapshot))
            tmp.rename(CHECKPOINT_PATH)
        except Exception as e:
            print(f"[cluster-bus] checkpoint failed: {e}", file=sys.stderr)


@app.on_event("startup")
def _restore_from_checkpoint():
    if CHECKPOINT_PATH.exists():
        try:
            data = json.loads(CHECKPOINT_PATH.read_text())
            with state_lock:
                nodes.update(data)
            print(f"[cluster-bus] restored {len(nodes)} nodes from {CHECKPOINT_PATH}")
        except Exception as e:
            print(f"[cluster-bus] restore failed: {e}", file=sys.stderr)
    threading.Thread(target=_checkpoint_loop, daemon=True).start()


# --- Main --------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host=HOSTBIND, port=PORT, log_level="info")
