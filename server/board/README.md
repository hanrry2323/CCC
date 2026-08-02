# board/ — 看板服务端

> 施工卡：T3（本卡：数据模型 + 三视图查询 + 导出）· 被依赖：`web/`（静态页读导出数据）· 依赖：任务卡文档（`docs/dispatch/`）

## 职责

- 数据模型：从任务卡文档解析的派生视图字段（契约 §4）。
- 三视图查询：实时（按状态筛选）、7 天回写（时间窗口 + 排序）、按项目分类（分组 + 计数）。
- 线路图状态聚合占位（P3 前置）：未开发 / 开发中 / 已开发待验收 / 已验收待确认 / 确认可用 / 有问题。
- 导出 `web/data/board.js`（`window.BOARD_DATA` 变量注入，`file://` 可开，零 API）。

## 数据模型（契约 §4 视图字段）

| 字段 | 来源 | 缺失容错 |
|------|------|---------|
| ID | 任务卡标题 `# 任务卡 T3` | 取文件名 |
| 状态 | 元数据 `状态：X`（契约 §2 五态） | 「未知」 |
| 项目 | 元数据 `关联：INT-120（…）`（取括号前） | 「未知」 |
| 执行体 | 元数据 `执行体：Claude Code（CLI）`（取括号前） | 「未知」 |
| 分派时间 | 元数据 `日期：YYYY-MM-DD` | 「未知」 |
| 回写时间 | 回写区 `**日期**：YYYY-MM-DD` | 「未知」 |
| 打回次数 | `打回次数：N` 显式字段；状态为「打回」至少 1 | 0 |

状态机 = **契约 §2 五态**：`待分派 → 执行中 → 已回写 → 已关闭`；失败 `执行中/已回写 → 打回（附问题清单）`；`打回 → 待分派` 人工重派。**无旧看板状态机（planned/verified/released）残留。**

## 关键约定

- **任务卡文档 = 唯一事实源**：board 数据由 `loader.py` 从 `docs/dispatch/*.md` 解析派生，不另建数据源。
- 字段缺失容错：标「未知」不崩溃；无显式打回次数按 0。
- **只做数据与查询，不做决策**；派发/调度归 `engine/`，board 不产生任务。
- 三视图：实时（状态分组）、7 天（回写时间窗口含排序）、项目（分组 + 计数）。

## 线路图占位（P3 前置）

§2 状态 → 线路图桶映射（占位，P3 可调）：

| §2 状态 | 线路图桶 |
|---------|----------|
| 待分派 | 未开发 |
| 执行中 | 开发中 |
| 已回写 | 已开发待验收 |
| 已关闭 | 确认可用 |
| 打回 | 有问题 |
| — | 已验收待确认（占位空桶） |

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `engine/` | engine 运行态走 `engine/store.py`；本模块只消费任务卡文档，二者不耦合 |
| `web/` | T3 静态页读 `export.py` 产出的 `board.js`，不直接 import |
| `config/` | 不依赖（导出目标路径由 `export.py` 参数给出） |

## T3 施工入口（本卡）

- `server/board/models.py`：`BoardItem` 视图数据字段 + 状态/线路图常量。
- `server/board/loader.py`：`parse_card` / `load_dispatch_cards`。
- `server/board/queries.py`：`view_realtime` / `view_recent` / `view_by_project` / `roadmap_aggregate`。
- `server/board/export.py`：`build_board_data` / `export_board` / CLI 导出到 `web/data/board.js`。
- 测试：`tests/test_board_{loader,queries,export}.py`。
