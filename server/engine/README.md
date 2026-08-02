# engine/ — 薄驱动核心

> 施工卡：T2（本卡）· 依赖：`config/`（已就绪）· 被依赖：`web/`、`deploy/`、`tests/`

## 职责

- 读取 `config/executors.json`（契约 §7 注册表），决定任务派发给谁。
- 发单：把待办任务变为可执行 work；派发：按执行体「分类」选择自动拉起（可后台 CLI）或挂起等人（手动 GUI）。
- 收单：读取执行结果，按契约 §2 更新状态（执行中 → 已回写 / 打回）。
- 状态更新写入看板接口（`store.py`），T3 前用内存实现。

## 关键约定

- **只做编排，不做执行**：`engine/` 不含任何具体工具逻辑；工具名只存在于注册表配置；T4 前不真拉执行体，只写「模拟拉起」日志。
- 派发规则（契约 §7 → §2）：`可后台 CLI` → Engine 自动拉起；`手动 GUI` → 挂起等人；管理席/验收席（分类「—」）与未知角色 → 不派发。
- 状态机 = **契约 §2 五态**：`待分派 → 执行中 → 已回写 → 已关闭`；失败路径 `执行中/已回写 → 打回（附问题清单）`，人工处理后 `打回 → 待分派` 重新派发；终态 `已关闭`。**非法状态转移一律抛 `IllegalTransitionError`。**
- 模型出口一律经 `relay/`，engine 不直连上游。

## 实现（T2 本卡产出）

| 文件 | 职责 |
|------|------|
| `task.py` | `Work` 数据结构 + 契约 §2 状态机（合法/非法转移） |
| `dispatch.py` | 注册表读取（§7 字段/分类校验）+ `decide()` 派发决策 |
| `store.py` | 看板对接接口 `BoardStore` + 内存实现 `InMemoryBoardStore`（T3 前占位） |
| `main.py` | 入口：`--config` → `load_config`；`--once` 单次扫描+收单；无 `--once` 持续循环+心跳 |

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `config/` | 经 `loader.load_config` 读运行参数；读 `EXECUTOR_REGISTRY_PATH` 指向的注册表 |
| `relay/` | 出模型时调 relay 路由（T4 落地，T2 先留接口） |
| `board/` | 状态更新写入 `store.py` 看板接口（T3 换真实数据结构，不改接口） |
| `deploy/` | `run.example.sh` 以 `$PYTHON_BIN -m server.engine.main --config …` 启动本模块入口 |

## 运行

```
$PYTHON_BIN -m server.engine.main --config <config.env>        # 持续模式（循环 + 心跳）
$PYTHON_BIN -m server.engine.main --config <config.env> --once  # 单次扫描 + 收单后退出
```

- `--once` 输出一行 JSON 统计（scanned / dispatched / in_flight / collected）。
- 缺 `--config` 或配置缺失 → 非零退出并报错。

## T3 施工入口

- `store.py` 接口不变，T3 用真实看板数据结构替换 `InMemoryBoardStore`。
