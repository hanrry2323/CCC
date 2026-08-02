# 节点/路径域

> 来源：T9 种子包 `01-nodes-paths.json`（qx-map `cluster/path-authority.md` + `cluster/cluster.json`）
> 导入日期：2026-08-02 · 更新：知识库独立维护后在此标注变更

## 机器节点

| 机器 | IP | OS | RAM | SSH 用户 | 访问方式 |
|------|-----|-----|-----|---------|---------|
| M1（本机） | 192.168.3.140 | macOS 26.5.2 arm64 | 8GB | apple | 本地 shell |
| Mac2017 | 192.168.3.116 | macOS 13.7.8 x86_64 | 16GB | fan | `ssh fan@192.168.3.116`（密钥 `~/.ssh/id_ed25519_xianyu`） |
| HP | 192.168.3.131 | Ubuntu 25.10 | 11GB | hp | `ssh hp@192.168.3.131`（密钥 `~/.ssh/id_ed25519_hp`） |
| Windows | 192.168.3.252 | Windows | — | win | `ssh win@192.168.3.252`（密钥 `~/.ssh/id_ed25519`） |

## 各机器服务

### M1（开发机 + Codex 驻场）
- Codex Desktop
- ai-loop-router :4100/:4102（loop-router，智能路由）
- ccc-relay-runtime :4000（CCC relay，与 loop-router 独立）
- postgres :5432
- ccc-chat-server :7777（localhost）
- ccc-agent-sidecar :7788

### Mac2017（重活节点 + qb 本体）
- qx-observer :7777
- xianyu :8080
- redis :6379

### HP（存储 + 知识库服务）
- mcp-server :8083（知识库 MCP 唯一入口）
- memory-store :8082
- postgres :5432
- ollama（4 models，not for prod embedding）
- medio-server

## 两套 relay 分清

| | loop-router | ccc-relay |
|--|-----------|-----------|
| 代码仓 | `/Users/apple/program/ai-loop-router` | `/Users/apple/.ccc/relay-runtime`（另有 Mac2017 副本） |
| M1 端口 | 4102 | 4000 |
| 上游 | opencode/minimax/zhipu 直连 | CCC relay（opencode） |
| Codex 当前是否用 | 是（model_provider=loop-router） | 否 |
| 职责 | Codex 走的智能路由 | CCC 产线的中转 |

**禁止**把 4000 当 4102 的下一跳，它们是两条独立 relay。

## HP 知识库

| 服务 | 位置 | 端口 | 说明 |
|------|------|------|------|
| mcp-server | HP | 8083 | 知识库 MCP 唯一入口 |
| memory-store | HP | 8082 | 记忆存储 |
| 知识数据 | HP `/data/knowledge/` | — | 权威知识在 HP，M1 仅索引 |

## 路径幻觉检查规则

1. 本机路径：`ls -d` 当场验证，不存在则不写
2. 集群路径：`ssh <host> 'ls -d ...'` 当场验证
3. SMB 路径：确认 `/Volumes/fan` 挂载再引用；卸载时改用 ssh
4. 旧快照：cluster.json 等过 3 天以上先重验再信
5. 写任何项目文档前对照本表；本表没有的路径 = 先查证再落盘