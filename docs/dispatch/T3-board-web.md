# 任务卡 T3 · 任务看板——board 数据模型 + 三视图 + web 页面（Claude Code 执行）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1（§2 状态模型 / §4 看板数据模型 / §8 拓扑）· 管理席：Codex
> 执行体：Claude Code（CLI）· 验收：Codex · 状态：待分派 · 日期：2026-08-02
> 依赖：T1-R、T2（均已验收通过，`server/` 骨架 + Engine 就绪）

## 目标

实现契约 §4 看板：`board/` 正式数据模型与三视图查询（实时状态 / 7 天回写 / 按项目分类）+ 线路图状态聚合占位；`web/` 静态看板页面（**无 API、无 fetch**，数据以导出 JS 变量注入，`file://` 可直接打开）。

## 前置清理（T2 遗留①）

`server/board/README.md` 仍含旧状态机（planned → released）——首步改为契约 §2（待分派 / 执行中 / 已回写 / 已关闭 / 打回）与契约 §4 数据模型描述。

## 红线（先看）

1. **不删除任何文件**；不碰旧代码（`scripts/`、`app/`、`desktop/`、`lib/`、`db/` 零改动）。
2. 不落密钥；**不碰运行面**：本卡不启动 web 服务、不注册 launchd、无网络 API——页面必须 `file://` 可开。
3. 不读不写 qx-map / 外脑；不硬编码（路径 / 端口 / 工具名一律配置化或占位）。
4. 验收标准不可自行解释；完成必须提交（真实 commit hash 回写）。
5. 工作树只允许预存 2 个无关改动（`scripts/.ccc/agent-mind/decided.json`、`_update_handoff.py`），不得带入提交。

## 范围

- 新增：`server/board/`（models.py、loader.py、queries.py、export.py，或等价结构）、`server/web/`（index.html + 页面资源 + `data/` 导出目录）。
- 修改：`server/board/README.md`（状态机清理）；如必要可小改 `server/engine/store.py`（对接用，不重构）。
- 不动：`server/engine/` 其余文件、`server/relay/`（T4）。

## 步骤

1. `board/README.md`：状态模型与数据模型对齐契约 §2 / §4。
2. `models.py`：视图数据字段（契约 §4：ID / 状态 / 项目 / 执行体 / 分派时间 / 回写时间 / 打回次数）。
3. `loader.py`：从任务卡文档解析派生视图（任务卡 = 唯一事实源；解析状态 / 项目 / 执行体 / 时间字段；字段缺失容错，标「未知」不崩溃）。
4. `queries.py`：三视图查询——实时（按状态筛选）、7 天（回写时间窗口，含排序）、按项目分类（分组 + 计数）；线路图状态聚合占位（未开发 / 开发中 / 已开发待验收 / 已验收待确认 / 确认可用 / 有问题）。
5. `export.py`：导出 `web/data/board.js`（`window.BOARD_DATA = {...}` 变量注入，非 fetch，`file://` 可开）。
6. `web/` 页面：三视图切换 + 线路图占位区块 + 顶部状态徽章；视觉沿用架构全景页语言（深/浅色可切换）；静态零 API。
7. 测试：`test_board_loader.py`（解析 / 容错）、`test_board_queries.py`（三视图 + 7 天窗口边界 + 项目分组）、`test_board_export.py`（导出可解析）。
8. 硬编码扫描（S1–S4）零字面量；提交 `chore(board):`，回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. `board/README.md` 已对齐契约 §2 / §4（无旧状态机残留）。
2. 三视图查询测试通过（含 7 天窗口边界、项目分组、状态筛选）。
3. 任务卡解析容错（字段缺失不崩，标未知）。
4. `board.js` 导出可被页面读取；页面 `file://` 可打开，三视图可切换，线路图占位可见。
5. 测试全绿（新增 board 测试 + 既有 engine 测试不回归）；`py_compile` / `bash -n` 过。
6. 零硬编码；真实提交；工作树仅剩 2 个预存项；未碰旧代码 / 运行面 / 外脑。

## 回写要求

结果摘要（人话一句）、测试输出、硬编码扫描输出、commit hash、验收自检对照表。

## 回写区

（Claude Code 回写）
