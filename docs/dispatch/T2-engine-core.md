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

**执行体**：Claude Code（CLI）  
**日期**：2026-08-02  
**实现 commit**：`d2fc2dd`（`chore(engine):` 前缀 · 9 文件 · 658 insertions）

### 结果摘要

Engine 薄驱动核心落地：契约 §2 状态机（`task.py`）、注册表读取与派发决策（`dispatch.py`）、看板接口内存占位（`store.py`）、`--once` 可测入口（`main.py`）；前置修正 `engine/README.md` 状态模型，50 用例全绿，已提交入库。

### 测试输出

```
$ python3 -m pytest server/tests/ -v --tb=short
collected 50 items
server/tests/test_engine_dispatch.py .........   [ 18%]
server/tests/test_engine_main.py ......          [ 30%]
server/tests/test_engine_task.py ........        [ 46%]
server/tests/test_skeleton.py ................... [100%]
============================== 50 passed in 0.04s ==============================
```

- TestEngineTask：8 passed（主链路合法 / 打回附问题清单 / 验收打回 / 重派回环 / 打回缺清单报错 / 非法跳转×3 / 终态封锁）
- TestEngineDispatch：9 passed（example 加载 / 缺字段 / 非法分类 / 文件缺失 / 开发+维护→AUTO / 仅手动 GUI→MANUAL / 管理席+验收席+未知→NONE）
- TestEngineMain：6 passed（缺 `--config` 退出码 2 / config 不存在退出码 2 / `--once` 冒烟 JSON / 派发待分派 CLI work / 管理席不派发 / 已回写不重扫）
- 语法：`py_compile server/engine/*.py server/tests/*.py` OK · `bash -n run.example.sh`/`health.example.sh` OK · `plutil -lint` OK

CLI 手动验证：

```
$ python3 -m server.engine.main --config <tmp>/config.env --once
{"mode": "once", "scanned": 0, "dispatched": 0, "in_flight": 0, "collected": 0}
缺 --config 退出码=2；--config 指向不存在文件 退出码=2（FATAL 报错）
```

### 硬编码扫描（S1–S4 · 零字面量通过线）

范围同 T1-R：`server/` 生产代码/模板（`.py/.sh/.plist/.env`），排除 `tests/` 夹具与 `config/executors.example.json`。

| # | 扫描项 | 命令 | 命中 |
|---|--------|------|------|
| S1 | 绝对路径 `/Users` | `rg -n '/Users' server/ -g '!*.md' -g '!server/tests/**' -g '!config/executors.example.json'` | **0** ✅ |
| S2 | 字面端口 `:[4-9][0-9]{3}` | 同上 | **0** ✅ |
| S3 | 模型名 `claude\|gpt-\|gemini\|llama` | `rg -ni 'claude\|gpt-\|gemini\|llama' server/ -g '*.py' -g '*.sh' -g '*.plist' -g '*.env' -g '!server/tests/**'` | **0** ✅ |
| S4 | 工具名 `python3\|opencode\|ollama\|launchd\|codex\|trae` | 同上 | **0** ✅ |

新增 engine 模块零工具名/模型名/端口/绝对路径字面量；执行体工具名只存在于 executors 配置。

### 目录树（engine 相关）

```
server/
├── engine/
│   ├── README.md          # 状态模型已修正为契约 §2
│   ├── main.py            # 入口：--config / --once / 持续循环+心跳
│   ├── dispatch.py        # 注册表读取 + decide()
│   ├── store.py           # BoardStore 接口 + InMemoryBoardStore
│   └── task.py            # Work + 五态状态机
└── tests/
    ├── conftest.py        # 仓库根入 sys.path
    ├── test_engine_dispatch.py
    ├── test_engine_main.py
    └── test_engine_task.py
```

### 验收自检对照表

| # | 验收标准 | 状态 |
|---|----------|------|
| 1 | 状态模型与契约 §2 一致（README 已修正 + 测试锁定） | ✅ engine/README 已改；task.py 五态 + 非法转移测试锁定 |
| 2 | `main --once` 可运行：无 config 报错、有 config 出结果 | ✅ 缺配置退出码 2 + FATAL；有 config 输出 JSON 统计、退出 0 |
| 3 | dispatch 决策与注册表分类一致（两分支单测） | ✅ 开发/维护→AUTO；仅手动 GUI→MANUAL；管理/验收席+未知→NONE |
| 4 | task 状态机五态 + 非法转移被拦 | ✅ 合法 5 路径 + 非法 5 断言全过 |
| 5 | 测试全绿（含新增 engine 测试）；py_compile / bash -n 过 | ✅ 50 passed；py_compile / bash -n / plutil 全过 |
| 6 | 零硬编码；真实提交；工作树仅剩 2 个预存项；未碰旧代码/运行面/外脑 | ✅ S1–S4 零命中；`d2fc2dd`；工作树剩 decided.json(M) + _update_handoff.py(??)；`scripts/` 等零改动；未启动/注册；未读外脑 |

### 遗留/不确定项

1. **board/README.md 仍含旧状态机引用**（planned / in_progress / testing / verified / released）：按本卡「不动 board/ 目录（T3/T4）」范围未改，留 T3 清理；engine 与 server README 已无同类引用。
2. **持续模式未做停止/退出策略**：`run_loop` 为循环 + 心跳占位（T2 范围），真实退出/超时留 T4。
3. **手动 GUI 挂起语义**：派发时同样转入「执行中」（表示已发单、等人接），差异仅在是否写「模拟拉起」日志；未引入独立「挂起」态（契约 §2 无此态）。
4. **打回 → 待分派 回环**：契约 §2 显式仅给「失败 → 打回」，人工处理后重派为隐含闭环；已在 task.py 与 README 明确实现并测试，是否越契约请 Codex 判定。
