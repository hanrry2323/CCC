# CCC 配置系统

## 配置文件

- **默认模板**: `templates/ccc-config.sh` — CCC 仓库自带，提供所有默认值
- **项目配置**: `<workspace>/.ccc/config.sh` — 每个项目可自定义覆盖

## 加载顺序

```
1. CCC 默认模板 templates/ccc-config.sh
2. 项目 .ccc/config.sh（如果存在，覆盖默认值）
3. 环境变量（如果有，运行时覆盖）
```

`install-ccc-roles.sh` 安装 plist 时自动按此顺序加载。
`ccc-board-server.py` 读取 `BOARD_PORT` / `BOARD_HOST` 环境变量。

## 完整变量表

### 路径

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CCC_HOME` | `/Users/apple/program/CCC` | CCC 项目家目录 |
| `CCC_CONTRACT_DIR` | `.ccc` | 契约文件目录（plan/phases/verdict/report） |

### 看板 HTTP 服务

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BOARD_PORT` | `7777` | 看板 HTTP 端口 |
| `BOARD_HOST` | `127.0.0.1` | 绑定地址（`0.0.0.0` 开局域网） |

### 角色频率（interval-based）

| 角色 | 变量 | 默认值（秒） | 实际 |
|------|------|-------------|------|
| product | `PRODUCT_INTERVAL` | 14400 | 4h |
| dev | `DEV_INTERVAL` | 600 | 10min |
| reviewer | `REVIEWER_INTERVAL` | 7200 | 2h |
| tester | `TESTER_INTERVAL` | 14400 | 4h |
| ops | `OPS_INTERVAL` | 1800 | 30min |

### 角色频率（calendar-based）

| 角色 | 变量 | 默认值 | 说明 |
|------|------|--------|------|
| kb | `KB_HOUR` / `KB_MINUTE` | `23` / `0` | 每晚 23:00 |
| regress | `REGRESS_HOUR` / `REGRESS_MINUTE` | `23` / `30` | 每晚 23:30 |

### 角色定义

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ROLES` | `(product dev reviewer tester ops kb regress)` | 7 个角色的 bash 数组 |

### 后端 agent

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENCODE_BIN` | `opencode` | opencode CLI 路径 |
| `OPENCODE_MODEL` | `loop/flash` | opencode 使用的模型 |

### 重试

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEV_MAX_RETRY` | `3` | dev 角色最大重试次数 |

### Agent planner

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AGENT_PLANNER` | `claude` | planner 使用的 CLI |
| `AGENT_PLANNER_BASE_URL` | `http://127.0.0.1:4000` | 中转站地址 |

## 自定义示例

创建 `<project>/.ccc/config.sh`：

```bash
# ── 自定义频率 ──
export DEV_INTERVAL=1200          # 改为 20min
export PRODUCT_INTERVAL=21600     # 改为 6h
export KB_HOUR=22                 # kb 改为 22:00
export KB_MINUTE=0

# ── 自定义角色（可选）──
ROLES=(product dev reviewer)
```

## 提示

- 不改 `templates/ccc-config.sh`，覆盖请用项目 `.ccc/config.sh`
- 改 plist 后需重跑 `install-ccc-roles.sh` 生效
- 看板端口改完后重启 `ccc-board-server` 即可，不需重装 plist
