---
title: CCC Cluster Protocol v1.0
---

# CCC Cluster Protocol v1.0

> Cross-device / Cross-session CCC node coordination protocol.
> Implementation: `scripts/cluster-bus.py` (P0-1) + `scripts/ccc-dispatch.py` (P0-2).

## 1. Topology

```
              ┌──────────────┐
              │  IDE Client  │  (Trae / Cursor / Claude Code)
              │  (user)      │
              └──────┬───────┘
                     │ "按 ccc full 跑 X"
                     ▼
        ┌────────────────────────┐
        │    ccc-dispatch.py     │  (P0-2)
        │    reads plan.md       │
        │    outputs triple      │
        │    hard-gate 'yes'     │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  cluster-bus (P0-1)    │  ◄── this protocol
        │  POST /api/node/...    │      port 9100 default
        │  GET  /api/node/list   │
        └────┬─────────┬────────┘
             │         │
     ┌───────▼──┐  ┌───▼────────┐
     │ M1 node  │  │ mac2017    │  ◄── real nodes
     │ (M1)     │  │ (192.168.3)│
     └──────────┘  └────────────┘
```

## 2. Endpoints

### 2.1 `POST /api/node/register`

- **Purpose**: register a node with capabilities
- **Request**:
  ```json
  {
    "node_id": "m1",
    "host": "127.0.0.1",
    "port": 9101,
    "capabilities": ["shell", "claude-p", "git"],
    "metadata": {"role": "developer", "env": "dev"}
  }
  ```
- **Response (201 created)**:
  ```json
  {"node_id": "m1", "status": "registered", "at": 1783309949.846792}
  ```
- **Errors**:
  - 422: validation failed (e.g. `node_id` empty)
  - Re-register: returns `{"status": "re-registered", ...}` (200 implicit)

### 2.2 `POST /api/node/heartbeat`

- **Purpose**: 30s ping, exp 90s TTL
- **Request**:
  ```json
  {"node_id": "m1", "load": 2.5}
  ```
- **Response (200)**:
  ```json
  {"node_id": "m1", "ack_at": 1783309949.887715}
  ```
- **Errors**:
  - 404 if node not registered (`POST /api/node/register first`)

### 2.3 `GET /api/node/list?active_only=true`

- **Purpose**: list active nodes (heartbeat fresh by default)
- **Response (200)**:
  ```json
  {
    "count": 2,
    "active_only": true,
    "nodes": [
      {
        "node_id": "m1",
        "host": "127.0.0.1", "port": 9101,
        "capabilities": ["shell", "claude-p", "git"],
        "load": 2.5,
        "last_heartbeat_age_s": 0.0,
        "registered_at": 1783309949.846792
      }
    ]
  }
  ```
- Query `active_only=false` returns all known nodes (excluded ones show with `last_heartbeat_age_s > 90`).

### 2.4 `GET /api/node/{node_id}`

- Returns single node detail. 404 if not found.

### 2.5 `GET /api/health`

- Bus liveness check. Always 200 unless catastrophic failure.

## 3. Capability Tags

Convention (L1/L2/L3 tiers):

- **L1 (basic)**: `shell`, `git`, `python`, `docker`, `make`
- **L2 (LLM)**: `claude-p`, `glm-5`, `deepseek-v4-flash`, `ollama-bge-m3`
- **L3 (specialized)**: `browser`, `gpu`, `cron`, `ssh-remote`, `feiniu`

**Free-form**: any string is accepted. Convention is informational, not enforced.

## 4. Authentication (mTLS)

> **Red Line 19** (enforced): all cross-device calls MUST be authenticated.

### 4.1 Why mTLS (not Bearer token)

- **6 agentmesh projects surveyed** (2026-07): **0/6 implement auth**.
- Clawmed-ai's `cli/connection.py`: no auth, no message signing.
- mTLS = mutual TLS, both client and server validate certs.

### 4.2 Cert setup (PoC)

