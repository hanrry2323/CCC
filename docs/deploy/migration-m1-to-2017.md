# 迁移：M1 自用 → Mac2017 服务端

> **历史文档**：记录从 M1 单机开发迁至 Mac2017 服务端+CCC Relay 的操作。  
> **注意**：**2026-08-01 Relay 清理后**，relay 代码已从 CCC 仓拆出，Mac2017 不再运行 relay 实例。
> 所有 relay 请求走 M1 的 ai-loop-router（`~/program/ai-loop-router`，端口 4100/4102）。  
> 拓扑见 [`topology.md`](topology.md)。  
> **当前状态**：M1 = 对话脑（Desktop + sidecar + loop-code + ai-loop-router），Mac2017 = 编排手（Hub + Board + Engine）。

---

## 目标（历史参照）

| 组件 | 迁前（M1） | 迁后（2017） |
|------|------------|--------------|
| CCC Relay（`:4000`/`:4002`） | M1 本机（旧 ai-loop-router） | **2017 生产实例** `com.ccc.relay.2017`（注意：M1 保留本地 `com.ccc.relay.m1` 供对话热路径使用） |
| CCC Hub / Board / Engine | 常驻 M1 | **唯一生产服务** |
| 业务工作区（Engine） | 多仓舰队 | `apps/ccc-demo`（重置后） |

**2026-08-01 更新**：上述 relay 部分已过时。当前 relay 改为 M1 单实例 ai-loop-router（`:4100`/`:4102`），2017 通过 LAN 连接。

---

## 纪律

1. 同一时刻只一台引擎、只一台 relay 接生产流量  
2. 先起 2017 → 再切客户端 → 最后停 M1（避免空窗）  
3. 密钥收至 `~/.ccc/relay/upstreams.json`，只留服务端  

---

## 步骤（历史参照）

### 0. 前置条件

按 [`server-layout.md`](server-layout.md) 清理重组 `~/program`；`git clone CCC`；建 `apps/ccc-demo`。  
确保 Node ≥ 18（relay 编译需 `npm ci && npm run build`）。

### 1. 部署 CCC Relay（2017）— 已废弃

详见 [`../relay/DEPLOY-2017.md`](../relay/DEPLOY-2017.md)（**此文档已标记废弃**，2017 不再部署 relay）。

关键步骤摘要（历史）：
1. `cd ~/program/CCC && npm ci && npm run build`
2. 配置 `~/.ccc/relay/upstreams.json`（三档 `flash`/`Pro`/`code` 密钥）
3. 安装 launchd plist：`bash scripts/install-relay-plist.sh --start --host 2017`
4. 验证：`curl http://127.0.0.1:4000/admin/status` 应 200

### 2. Engine 接入 relay

Engine 启动时自动读 `AGENT_PLANNER_BASE_URL=http://192.168.3.140:4100`（M1 ai-loop-router）。  
`OPENCODE_MODEL=loop/flash` 走 `:4102` 出口。

### 3. CCC 服务启动（2017）

```bash
bash scripts/ccc-autostart-guard.sh enable --start
# 顺序：relay 先起（M1）→ Engine 后起（2017）
```

验收：`launchctl list | grep ccc.engine` 在列；看板 demo 任务能进闭环。

### 4. M1 停止旧服务

对话通过 sidecar 走本机 ai-loop-router `:4100`；不再需要 2017 端口直连。  
旧 `com.ai-loop-router` plist 已退役清理。