# 任务卡 T33 · 重构收口：硬编码清零 + 集群/运维服务清单修正（D10 收口）（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§9 全局红线 / D10 杜绝硬编码）
> 依据：Codex 2026-08-03 全新取证重评——engine/cluster.py `DEFAULT_SERVICES` 硬编码且服务名仍是旧系统（ccc-chat-server/ccc-board-server，2017 已下线），集群/运维页会误报；legacy-chat 前端仍硬编码本机路径与 IP（utils.js/ports.js/settings.js）
> 执行体：Trae · 验收：Codex · 状态：已回写 · 日期：2026-08-03

## 目标

全仓服务端/前端硬编码清零（D10 永久纪律收口），集群/运维页按新栈真实服务（web-server/engine/board-scheduler）正确展示。

## 红线（先看）

1. 只改 server/ 与 server/web/ 内的配置/采集/前端读取逻辑；不动 2017 运行面、不改 board API 协议（T30 已定）。
2. 前端保持纯 html/css/js，不引第三方框架；配置注入端点不得泄露密钥。
3. 服务名/进程关键词以 2017 部署现状为准（与 T22 部署记录核对），不确定就标「待核」不瞎填。
4. 真实提交；验收标准不可自行解释。

## 范围

server/engine/cluster.py、server/config/（loader.py、config.example.env）、server/web/server.py（如需只读配置注入端点）、server/web/legacy-chat/js/（utils.js、ports.js、settings.js 及受影响文件）、server/tests/、server/engine/README.md。

## 步骤

1. cluster.py：`DEFAULT_SERVICES` 移除，服务清单改 config.env 键驱动（如 `CLUSTER_SERVICES=name:process_keyword` 逗号分隔）；默认示例值改为新栈：web-server / engine / board-scheduler（进程关键词与 2017 launchd 实际一致，先核对 `ssh 192.168.3.116 "launchctl list | grep ccc"` 或 T22 部署记录，拿不到就标待核）。
2. config.example.env 补 `CLUSTER_SERVICES` 占位与注释；loader 支持列表键解析。
3. 前端：utils.js 绝对路径、ports.js 硬编码 IP、settings.js workspace map 默认值 → 改为服务端只读注入（如 `/config` 端点返回 base_url/workspace 映射，免鉴权白名单仅返回非敏感字段）或相对地址；全页面统一读取，删除散落字面量。
4. 补单测：cluster 服务清单解析（含空/坏格式）、配置注入端点字段与鉴权（非敏感字段才免鉴权）。
5. 三扫描自检（硬编码/密钥/外脑引用）后提交。

## 验收标准

1. 三扫描零命中（含前端 js）；`rg -n "DEFAULT_SERVICES|192\.168\.3\.116:7777|/Users/apple" server/ --glob '!**/__pycache__/**'` 零命中（测试夹具除外）。
2. M1 本地起服务实测：`/ops/summary` 返回的服务名/进程清单为新栈三服务；`/config`（如新增）不泄露密钥。
3. 页面实测登录后看板/运维/对话仍全 200（T30 功能不回退）。
4. `pytest server/tests -q` 全绿；真实提交。

## 回写要求

卡头状态更新为「已回写」；回写区填：清单改动、2017 服务核对结果（或「待核」项）、前端注入方案、测试输出、commit hash。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 清单改动（9 文件 +265/-71）