```bash
# 1. Generate CA
openssl genrsa -out /tmp/ccc-ca.key 2048
openssl req -x509 -new -nodes -key /tmp/ccc-ca.key \
  -days 365 -out /tmp/ccc-ca.crt

# 2. Per-node cert (each node gets unique cert signed by CA)
openssl genrsa -out /tmp/<node>-key.pem 2048
openssl req -new -key /tmp/<node>-key.pem -out /tmp/<node>-csr.pem
# Sign by CA
openssl x509 -req -in /tmp/<node>-csr.pem \
  -CA /tmp/ccc-ca.crt -CAkey /tmp/ccc-ca.key \
  -out /tmp/<node>-cert.pem -days 90

# 3. cluster-bus loads:
#    ssl_keyfile=/tmp/ccc-ca.key  ssl_certfile=/tmp/ccc-ca.crt
#    ssl_ca_certs=/tmp/ccc-ca.crt   (for client cert verification)
```

### 4.3 cluster-bus.py — mTLS not yet wired (TODO P1-1 extension)

Current v0.1.0 binds `0.0.0.0:9100` **plaintext**. mTLS upgrade is part of P1-2 work.

**Temporary rules**:
- Bind only to **trusted network** (RFC1918)
- Skip mTLS on `127.0.0.1` only (dev mode)
- Disable cluster-bus on public networks until mTLS shipped

## 5. Error Codes

| Code | Meaning | Recovery |
|------|---------|----------|
| 200 | OK | — |
| 201 | Created | — |
| 400 | Bad request | Fix payload |
| 401 | Unauthenticated | Add cert / token |
| 404 | Node not registered | POST /api/node/register first |
| 409 | Conflict (re-register OK) | Pass |
| 410 | Node offline too long | Re-register + heartbeat |
| 422 | Validation failed | Check field constraints |
| 500 | Internal error | Check bus logs at stderr |
| 503 | Bus shutting down | Retry after restart |

## 6. Examples (curl)

```bash
# Register a node
curl -X POST http://127.0.0.1:9100/api/node/register \
  -H 'Content-Type: application/json' \
  -d '{"node_id":"m1","host":"127.0.0.1","port":9101,"capabilities":["shell","claude-p","git"]}'

# Heartbeat (every 30s)
curl -X POST http://127.0.0.1:9100/api/node/heartbeat \
  -H 'Content-Type: application/json' \
  -d '{"node_id":"m1","load":2.5}'

# List active nodes
curl http://127.0.0.1:9100/api/node/list

# Get single node
curl http://127.0.0.1:9100/api/node/m1
```

## 7. Examples (Python)

```python
import urllib.request, json

req = urllib.request.Request(
    "http://127.0.0.1:9100/api/node/register",
    method="POST",
    headers={"Content-Type": "application/json"},
    data=json.dumps({
        "node_id": "m1", "host": "127.0.0.1", "port": 9101,
        "capabilities": ["shell", "claude-p", "git"]
    }).encode(),
)
resp = urllib.request.urlopen(req)
print(json.loads(resp.read()))
```

## 8. Sizing & Limits

| Metric | Soft limit | Hard limit |
|--------|-----------|-----------|
| Node count | 100 | 1000 |
| Capability tags per node | 20 | 100 |
| Heartbeat TTL | 90s default | tunable |
| Concurrent connections | 50 | 200 |
| Single request body | 4 KB | 1 MB |

## 9. Versioning

- **v1.0.0** (2026-07-06): Initial release — nodes + heartbeat + dispatcher
- **v1.1**: mTLS (planned P1-2+)
- **v1.2**: chunk_id idempotency in commit messages (red line 15)

## 10. Related

- `references/red-lines.md` — Red Line 18 (capability default open), 19 (independent verifier), 20 (bash v3 portability)
- `docs/lessons.md` — Lesson 27 (claude -p), 29 (bash portability), 30 (independent verifier)
- `DESIGN-VALIDATION.md` — v1.0 design rationale
