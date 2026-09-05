# Stage 8: Relay 中转站清理方案

## 一、概述

### 目标
1. **删除 Mac2017 上的中转站代码**（CCC 仓内 `relay/` 目录）
2. **Mac2017 全部使用 M1 的 ai-loop-router**（端口 4100/4102）
3. **CCC Desktop 也使用 ai-loop-router**（端口 4100/4102）
4. **CCC 项目中的中转站代码全部拆出**，清理干净
5. **文档先行**，修改所有相关文档并标注问题

### 背景
当前存在 **两套** relay 代码：
- **ai-loop-router**（`/Users/apple/program/ai-loop-router`）：原始独立中转站，v4.5.1，端口 4100/4102，已 STABLE FREEZE
- **CCC relay/**（`/Users/apple/program/CCC/relay/`）：从 ai-loop-router 复制并入 CCC 的副本，v4.3.0，端口 4000/4002

两套代码功能完全相同，CCC relay/ 是 ai-loop-router 的过时副本。维护两套代码造成混乱，且 Mac2017 运行 `com.ccc.relay.2017` 实例增加运维负担。

---

## 二、当前状态分析

### 2.1 代码分布

| 位置 | 说明 | 端口 | 实例 |
|------|------|------|------|
| `~/program/ai-loop-router/` | 独立项目，原始中转站 | 4100/4102 | M1 可运行 |
| `~/program/CCC/relay/` | CCC 仓内副本，待删除 | 4000/4002 | M1: `com.ccc.relay.m1`，2017: `com.ccc.relay.2017` |

### 2.2 当前 relay 连接拓扑

```
M1 桌面端 → sidecar → 本机 relay :4000 (com.ccc.relay.m1)
2017 Engine → 本机 relay :4000 (com.ccc.relay.2017) → Claude product
2017 OpenCode → 本机 relay :4002 (com.ccc.relay.2017) → code tier
```

### 2.3 目标拓扑

```
M1 桌面端 → sidecar → 本机 ai-loop-router :4100 (flash)
2017 Engine → M1 ai-loop-router http://192.168.3.140:4100 → Claude product
2017 OpenCode → M1 ai-loop-router http://192.168.3.140:4102 → code tier
```

### 2.4 关键文件清单

**需要修改的代码文件（CCC 仓内）：**

| 文件 | 当前值 | 需改为 |
|------|--------|--------|
| `scripts/_utils.py:72` | `_DEFAULT_AGENT_PLANNER_URL = "http://127.0.0.1:4000"` | `http://127.0.0.1:4100` |
| `scripts/_utils.py:122,132` | `port = 4000`（relay_is_up 默认） | `port = 4100` |
| `scripts/_config.py:92` | `base_url: str = "http://127.0.0.1:4000"` | `http://127.0.0.1:4100` |
| `scripts/_config.py:142` | `relay_base_url: str = "http://127.0.0.1:4000"` | `http://127.0.0.1:4100` |
| `scripts/ccc-agent-sidecar.py:332` | `_RELAY_BASE = "...:4000"` | `...:4100` |
| `scripts/ccc-relay-flash-watchdog.sh:12` | `RELAY_URL="${CCC_RELAY_URL:-http://127.0.0.1:4000}"` | M1 IP `http://192.168.3.140:4100` |
| `scripts/install-relay-flash-watchdog-plist.sh:37` | `http://127.0.0.1:4000` | M1 IP `http://192.168.3.140:4100` |
| `scripts/install-relay-flash-watchdog-plist.sh:39` | `com.ccc.relay.2017` | 无需 relay 标签，改为 watchdog 目标 |
| `scripts/install-relay-plist.sh` | 安装 CCC relay plist（M1/2017） | 整个文件删除或改造为 ai-loop-router plist |

**需要删除的代码目录：**

| 路径 | 说明 |
|------|------|
| `relay/` | 整个目录（CCC 仓内中转站副本） |

**需要修改的文档：**

| 文档 | 修改内容 |
|------|----------|
| `docs/deploy/topology.md` | 更新 relay 端口为 4100/4102，删除 M1 relay 实例，2017 指向 M1 |
| `docs/deploy/migration-m1-to-2017.md` | 删除 relay 迁移部分，标注历史文档 |
| `docs/relay/KEY-POOL.md` | 更新拓扑，M1 为唯一 relay 节点 |
| `docs/relay/DEPLOY-2017.md` | 标记为废弃，不再需要 2017 部署 relay |
| `docs/product/loop-engineer-authority.md` | 更新 CCC Relay 章节，M1 单实例 |
| `docs/executors/overview.md` | 更新 relay 连接信息 |
| `docs/briefs/2026-07-27-relay-handoff.md` | 更新拓扑 |

---

## 三、变更方案

### WP1: 文档先行（先改文档，再改代码）

**文件：全部文档列表**

逐个修改文档，核心变更内容：
1. 所有 `:4000` 引用改为 `:4100`
2. 所有 `:4002` 引用改为 `:4102`
3. 删除 `com.ccc.relay.m1` / `com.ccc.relay.2017` 双实例描述
4. 改为单一 ai-loop-router 实例（M1，端口 4100/4102）
5. Mac2017 通过 `http://192.168.3.140:4100` 连接 M1 relay
6. 标注「CCC relay/ 已拆出，使用独立 ai-loop-router」
7. 删除 `relay/DEPLOY-2017.md` 内容，改为废弃说明

### WP2: 修改 CCC 代码中的 relay 连接配置

**文件：`scripts/_utils.py`**
- 将 `_DEFAULT_AGENT_PLANNER_URL` 从 `http://127.0.0.1:4000` 改为 `http://127.0.0.1:4100`
- 将 `relay_is_up()` 中的默认端口从 `4000` 改为 `4100`

**文件：`scripts/_config.py`**
- 将 `RelayEnv.base_url` 默认值从 `:4000` 改为 `:4100`
- 将 `AgentEnv.relay_base_url` 默认值从 `:4000` 改为 `:4100`

**文件：`scripts/ccc-agent-sidecar.py`**
- 将 `_RELAY_BASE` 默认值从 `:4000` 改为 `:4100`

### WP3: 删除 CCC 仓内 relay/ 目录

**操作：**
- 删除 `relay/` 整个目录（`git rm -r relay/`）
- 注意：`relay/.gitignore` 中 dist/、node_modules/ 等不入仓，只需删除入仓的 src/、tests/、scripts/、docs/、配置文件等

**影响分析：**
- `relay/` 是 ai-loop-router 的副本，功能完全由 ai-loop-router 替代
- 无其他 CCC 代码直接 import relay/ 中的 TypeScript 源码（所有交互通过 HTTP API）
- 不需要保留任何 relay/ 文件

### WP4: 更新 Mac2017 看门狗脚本

**文件：`scripts/ccc-relay-flash-watchdog.sh`**
- 将 `RELAY_URL` 默认值从 `http://127.0.0.1:4000` 改为 `http://192.168.3.140:4100`
- 将 `LABEL` 从 `com.ccc.relay.2017` 改为指向 M1 服务（无需重启 2017 实例，改为检测 M1 relay 可达性）

**文件：`scripts/install-relay-flash-watchdog-plist.sh`**
- 更新环境变量 `CCC_RELAY_URL` 为 `http://192.168.3.140:4100`
- 更新 plist 描述

### WP5: 处理 install-relay-plist.sh

**文件：`scripts/install-relay-plist.sh`**
- 此脚本安装 `com.ccc.relay.m1` 和 `com.ccc.relay.2017` plist
- 改为安装 ai-loop-router 的 plist（使用 `com.ai-loop-router` 标签，端口 4100/4102）
- 删除 --host 2017 支持（Mac2017 不再运行 relay 实例）
- 删除 `--host` 参数中 2017 分支
- 简化脚本：只安装 M1 本机 plist

### WP6: 清理残留引用

**搜索确认：**
- 全局搜索 `:4000` 和 `:4002` 在 CCC 代码中的硬编码引用
- 全局搜索 `com.ccc.relay` 引用
- 全局搜索 `ccc-relay` 引用
- 更新或删除对应的脚本、配置

**需要确认的脚本：**
- `scripts/ccc-autostart-guard.sh` → 检查是否引用 relay
- `scripts/_ccc_launchd.sh` → 检查是否引用 relay 标签
- `scripts/smoke-desktop-stable.sh` → 更新 relay 相关检查

### WP7: 配置 M1 的 ai-loop-router

**M1 操作：**
1. 确保 `~/program/ai-loop-router/upstreams.json` 配置正确（flash 通道）
2. 创建 launchd plist，标签 `com.ai-loop-router`，端口 4100/4102
3. 启动并验证：`curl http://127.0.0.1:4100/admin/status`

**注意：** ai-loop-router 已经有 `scripts/com.ai-loop-router.plist.example`，可直接使用或参考。

### WP8: 配置 Mac2017 环境变量

**Mac2017 操作：**
1. 删除 `com.ccc.relay.2017` plist：`launchctl bootout gui/$(id -u)/com.ccc.relay.2017`
2. 设置 Engine 环境变量指向 M1 relay：
   - `CCC_RELAY_BASE_URL=http://192.168.3.140:4100`
   - `AGENT_PLANNER_BASE_URL=http://192.168.3.140:4100`
   - `OPENCODE_MODEL=loop/flash`（OpenCode 自动用 `:4002` 逻辑，但需指向 M1）

---

## 四、决策与假设

### 决策
1. **保留 ai-loop-router 独立项目**，不合并回 CCC 仓
2. **Mac2017 不运行任何 relay 实例**，所有请求走 M1 relay
3. **使用 flash 通道**（单付费 Go 上游）
4. **端口 4100/4102**（ai-loop-router 默认端口，与旧 CCC 4000/4002 区隔）
5. **CCC 仓内 relay/ 目录完全删除**，不再保留

### 假设
1. M1 机器（192.168.3.140）7x24 在线，可被 Mac2017 访问
2. ai-loop-router 的 upstreams.json 配置已包含 flash 付费 key
3. 网络延迟：M1 → Mac2017 局域网内，额外延迟 <1ms，可忽略

### 风险与缓解
| 风险 | 缓解 |
|------|------|
| M1 关机导致全部 relay 不可用 | fail-open 机制已存在（`CCC_RELAY_DIRECT_URL`），可直连上游 |
| 网络延迟增加影响 Engine 性能 | 局域网延迟 <1ms，无影响 |
| 端口 4100/4102 被占用 | 检查并清理旧进程 |

---

## 五、验证步骤

### 5.1 M1 验证
```bash
# 1. 启动 ai-loop-router
cd ~/program/ai-loop-router && npm run build && npm start &

# 2. 验证双端口
curl -s http://127.0.0.1:4100/admin/status | head -5
curl -s http://127.0.0.1:4102/v1/models | head -5

# 3. 验证 flash 通道
curl -s -X POST http://127.0.0.1:4100/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":8,"messages":[{"role":"user","content":"hi"}]}' | head -5
```

### 5.2 Mac2017 验证
```bash
# 1. 验证能连 M1 relay
curl -s http://192.168.3.140:4100/admin/status | head -5

# 2. 验证 flash 通道
curl -s -X POST http://192.168.3.140:4100/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":8,"messages":[{"role":"user","content":"hi"}]}' | head -5

# 3. 确认旧 relay 已停止
curl -s http://127.0.0.1:4000/admin/status | head -3  # 应失败
```

### 5.3 CCC 验证
```bash
# 1. 确认 relay 目录已删除
ls ~/program/CCC/relay/  # 应不存在

# 2. 确认配置已更新
grep -r "4000" ~/program/CCC/scripts/_utils.py  # 应只有注释
grep -r "4000" ~/program/CCC/scripts/_config.py  # 应只有注释

# 3. 运行 CCC 健康检查
# （在 Mac2017 上）
python3 -c "from _utils import relay_is_up; print(relay_is_up('192.168.3.140', 4100))"
```

### 5.4 文档验证
```bash
# 确认无残留 :4000 引用（除历史注释）
grep -rn "4000" ~/program/CCC/docs/ --include="*.md" | grep -v "历史" | grep -v "DEPRECATED" | grep -v "退役"
```

---

## 六、执行顺序

1. **WP1: 文档先行** → 修改所有文档
2. **WP2: 修改代码配置** → 更改 _utils.py、_config.py、sidecar.py
3. **WP3: 删除 relay/ 目录** → git rm -r relay/
4. **WP4: 更新看门狗** → flash-watchdog 脚本
5. **WP5: 改造 install-relay-plist.sh** → 只支持 M1 的 ai-loop-router
6. **WP6: 清理残留** → 搜索并清理 :4000 引用
7. **WP7: M1 配置 ai-loop-router** → 启动服务
8. **WP8: Mac2017 配置** → 停旧 relay，设环境变量