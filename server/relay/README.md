# relay/ — 中转站

> 施工卡：T4 · 依赖：`config/`（`RELAY_UPSTREAM_URL` / `RELAY_UPSTREAM_KEY`）· 被依赖：`engine/`

## 职责

- 模型出口上游路由：把 engine/执行的模型调用路由到配置的上游。
- 密钥管理：上游密钥只允许占位引用（`RELAY_UPSTREAM_KEY`），不落明文。
- 调用方切换（M4 前置）：CCC 自带中转站就绪并切换后再停旧中转站。

## 关键约定

- 上游地址/密钥全部来自 `config.env`，代码零字面量。
- 不感知具体模型/工具名；只做路由与鉴权。
- 切换纪律（红线）：先部署 CCC 自带中转站 → 切换调用方 → 再停旧站；顺序不可反。

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `engine/` | engine 出模型时经 relay 路由 |
| `config/` | 读 `RELAY_UPSTREAM_URL` / `RELAY_UPSTREAM_KEY` |
| `deploy/` | T4 落地部署以 deploy 模板为基础 |

## T4 施工入口

1. `server/relay/client.py`：上游客户端（地址/密钥来自 config）。
2. `server/relay/router.py`：路由决策（逻辑名 → 上游）。
3. 部署 + 调用方切换（运行面，最后单独做，需管理席许可）。
