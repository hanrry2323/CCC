# web/ — HTTP 前端

> 施工卡：T3（与 T2 并行，目录不相交）· 依赖：`board/` 查询接口、`config/`

## 职责

- 看板 UI：实时刷新、7 天视图、项目分类。
- API 端点：供前端消费的只读/操作接口（聚合 `board/` 查询）。
- 线路图占位（P3 派生视图的前置壳）。

## 关键约定

- 端口来自 `config.env`（`WEB_PORT`），监听地址走环境变量，不写死。
- 前端不直连 `board/` 内部，只消费 `web/` 暴露的 API。
- UI 状态自动聚合，人只做「确认可用」（P3 方向，T3 先留接口位）。

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `board/` | 读 board 查询接口（数据源） |
| `engine/` | 不直接依赖；如需触发派发走 API 约定 |
| `config/` | `WEB_PORT` 等运行参数 |

## T3 施工入口

1. `server/web/app.py`：HTTP 服务（读 `WEB_PORT`）。
2. `server/web/routes.py`：/board 实时、/7days、/projects 路由。
3. `server/web/static/`：SPA 壳 + 组件。
4. 与 `board/` 查询接口联调，冒烟测试落 `tests/`。
