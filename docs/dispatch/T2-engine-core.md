# 任务卡 T2 · Engine 薄驱动核心（Claude Code 执行）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1 · 管理席：Codex
> 执行体：Claude Code（CLI）· 验收：Codex · 状态：待分派 · 日期：2026-08-02
> 依赖：T1-R（已验收通过，`server/` 骨架就绪）

## 目标

基于 `server/` 骨架实现 Engine 薄驱动核心：入口 + 配置加载 + 主循环 + 注册表读取 + 派发决策 + 任务状态机（契约 §2）。**只做编排，不做执行**；「拉起执行体」本卡只留接口与日志，不真拉。

## 前置修正（验收 T1-R 时发现，必须第一步做）

`server/engine/README.md` 的「关键约定」引用了旧看板状态机（planned / in_progress / testing / verified / released）——与新契约 §2 冲突。第一步改为契约 §2 状态模型：`待分派 → 执行中 → 已回写 → 已关闭`；失败路径 `打回（附问题清单）`。同步检查 `server/README.md` 是否有同类引用。

## 红线（先看）

1. **不删除任何文件**；不碰旧代码（`scripts/`、`app/`、`desktop/`、`lib/`、`db/` 零改动）。
2. 不落密钥；**不碰运行面**：本卡不启动服务、不注册 launchd、不真拉执行体。
3. 不读不写 qx-map / 外脑；不硬编码（工具名/路径/端口/模型一律配置化，沿用 `$PYTHON_BIN` 等变量）。
4. 验收标准不可自行解释；完成必须提交（真实 commit hash 回写）。
5. 工作树只允许预存 2 个无关改动（`scripts/.ccc/agent-mind/decided.json`、`_update_handoff.py`），不得带入提交。

## 范围

- 新增：`server/engine/main.py`、`server/engine/dispatch.py`、`server/engine/task.py`（或等价结构，按 engine/README 施工入口）。
- 修改：`server/engine/README.md`（状态模型修正）、`server/tests/`（新增 `test_engine_*.py`）；如必要可小改 `server/config/loader.py`。
- 不动：`board/`、`web/`、`relay/` 目录（T3 / T4）。

## 步骤

1. 修正 `engine/README.md` 状态模型 → 契约 §2（待分派 / 执行中 / 已回写 / 已关闭 / 打回）。
2. `main.py`：`--config` 加载（走 `loader.load_config`）；支持 `--once`（单次扫描 + 收单，可测）与持续模式（循环 + 心跳占位）；缺配置报错退出。
3. `dispatch.py`：读 `executors.json`（契约 §7 五角色 schema），派发决策——`可后台 CLI` → 标记自动（T4 前写「模拟拉起」日志）；`手动 GUI` → 挂起等人；管理席 / 验收席不参与派发。
4. `task.py`：work 数据结构 + 状态机（契约 §2 五态），非法状态跳转必须报错。
5. 看板对接占位：状态更新写入 `board/` 数据结构接口（T3 落地前先留接口 + 内存实现）。
6. 测试：`test_engine_dispatch.py`（注册表分类决策两分支）、`test_engine_task.py`（合法 / 非法转移）、`test_engine_main.py`（`--once` 冒烟 + 缺配置报错）。
7. 硬编码扫描（S1–S4）零字面量；提交 `chore(engine):`，回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. 状态模型与契约 §2 一致（`engine/README.md` 已修正 + 测试锁定）。
2. `main --once` 可运行：无 config 报错、有 config 出结果。
3. dispatch 决策与注册表分类一致（单测覆盖「可后台 / 手动」两分支）。
4. task 状态机五态 + 非法转移被拦。
5. 测试全绿（含新增 engine 测试）；`py_compile` / `bash -n` 过。
6. 零硬编码；真实提交；工作树仅剩 2 个预存项；未碰旧代码 / 运行面 / 外脑。

## 回写要求

结果摘要（人话一句）、测试输出、硬编码扫描输出、commit hash、验收自检对照表。

## 回写区

（Claude Code 回写）