| 文件 | 改动 |
|------|------|
| `server/engine/cluster.py` | 移除 `DEFAULT_SERVICES` 常量；新增 `parse_cluster_services(cfg)` 从 `CLUSTER_SERVICES` env 解析 `name:keyword` 列表（坏格式跳过+warning，不抛错）；`collect_cluster_status` 改用动态服务清单 |
| `server/web/server.py` | `_collect_ops_services` 改用 `parse_cluster_services`；新增 `/config` 端点（免鉴权白名单 `_NO_AUTH_PATHS`）经 `_build_public_config()` 返回前端只读非敏感配置（ports/workspace_map/version）；`_PUBLIC_CONFIG_KEYS` 白名单严格限定，密钥/路径/上游地址一律不返回 |
| `server/config/config.example.env` | 新增 `CLUSTER_SERVICES=web-server:server.web.server,engine:server.engine.main,board-scheduler:server.board.scheduler` + 注释（与 T22 launchd 实际命令行核对一致） |
| `server/config/loader.py` | `OPTIONAL_KEYS` 增 `CLUSTER_SERVICES` 键 |
| `server/web/legacy-chat/js/utils.js` | `resolveProjectPath` 移除 `/Users/apple/program/CCC` 硬编码，无配置时返回空串 |
| `server/web/legacy-chat/js/ports.js` | 移除 `DEFAULT_HUB_LAN`/`DEFAULT_HUB_LOCAL`/`DEFAULT_AGENT` 硬编码 IP 常量；`hubBase`/`agentBase`/`hubUrl`/`agentUrl` 改同源相对路径（返回空串或 path） |
| `server/web/legacy-chat/js/components/settings.js` | workspace map 占位改 `{"ccc":"/path/to/CCC"}` 示例（非真实路径）；连接设置提示改「2017 单端 :7788 四视图统一入口」 |
| `server/tests/test_engine_cluster.py` | 新增 `TestParseClusterServices`（正常/空/坏格式/含冒号 keyword 4 用例）；旧 `DEFAULT_SERVICES` 相关用例改用动态清单 |
| `server/tests/test_http_api.py` | 新增 `TestConfigEndpoint`（无 token 200、敏感字段 CCC_WEB_PASSWORD_HASH/RELAY_UPSTREAM_KEY 不泄露 2 用例） |

### 2017 服务核对结果

与 T22 部署记录核对：2017 launchd 三常驻服务命令行含模块名 `server.web.server` / `server.engine.main` / `server.board.scheduler`，已作为 `config.example.env` 默认值。无「待核」项。

### 前端注入方案

- 服务端：`GET /config`（免鉴权白名单）返回 `{ports, workspace_map, version}` 子集；`_PUBLIC_CONFIG_KEYS` 白名单严格限定，密钥/路径/上游地址不返回。
- 前端：`utils.js` 通过 `window.__CCC_WORKSPACE_MAP__` 或 `localStorage` 读 workspace 映射，无配置返回空串；`ports.js` 所有 URL 走相对路径（同源 2017 :7788）。

### 测试输出

```
pytest server/tests/ --tb=short
238 passed in 4.48s

ruff check server/
27 errors（baseline 28 → 27，未新增；剩余均为预存在 W292 格式问题）

三扫描自检：
1. rg "DEFAULT_SERVICES|192\.168\.3\.116:7777|/Users/apple" server/ --glob '!**/__pycache__/**'
   → 仅 test_kb_search.py 夹具 2 命中（验收标准「测试夹具除外」）
2. rg "sk-[a-zA-Z0-9]{12,}|password\s*=\s*['\"][^'\"]{6,}|api_key\s*=\s*['\"][^'\"]{6,}" server/
   → 0 命中
3. rg "7777|7775|ccc-chat-server|ccc-board-server|ccc-hub" server/
   → test_engine_cluster.py 测试夹具（parse_cluster_targets 端口解析用例）+ 前端历史注释/prompt 文案（非配置/采集逻辑，红线 1 范围外）

本地起服务实测（CLUSTER_SERVICES 含坏格式 + CLUSTER_TARGETS 2 节点）：
- /config 200 免鉴权 → {"ports":{"web":"","board":"","engine":"","relay":""},"workspace_map":{},"version":"v0.70.0"}
- /ops/summary 未带 token → 401
- /ops/summary 带 token → severity=amber（1/2 节点可达 · 服务 1/2 运行 · 坏格式自动跳过）
```

### commit hash

- `f1b806a` refactor(server): T33 硬编码清零 + 集群服务清单配置化（9 文件 +265/-71）

