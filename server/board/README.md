# board/ — 看板服务端

> 施工卡：T2（服务端数据结构与查询）· 被依赖：`web/`（T3 前端只读本模块查询接口）· 依赖：`config/`

## 职责

- 任务板数据模型：epic / work、阶段五态、epic split 状态。
- 查询接口：按状态、按项目、按时间（7 天）聚合。
- 状态机：承接 `engine/` 的状态更新，保证一致性。

## 关键约定

- 数据契约对齐 `references/board-task-schema.md`（跨 IDE 契约），不另造格式。
- 状态枚举：`planned / in_progress / testing / verified / released`；epic `pending → planned → running → done / failed`。
- **只做数据与查询，不做决策**；派发/调度归 `engine/`，board 不产生任务。

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `engine/` | engine 调 board 写入状态更新 |
| `web/` | T3 前端只读 board 查询接口（实时 / 7 天 / 项目分类），不直接 import |
| `config/` | `BOARD_PORT` / `DATA_DIR` 由 `loader.load_config` 提供 |

## T2/T3 施工入口

- T2：`server/board/models.py`（数据结构）+ `server/board/store.py`（查询/聚合）。
- T3：`web/` 只经 API 读本模块查询接口。
