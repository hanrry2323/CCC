# `cluster-bus.py` — v1.0 Cluster Bus + Node Registry + Heartbeat

> CCC v1.0 集群总线的 FastAPI 实现。监听 node 注册/心跳/PoC 派单，提供 node 列表查询。

## 用途

P0-1 落地：让 M1 / mac2017 / feiniu 等多个 node 在同一 cluster bus 上注册 + 30 秒一次心跳，超时 90 秒判定 dead。

## 用法

```bash
python3 scripts/cluster-bus.py           # 默认 0.0.0.0:9100
python3 scripts/cluster-bus.py --port 8888
```

## Endpoints (5)

| Method | Path | 用途 |
|--------|------|------|
| POST | `/api/node/register` | 注册 node + capabilities (201) |
| POST | `/api/node/heartbeat` | 30s 心跳 (200) |
| GET | `/api/node/list` | 列出 active nodes (heartbeat fresh) |
| GET | `/api/node/{node_id}` | 单 node 详情 |
| GET | `/api/health` | bus liveness |

## Anti-restart 丢失

- In-memory dict 60s 自动 checkpoint 到 `/tmp/ccc-cluster-bus.json`
- 启动时自动 restore
- nodes self-recover via 心跳（无需外部 trigger）

## Capability Tags 约定

参考 `references/cluster-protocol.md` § 3:
- L1: shell / git / python
- L2: claude-p / glm-5
- L3: browser / gpu / cron

## Exit codes

- 0: graceful shutdown (SIGINT/SIGTERM handled)
- 其他: process exit

## Example

```bash
# 启动 bus
python3 scripts/cluster-bus.py &
# INFO: Uvicorn running on http://0.0.0.0:9100

# 注册 m1
curl -X POST localhost:9100/api/node/register \
  -d '{"node_id":"m1","host":"127.0.0.1","port":9101,"capabilities":["shell","claude-p","git"]}'
# → {"node_id":"m1","status":"registered","at":1783309949.846}

# 心跳
curl -X POST localhost:9100/api/node/heartbeat \
  -d '{"node_id":"m1","load":2.5}'
# → {"node_id":"m1","ack_at":1783309949.887}

# 列出
curl localhost:9100/api/node/list
# → {"count":1, "nodes":[{...}]}
```

## 关联

- `references/cluster-protocol.md` (完整协议规范)
- `scripts/ccc-dispatch.py` (PoC 派单消费此 bus)
- `tools/cluster-doctor.sh` (诊断工具)
- `tests/cluster/test-capability-required.py` (红线 18 enforcement)
