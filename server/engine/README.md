# engine/ — 薄驱动核心

> 施工卡：T2 · 依赖：`config/`（已就绪）· 被依赖：`web/`、`deploy/`、`tests/`

## 职责

- 读取 `config/executors.json`（契约 §7 注册表），决定任务派发给谁。
- 发单：把待办任务变为可执行 work；派发：按执行体「分类」选择自动拉起（可后台 CLI）或挂起等人（手动 GUI）。
- 收单：读取执行结果，更新状态（planned → in_progress → testing → verified → released）。
- 状态更新对接 `board/` 数据结构，保证看板一致。

## 关键约定

- **只做编排，不做执行**：`engine/` 不含任何具体工具逻辑；工具名只存在于注册表配置。
- 派发规则：`可后台 CLI` → Engine 直接拉起；`手动 GUI` → 只发单、等人工接单；管理席/验收席不参与派发。
- 状态机沿用 CCC 看板契约：`planned / in_progress / testing / verified / released`；epic 侧 `pending → planned → running → done / failed`。
- 模型出口一律经 `relay/`，engine 不直连上游。

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `config/` | 经 `loader.load_config` 读运行参数；读 `EXECUTOR_REGISTRY_PATH` 指向的注册表 |
| `relay/` | 出模型时调 relay 路由（T4 落地，T2 先留接口） |
| `board/` | 状态更新写入 board 数据结构 |
| `deploy/` | `run.example.sh` 以 `$PYTHON_BIN -m server.engine.main --config …` 启动本模块入口 |

## T2 施工入口

1. `server/engine/main.py`：入口——`--config` → `load_config` → 主循环。
2. `server/engine/dispatch.py`：注册表读取 + 派发决策（分类 → 拉起/挂起）。
3. `server/engine/task.py`：work 数据结构（id / 角色 / 状态 / 结果）。
4. 状态更新对接 `board/`；单测落 `tests/test_engine_*.py`。
