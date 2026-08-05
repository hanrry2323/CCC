# 任务卡 T3 · 任务看板——board 数据模型 + 三视图 + web 页面（Claude Code 执行）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1（§2 状态模型 / §4 看板数据模型 / §8 拓扑）· 管理席：Codex · 派发：manual · 项目：ccc
> 执行体：Claude Code（CLI）· 验收：Codex · 状态：已关闭 · 日期：2026-08-02
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

**执行体**：Claude Code（CLI）  
**日期**：2026-08-02  
**实现 commit**：`84b496b`（`chore(board):` 前缀 · 13 文件 · 1218 insertions）

### 结果摘要

契约 §4 看板落地：board 数据模型（models）+ 任务卡解析（loader）+ 三视图与线路图查询（queries）+ `window.BOARD_DATA` 导出（export）；`web/` 静态零 API 页面（三视图切换 + 线路图占位 + 状态徽章 + 深/浅主题）以 `file://` 可开；前置清理 board/README 旧状态机，67 用例全绿。

### 测试输出

```
$ python3 -m pytest server/tests/ -v --tb=short
collected 67 items
server/tests/test_board_export.py ...                                    [  4%]
server/tests/test_board_loader.py ......                                [ 14%]
server/tests/test_board_queries.py .......                              [ 25%]
server/tests/test_engine_dispatch.py .........                          [ 38%]
server/tests/test_engine_main.py ......                                 [ 47%]
server/tests/test_engine_task.py ........                               [ 59%]
server/tests/test_skeleton.py ...........................                [100%]
============================== 67 passed in 0.06s ==============================
```

- TestBoardLoader：6 passed（完整解析 / 显式打回次数 / 打回态隐含 / 缺失标未知 / 无括号执行体 / 目录加载）
- TestBoardQueries：7 passed（实时分组 / 未知态桶 / **7 天窗口边界**（恰 7 天含、8 天不含）/ 倒序 / 项目分组计数 / 线路图桶映射 / 徽章计数）
- TestBoardExport：4 passed（导出可解析 / 自动建父目录 / 聚合数据完整）
- 既有 engine 23 + skeleton 27 不回归；`py_compile server/board/*.py` OK · `bash -n` OK · `node --check js/app.js` OK · `node` 桩加载 `board.js` OK

真实数据导出验证：

```
$ python3 -m server.board.export
exported 4 cards -> server/web/data/board.js
states: 待分派 4 · 执行中 0 · 已回写 0 · 已关闭 0 · 打回 0
recent: T1-R, T1, T2（2026-08-02 回写，T3 未回写排除）
projects: INT-120 × 4 · roadmap: 未开发 4
```

### 硬编码扫描（S1–S4 · 零字面量通过线）

范围同前：`server/` 生产代码/模板（`.py/.sh/.plist/.env`），排除 `tests/` 夹具与 `config/executors.example.json`。

| # | 扫描项 | 命令 | 命中 |
|---|--------|------|------|
| S1 | 绝对路径 `/Users` | `rg -n '/Users' server/ -g '!*.md' -g '!server/tests/**' -g '!config/executors.example.json'` | **0** ✅ |
| S2 | 字面端口 `:[4-9][0-9]{3}` | 同上 | **0** ✅ |
| S3 | 模型名 `claude\|gpt-\|gemini\|llama` | `rg -ni 'claude\|gpt-\|gemini\|llama' server/ -g '*.py' -g '*.sh' -g '*.plist' -g '*.env' -g '!server/tests/**'` | **0** ✅ |
| S4 | 工具名 `python3\|opencode\|ollama\|launchd\|codex\|trae` | 同上 | **0** ✅ |

新增 board 模块零字面量；web 静态资源不监听端口、无绝对路径；执行体名只出现在导出的 `board.js`（数据）。

### 目录树（board/web 相关）

```
server/
├── board/
│   ├── README.md          # 状态机已清理 → 契约 §2/§4
│   ├── models.py          # BoardItem + 状态/线路图常量
│   ├── loader.py          # parse_card / load_dispatch_cards（容错）
│   ├── queries.py         # 三视图 + 线路图聚合
│   └── export.py          # build_board_data / export_board / CLI
├── web/
│   ├── README.md          # 已对齐静态零 API 实现
│   ├── index.html         # 顶栏 + 徽章 + 主题 + 四标签
│   ├── css/style.css      # 深/浅主题令牌（沿用架构页）
│   ├── js/app.js          # 渲染 window.BOARD_DATA
│   └── data/board.js      # 导出产物（4 张真实卡）
└── tests/
    ├── test_board_loader.py / test_board_queries.py / test_board_export.py
```

### 验收自检对照表

| # | 验收标准 | 状态 |
|---|----------|------|
| 1 | `board/README.md` 已对齐契约 §2 / §4（无旧状态机残留） | ✅ 已重写；`web/README.md` 同步对齐（原 HTTP 假设已被零 API 取代） |
| 2 | 三视图查询测试通过（含 7 天窗口边界、项目分组、状态筛选） | ✅ 边界测试：恰 7 天含 / 8 天不含 / 未知回写不含；倒序 |
| 3 | 任务卡解析容错（字段缺失不崩，标未知） | ✅ `test_missing_fields_unknown` 通过；ID 回退文件名 |
| 4 | `board.js` 可被页面读取；页面 `file://` 可开，三视图可切换，线路图占位可见 | ✅ node 桩加载验证；相对路径零 fetch；四标签 + 线路图区块 + 徽章 |
| 5 | 测试全绿（新增 board + 既有 engine 不回归）；py_compile / bash -n 过 | ✅ 67 passed；py_compile / bash -n / node --check 全过 |
| 6 | 零硬编码；真实提交；工作树仅剩 2 个预存项；未碰旧代码/运行面/外脑 | ✅ S1–S4 零命中；`84b496b`；工作树剩 decided.json(M) + _update_handoff.py(??)；`scripts/` 等零改动；未启动服务；未读外脑 |

### 遗留/不确定项

1. **线路图「已验收待确认」为空桶**：§2 五态映射后无源状态落到该桶（占位预留，P3 定义）；已关闭映射到「确认可用」。
2. **打回次数源数据缺失**：当前 4 卡无 `打回次数：N` 显式字段且状态非「打回」，均按 0；loader 已支持显式字段与「打回」态隐含。
3. **`board.js` 为提交产物**：由 `server.board.export` 生成并入库；任务卡变更后需重新导出（命令见 `web/README.md`）。
4. **当前卡状态字段未更新**（均「待分派」含已执行卡）：board 忠实呈现任务卡事实源，未做推断覆盖。
