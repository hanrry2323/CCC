# web/ — 看板静态页 + HTTP API

> 施工卡：T3（静态页）· T13（HTTP API）· 依赖：`board/` 导出数据（`web/data/board.js`）

## 职责

- 看板 UI：三视图切换——实时（按状态）、7 天回写、按项目分类。
- 线路图占位（P3 派生视图前置壳）：未开发 / 开发中 / 已开发待验收 / 已验收待确认 / 确认可用 / 有问题。
- 顶部状态徽章（契约 §2 各状态计数）；深/浅主题可切换（视觉沿用架构全景页令牌）。
- HTTP API 服务（可选）：提供 5 个 GET 只读接口，数据与静态导出同源。

## 关键约定

- **数据源可切换**：页面支持「本地 board.js / HTTP API」两种来源（URL 参数 `?api=http://host:port` 决定），API 不可用时回退本地数据。
- **API 模式鉴权**：T16 起所有 `/board/*` 接口需 Bearer token；页面通过 `?token=<token>` 参数注入鉴权头（token 由 `POST /session` 换取）。无 token 时接口 401，页面静默回退本地 `board.js`。
- **零 API 模式**：无 `?api` 参数时，数据以 `window.BOARD_DATA = {...}` 变量注入（`data/board.js`），`file://` 可直接打开。
- 页面不直连 `board/` 内部；数据由 `board/export.py` 或 HTTP API 提供。
- 视觉沿用架构全景页（`docs/ccc-refactor-architecture.html`）CSS 令牌与深/浅主题。

## 内容

| 文件 | 职责 |
|------|------|
| `index.html` | 页壳：顶栏 + 状态徽章 + 主题开关 + 四标签 + 视图区 |
| `css/style.css` | 深/浅主题令牌 + 卡片/徽章/线路图样式 |
| `js/app.js` | 渲染数据三视图 + 线路图 + 徽章 + 主题切换；支持 API 数据源 |
| `data/board.js` | **导出产物**（`window.BOARD_DATA`），由 `board/export.py` 生成 |
| `server.py` | **HTTP API 服务端**（零依赖，Python stdlib） |

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `board/` | 消费 `export.py` 产出的 `data/board.js`，不 import；`server.py` 调用 `board.queries` |
| `engine/` | 不依赖 |
| `config/` | `server.py` 端口走 `--port` 参数 / `WEB_PORT` 环境变量 |

## HTTP API

### 启动

```bash
python3 -m server.web.server --port 9999
```

默认端口 0（随机端口，仅测试用）。生产部署必须指定端口并配置鉴权。

### 接口

| 方法 | 路径 | 响应 | 说明 |
|------|------|------|------|
| GET | `/health` | `{"status": "ok"}` | 健康检查（无鉴权） |
| POST | `/session` | `{token, expires_at, ttl_s}` | 账号密码换 token（无鉴权） |
| GET | `/board/realtime` | `{状态名: [明细...]}` | 实时视图（按状态分组，需 Bearer token） |
| GET | `/board/recent` | `[明细...]` | 7 天回写视图（按回写时间倒序，需 Bearer token） |
| GET | `/board/by_project` | `[{project, count, states}]` | 按项目分类（需 Bearer token） |
| GET | `/board/roadmap` | `{overview, by_project}` | 线路图聚合（需 Bearer token） |
| GET | `/board/states` | `{状态名: 计数}` | 状态徽章计数（需 Bearer token） |
| POST | `/conversation` | `{reply}` | 对话回声占位（需 Bearer token，接大脑留接口） |
| GET | `/conversation` | `{messages: [...]}` | 对话历史（需 Bearer token） |

### 响应示例

```json
GET /health → {"status": "ok"}
GET /board/realtime → {"待分派": [{"id": "T1", "title": "...", "state": "待分派", ...}]}
GET /board/recent → [{"id": "T2", "written_at": "2026-08-02", ...}]
GET /board/by_project → [{"project": "INT-120", "count": 3, "states": {"待分派": 1, "已回写": 2}}]
GET /board/roadmap → {"overview": [{"bucket": "未开发", "count": 1}, ...], "by_project": [...]}
```

### 鉴权（T16 已实现）

> 所有 `/board/*` 与 `/conversation` 接口均需 `Authorization: Bearer <token>`；`/health` 与 `/session` 免鉴权。

- 账号/密码/有效期走环境变量：`CCC_WEB_USERNAME` / `CCC_WEB_PASSWORD_HASH`（SHA-256）/ `CCC_WEB_TOKEN_TTL`，不落库、不硬编码（占位见 `config/config.example.env`）。
- token 由 `POST /session` 签发（HMAC-SHA256，内存 store，过期即拒）；生产建议改用持久化/签名 token 方案。
- 前端 API 模式通过 `?token=<token>` 注入鉴权头；无 token 时接口 401 并回退本地 `board.js`。
- 鉴权未配置时 `POST /session` 返回 500「server auth not configured」（预期行为）。

## 施工入口

- 重新导出：`$PYTHON_BIN -m server.board.export`（扫描 `docs/dispatch/` → 重写 `data/board.js`）。
- 启动 API：`python3 -m server.web.server --port 9999`。
- P3：在线路图区块接入「确认可用」交互（人只做确认）。
- 壳对接：HTTP API 接入 7788 对话口与桌面端（后续卡）。
