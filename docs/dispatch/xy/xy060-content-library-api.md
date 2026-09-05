# 任务卡 xy060 · M6.1 内容库 API（DSH 执行）

> 关联：xy-plan-009 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-05 · 状态版本：18

## 基准文件（先看）

- CCC 项目档案：`docs/projects/xy/README.md`。
- 方案池：`docs/projects/xy/plans/009-frontend-showcase.md`，只激活其中 6.1「内容库 API」；6.2 工作流 API、6.3 视频/图文预览页面、6.4 工作流可视化页面均不在本卡。
- xianyu 业务仓入口（只读核实后在引擎 worktree 执行）：业务仓根 `README.md`、`AGENTS.md`、`CLAUDE.md`。
- 已核实的业务 API 入口：xianyu 业务仓 `admin/api/server.py`（FastAPI，既有 `/api/health` 等只读适配端点）；既有产出扫描基准为 `video-pipeline/output/`，实际路径和现状必须在 worktree 内再次核实后以代码为准。
- 已核实的测试基准：业务仓 `tests/admin/` 下现有 admin API 测试；新增或调整测试须限于内容库 API 契约。

## 目标

在 xianyu 现有 admin 只读适配层中实现或补齐 M6.1「内容库 API」：扫描既有视频产出目录与图文产物目录，按稳定契约输出只读 JSON 元数据列表，供后续展示台消费。每次请求实时发现新产出，不引入发布或工作流副作用。

## 非目标

- 不实现或修改 M6.2 工作流 API、M6.3 视频/图文预览页面、M6.4 工作流可视化页面。
- 不修改视频/图文生产核心、pipeline 状态机、worker、调度、发布、数据库 schema 或外部工作流 API。
- 不触发发布、不启动生产任务、不增加后台常驻扫描、不接入鉴权以外的新运行时依赖。
- 不改变既有 admin 页面；本卡只交付 API 适配与对应测试。

## 实现要求

1. 在现有 admin/API 入口中提供只读 `GET /api/v1/library`；沿用当前服务的认证、错误处理和 JSON 返回风格，不另起服务。
2. 以业务仓当前真实产出目录为准，扫描任务目录中的视频与图文产物；不得凭卡内示例路径臆造目录。必要时兼容仓内已经存在的扁平产出结构，但不能扫描到范围外的生产目录。
3. 每条记录稳定提供 `task_id`、`title`、`date`、`duration`、`size`、`type`、`path`；`type` 仅为 `video` 或 `article`。标题、时长、日期按现有产物元数据优先级读取，缺失元数据时使用可解释的文件/目录降级值。
4. 扫描必须是只读、实时、可容错：空目录/目录不存在返回空列表；坏 JSON、坏文件名或单个不可读条目不得使整个 API 500；结果按日期倒序且字段类型稳定。
5. 补齐针对视频、图文、空态、坏元数据/缺字段、无脚本降级、新产出自动发现和只读边界的测试；测试使用临时目录/fixtures，不触碰真实生产产出。
6. 若基准中已有 M6.1 实现，先逐项对账本卡契约与现有测试；只修复确有证据的缺口，不重复造同名路由，不扩大到 6.2–6.4。

## 红线

1. 只允许在引擎提供的 xianyu 业务 worktree 内改动业务代码；禁止修改 CCC 主仓卡、主仓其他文件或业务仓 main 工作区。
2. 禁止修改业务仓 `src/xianyu/`、视频管线核心、worker/调度/发布代码；只读 admin 适配层与本卡对应测试文件。
3. 禁止发布、写数据库、写产出目录、删除/覆盖真实产物、调用工作流 API 或启动 DSH。
4. 禁止把绝对业务仓路径写入 CCC `## 范围`；跨仓文件只在基准文件/步骤中以自然语言说明。
5. 禁止写 `## 机审区`、`## 验收区`、修改卡头状态或把 `.ccc-result.md` 纳入业务仓提交。

## 范围

docs/dispatch/xy/xy060-content-library-api.md

## 步骤

1. 在引擎提供的业务 worktree 中先通读本卡、业务仓根 `README.md`/`AGENTS.md`/`CLAUDE.md`，再只读核实 admin/API 入口、当前路由、实际产出目录和现有测试；把核实结果写入 `.ccc-result.md`，不得凭空造路径。
2. 对照方案 009 的 6.1 契约与现有实现，确定最小业务文件集合：现有 admin API 适配入口及其对应 admin 测试；不改生产核心。
3. 实现或补齐实时目录扫描与 `GET /api/v1/library`，处理视频、图文、空目录、缺失/坏元数据、不可读条目和稳定日期排序；保持既有认证边界与只读行为。
4. 用临时 fixtures 编写/补齐测试，至少覆盖：完整视频字段、图文字段、空态、无脚本降级、坏 JSON 容错、新目录自动收录、日期倒序、认证/只读边界；测试不得写真实产出目录。
5. 运行并记录仓库实际适用的测试、编译和 lint 门禁；若仓库现有命令或依赖不可用，记录原始输出和退出码，不用假结果替代。
6. 检查业务 worktree diff 只落在本卡允许的 admin 适配层/测试文件；不得直接改主仓卡，不得把结果文件提交到业务仓。
7. 在业务 worktree 根写 `.ccc-result.md`，包含卡标题复述、独立核实探针、实现/测试结果、变更证据、维护区四问和批注落实；写完即停，交由 wrapper/Engine 回写主仓卡。

## 验收标准

1. API 可读：认证方式沿用既有 admin API；`GET /api/v1/library` 在有效认证下返回 2xx JSON，顶层包含稳定的 `count` 与 `items`，未授权请求保持既有拒绝行为。
2. 元数据字段稳定：视频和图文记录均含 `task_id/title/date/duration/size/type/path`；视频 `type=video` 且时长可为数值或明确的 `null`，图文 `type=article` 且不伪造时长；`size` 为非负整数，`path` 为业务仓内可消费的相对路径，不泄漏绝对路径。
3. 发现与排序：新增任务目录/产物无需重启即可出现在下一次请求；列表按日期倒序，混合视频、图文和同任务多产物时结果可预测。
4. 空态：产出目录不存在、存在但为空、只有无关文件时，API 返回 2xx、`count=0`、`items=[]`，不创建目录、不写数据库。
5. 坏文件容错：坏 JSON、缺失可选元数据、单个不可读/不符合扩展名的条目不会导致整次请求 500；可降级记录仍保持字段契约，无法安全读取的条目可被跳过并在测试/结果中说明。
6. 只读边界：实现不修改生产核心、调度、发布、数据库或真实产出；测试验证扫描过程无写副作用，业务 diff 只在本卡允许的 admin 适配层与测试文件。
7. 质量门禁：业务仓已有测试、与本卡相关的新增测试、编译检查和 lint 按仓库实际命令通过；所有命令及退出码原样记录在 `.ccc-result.md`。
8. 回写契约：`.ccc-result.md` 位于执行 worktree 根，完整包含卡标题复述、独立探针、测试输出、变更文件证据和维护区四问；执行体不修改主仓卡、不写机审区、不提交 `.ccc-result.md`。

## 门禁

> 门禁命令以业务仓现行配置为准；执行体必须记录原始输出与退出码。
测试：`uv run pytest tests/admin/test_library.py tests/admin/ -q`（若仓库现行入口不同，先核实后使用等价命令）
编译：`uv run python -m compileall admin/`
lint：`uv run ruff check admin/ tests/admin/`
范围：false

## 回写要求

执行体只在引擎提供的业务 worktree 工作；完成后只在 worktree 根产出 `.ccc-result.md`，不改 CCC 主仓卡、不把结果文件纳入业务仓提交、不手动启动 DSH。

`.ccc-result.md` 必须包含：

- `## 0. 卡标题复述`：完整复述本卡标题、目标、非目标与红线；
- `## 1. 独立核实`：真实 admin/API 入口、真实产出目录、现有测试入口、关键基准文件与核实命令输出；
- `## 2. 实现与自测`：实现文件、测试/编译/lint 原始输出和退出码；
- `## 3. 维护区四问`：方案同步、教训沉淀、档案/README、线路图，逐项 `[是]`/`[否]` 或 `[有]`/`[无]` 并说明证据；
- `## 4. 变更证据`：业务 worktree 的 `git diff --stat`、改动文件白名单对账、提交/分支事实（如 wrapper 已提交则如实记录）。

写完结果文件后停手，等待 Engine 代写主仓卡回写区、维护区四问和卡头状态。

## 前置机审与维护区契约

- 前置机审必须独立核对：业务 diff 是否仅在 admin 只读适配层与测试；是否真的提供只读 `/api/v1/library`；字段、排序、空态、坏文件容错和实时发现是否有可复现证据；是否触碰生产核心/发布/工作流；测试/编译/lint 输出是否与结果文件一致。
- 机审不得以执行体自报替代证据；必须以业务 worktree 的 git diff、测试原始输出、测试 fixtures 和实际符号/路由核对结论。
- 回写时维护区四问必须逐项回答并附具体证据：
  1. 方案同步：只涉及 `xy-plan-009` 的 6.1，说明方案状态/关联卡同步情况；不宣称 6.2–6.4 完成。
  2. 教训沉淀：Q2 选择 `[有]` 时，说明必须引用 CCC 主仓中真实存在的 `docs/notes/YYYY-MM-DD-*.md` 或 `lessons.md` 路径，并说明该文档与本卡的复用教训；若没有真实文档，必须选择 `[无]` 并说明理由，不得以未落盘的口头教训或其他过程记录代替。
  3. 档案/README：说明是否改变项目结构、技术栈或路径；若仅改 admin 适配层与测试，写 `[否]` 并给 diff 证据。
  4. 线路图：说明 M6.1 交付是否改变 xianyu 下一步；不得顺带推进 M6.2–6.4。
- 若上述任一项缺少真实证据，前置机审打回，不以过程日志或口头完成声明替代。

## 人工批注

无批注。若后续出现批注，执行体必须先读本节并在 `.ccc-result.md` 的批注落实段逐项说明。

## 批注落实

」，内容为无批注，无额外落实项。

## 回写区

## 0. 卡标题复述

卡标题：**任务卡 xy060 · M6.1 内容库 API（DSH 执行）**。

- 目标：在 xianyu 现有 admin 只读适配层中实现或补齐 M6.1「内容库 API」：扫描既有视频产出目录与图文产物目录，按稳定契约输出只读 JSON 元数据列表，供后续展示台消费；每次请求实时发现新产出，不引入发布或工作流副作用。
- 非目标：不实现或修改 M6.2 工作流 API、M6.3 视频/图文预览页面、M6.4 工作流可视化页面；不修改视频/图文生产核心、pipeline 状态机、worker、调度、发布、数据库 schema 或外部工作流 API；不触发发布、不启动生产任务、不增加后台常驻扫描、不接入鉴权以外的新运行时依赖；不改变既有 admin 页面。
- 红线：仅允许 admin 只读适配层与本卡对应测试；未触碰 `src/xianyu/`、视频管线核心、worker/调度/发布、数据库；未发布、未写数据库、未写真实产出目录、未调用工作流 API；未修改 CCC 主仓卡；本结果文件不纳入业务提交。
- 人工批注：已读取「## 人工批注」与「## 批注落实」，内容为无批注，无额外落实项。

## 1. 探针输出

工作目录：`/Users/fan/program/apps/.ccc-wt/xy/xy060`。

| 核实项 | 命令 | 原始输出与结果 |
|---|---|---|
| 分支/工作树 | `git branch --show-current && git log --oneline -6 && git status --short --branch` | 分支 `codex/xy060-content-library-api`；HEAD `f769514 fix(xy060): guard unreadable video output root`；工作树仅预置未跟踪 `.venv`，无业务文件改动。 |
| API 路由与认证 | `grep -n "@app.get(\"/api/v1/library\")\\|Depends(verify_credentials)\\|return {\"count\"" admin/api/server.py` | `admin/api/server.py:1595` 提供 `GET /api/v1/library`，`server.py:1596` 使用 `Depends(verify_credentials)`，`server.py:1614` 返回 `count/items`。 |
| 实现主体 | 读取 `admin/api/server.py:1409-1614` | 已有只读扫描 `_scan_library_task`、`_scan_article_library`、`scan_library`；字段含 `task_id/title/date/duration/size/type/path`；视频/图文类型分别为 `video/article`；坏 JSON、目录/条目不可读时降级或跳过；每次请求实时扫描并按日期倒序。 |
| 测试基准 | 读取 `tests/admin/test_library.py` | 文件 416 行，20 个本卡用例，覆盖视频、图文、空态、坏 JSON、缺字段/无脚本降级、不可读条目、实时发现、日期倒序、认证与只读边界。 |
| 真实产出目录 | `ls -ld video-pipeline/output workspace/outputs/image_text 2>&1`; 同样核对 `/Users/fan/program/apps/xianyu/...` | worktree 与权威业务仓两处均输出 `No such file or directory`；代码真实落点为 `ROOT / video-pipeline / output` 与 `ROOT / workspace / outputs / image_text`，缺失时返回空列表且不创建目录。 |
| 范围对账 | `git diff --check origin/main...HEAD && git diff --name-only origin/main...HEAD` | `git diff --check` 退出码 `0`；文件仅 `admin/api/server.py`、`tests/admin/test_library.py`。 |

## 2. 自测输出

以下命令均在业务 worktree 执行，记录原始输出摘要与退出码：

1. 测试：`uv run pytest tests/admin/test_library.py tests/admin/ -q`
   - 原始输出末段：`collected 98 items`；`======================= 98 passed, 30 warnings in 6.21s ========================`
   - 退出码：`0`
   - 说明：包含本卡 `tests/admin/test_library.py` 的 20 个用例及全部 `tests/admin/` 测试。
2. 编译：`uv run python -m compileall admin/`
   - 原始输出：`Listing 'admin/'...`、`Listing 'admin/api'...`、`Listing 'admin/css'...`、`Listing 'admin/js'...`、`Listing 'admin/pages'...`
   - 退出码：`0`
3. lint：`uv run ruff check admin/ tests/admin/`
   - 原始输出：`All checks passed!`
   - 退出码：`0`
4. 范围：`git diff --check origin/main...HEAD && git diff --stat origin/main...HEAD && git diff --name-only origin/main...HEAD && git status --short --branch`
   - 原始输出：`admin/api/server.py | 138 +++++++++++++++++++++++++++++++++-----------`；`tests/admin/test_library.py | 136 +++++++++++++++++++++++++++++++++++++++++++`；仅上述两个业务文件；工作树仅预置未跟踪 `.venv`。
   - 退出码：`0`

## 0. 卡标题复述

卡标题：**任务卡 xy060 · M6.1 内容库 API（DSH 执行）**。

- 目标：在 xianyu 现有 admin 只读适配层中实现或补齐 M6.1「内容库 API」：扫描既有视频产出目录与图文产物目录，按稳定契约输出只读 JSON 元数据列表，供后续展示台消费；每次请求实时发现新产出，不引入发布或工作流副作用。
- 非目标：不实现或修改 M6.2 工作流 API、M6.3 视频/图文预览页面、M6.4 工作流可视化页面；不修改视频/图文生产核心、pipeline 状态机、worker、调度、发布、数据库 schema 或外部工作流 API；不触发发布、不启动生产任务、不增加后台常驻扫描、不接入鉴权以外的新运行时依赖；不改变既有 admin 页面。
- 红线落实：业务改动仅限 `admin/api/server.py` 与 `tests/admin/test_library.py`；未触碰 `src/xianyu/`、视频管线核心、worker/调度/发布、数据库；未发布、未写数据库、未写真实产出目录、未调用工作流 API；未修改 CCC 主仓卡；`.ccc-result.md` 未纳入业务提交。
- 人工批注：已读取卡内「## 人工批注」与「## 批注落实」，内容为无批注，无额外落实项。

## 1. 探针输出

工作目录：`/Users/fan/program/apps/.ccc-wt/xy/xy060`。

1. 分支与工作树：
   - 命令：`git branch --show-current && git status --short --branch`
   - 输出：`codex/xy060-content-library-api`；工作树仅有预置未跟踪软链接 `.venv`，无业务文件改动。
2. admin/API 入口与认证：
   - 命令：`grep -n "^ROOT\|^LIBRARY_OUTPUT_DIR\|^LIBRARY_ARTICLE_OUTPUT_DIR\|^ADMIN_USER\|^ADMIN_PASS\|from datetime\|import json\|^app = \|def verify_credentials\|@app.get(\"/api/v1/library\")" admin/api/server.py`
   - 原始输出：`ROOT`=`admin/api/server.py:49`；视频目录=`server.py:51 ROOT / "video-pipeline" / "output"`；图文目录=`server.py:52 ROOT / "workspace" / "outputs" / "image_text"`；认证=`server.py:76 verify_credentials`；FastAPI=`server.py:137`；路由=`server.py:1595`。
3. 真实产出目录：
   - 命令：`ls video-pipeline/output 2>&1; ls workspace/outputs/image_text 2>&1; ls /Users/fan/program/apps/xianyu/video-pipeline/output 2>&1; ls /Users/fan/program/apps/xianyu/workspace/outputs/image_text 2>&1`
   - 原始输出：四个路径均为 `No such file or directory`。实现按代码真实落点扫描，目录缺失返回空列表，不创建目录。
4. 方案契约：
   - 命令：`grep -n -A8 "6.1" /Users/fan/program/CCC/docs/projects/xy/plans/009-frontend-showcase.md | head -60`
   - 原始输出关键行：`117` 仅激活 6.1 内容库 API；`118` 沿用 admin 只读适配层与既有产出目录；`119` 验收 `GET /api/v1/library` 字段完整、当日产出可见、新任务自动收录；`120` 明确 6.2–6.4 未激活。
5. 测试入口：`tests/admin/test_library.py` 存在，当前 416 行；测试文件覆盖视频、图文、空态、坏 JSON、缺字段/无脚本降级、不可读条目、实时发现、日期倒序、认证与只读边界。
6. 范围核对：`git diff --name-only origin/main...HEAD` 输出仅 `admin/api/server.py`、`tests/admin/test_library.py`；`git diff --check origin/main...HEAD` 退出码为 `0`。

## 2. 自测输出

以下命令均在业务 worktree 执行，记录原始输出摘要与退出码：

1. 测试
   - 命令：`uv run pytest tests/admin/test_library.py tests/admin/ -q`
   - 原始输出：`collected 98 items`；`======================= 98 passed, 30 warnings in 6.09s ========================`
   - 退出码：`0`
2. 编译
   - 命令：`uv run python -m compileall admin/`
   - 原始输出：`Listing 'admin/'...`、`Listing 'admin/api'...`、`Listing 'admin/css'...`、`Listing 'admin/js'...`、`Listing 'admin/pages'...`
   - 退出码：`0`
3. lint
   - 命令：`uv run ruff check admin/ tests/admin/`
   - 原始输出：`All checks passed!`
   - 退出码：`0`
4. 范围与工作树
   - 命令：`git diff --check origin/main...HEAD && git diff --stat origin/main...HEAD && git diff --name-only origin/main...HEAD && git status --short --branch`
   - 原始输出：`admin/api/server.py | 138 +++++++++++++++++++++++++++++++++-----------`；`tests/admin/test_library.py | 136 +++++++++++++++++++++++++++++++++++++++++++`；仅上述两个业务文件；`

## 0. 卡标题复述

卡标题：**任务卡 xy060 · M6.1 内容库 API（DSH 执行）**。

- 目标：在 xianyu 现有 admin 只读适配层中实现或补齐 M6.1「内容库 API」：扫描既有视频产出目录与图文产物目录，按稳定契约输出只读 JSON 元数据列表，供后续展示台消费；每次请求实时发现新产出，不引入发布或工作流副作用。
- 非目标：不实现或修改 M6.2 工作流 API、M6.3 视频/图文预览页面、M6.4 工作流可视化页面；不修改视频/图文生产核心、pipeline 状态机、worker、调度、发布、数据库 schema 或外部工作流 API；不触发发布、不启动生产任务、不增加后台常驻扫描、不接入鉴权以外的新运行时依赖；不改变既有 admin 页面。
- 红线落实：业务改动仅限 `admin/api/server.py` 与 `tests/admin/test_library.py`；未触碰 `src/xianyu/`、视频管线核心、worker/调度/发布、数据库；未发布、未写数据库、未写真实产出目录、未调用工作流 API；未修改 CCC 主仓卡；`.ccc-result.md` 未纳入业务提交。
- 人工批注：已读取卡内「## 人工批注」与「## 批注落实」，内容为无批注，无额外落实项。

## 1. 探针输出

工作目录：`/Users/fan/program/apps/.ccc-wt/xy/xy060`。

| 核实项 | 命令/证据 | 原始输出与结果 |
|---|---|---|
| 分支与工作树 | `git status --short --branch && git log --oneline -5` | `

## 2. 自测输出

以下命令均在业务 worktree 执行；结果按终端原始输出记录：

1. 测试：`uv run pytest tests/admin/test_library.py tests/admin/ -q`
   - 输出末行：`======================= 98 passed, 30 warnings in 5.30s ========================`
   - 退出码：`0`
2. 编译：`uv run python -m compileall admin/`
   - 输出：`Listing 'admin/'...`、`Listing 'admin/api'...`、`Listing 'admin/css'...`、`Listing 'admin/js'...`、`Listing 'admin/pages'...`
   - 退出码：`0`
3. lint：`uv run ruff check admin/ tests/admin/`
   - 输出：`All checks passed!`
   - 退出码：`0`
4. 最终范围与工作树：`git status --short --branch && git diff --check origin/main...HEAD && git diff --stat origin/main...HEAD && git diff --name-only origin/main...HEAD`
   - 输出包含：`admin/api/server.py | 138 +++++++++++++++++++++++++++++++++-----------`、`tests/admin/test_library.py | 136 +++++++++++++++++++++++++++++++++++++++++++`；仅上述两项业务文件；`.ccc-result.md` 未被纳入该 diff。
   - 退出码：`0`

实现证据：`admin/api/server.py:1410-1614` 提供只读目录扫描、视频/图文字段归一化、坏元数据/不可读条目容错、实时发现、日期倒序和 `GET /api/v1/library`；测试证据：`tests/admin/test_library.py:103-416`。

## 0. 卡标题复述

卡标题：**任务卡 xy060 · M6.1 内容库 API（DSH 执行）**。

- 目标：在 xianyu 现有 admin 只读适配层中实现或补齐 M6.1「内容库 API」：扫描既有视频产出目录与图文产物目录，按稳定契约输出只读 JSON 元数据列表，供后续展示台消费；每次请求实时发现新产出，不引入发布或工作流副作用。
- 非目标：不实现或修改 M6.2 工作流 API、M6.3 视频/图文预览页面、M6.4 工作流可视化页面；不修改视频/图文生产核心、pipeline 状态机、worker、调度、发布、数据库 schema 或外部工作流 API；不触发发布、不启动生产任务、不增加后台常驻扫描、不接入鉴权以外的新运行时依赖；不改变既有 admin 页面。
- 红线：业务改动仅限 `admin/api/server.py` 与 `tests/admin/test_library.py`；未触碰 `src/xianyu/`、视频管线核心、worker/调度/发布、数据库；未发布、未写数据库、未写真实产出目录、未调用工作流 API；未修改 CCC 主仓卡；`.ccc-result.md` 未纳入业务提交。
- 人工批注：无；已核对卡内「## 人工批注」与「## 批注落实」。

## 1. 探针输出

工作目录：`/Users/fan/program/apps/.ccc-wt/xy/xy060`。

| 核实项 | 命令/证据 | 原始输出与结果 |
|---|---|---|
| 分支与工作树 | `git branch --show-current && git status --short --branch` | `codex/xy060-content-library-api`；工作树仅预置未跟踪软链接 `.venv`。 |
| 业务入口与路由 | `grep -n "LIBRARY_OUTPUT_DIR\\|LIBRARY_ARTICLE_OUTPUT_DIR\\|^ROOT\\|^app = \\|verify_credentials" admin/api/server.py` | `ROOT = Path(__file__).resolve().parents[2]`；视频目录 `ROOT / "video-pipeline" / "output"`；图文目录 `ROOT / "workspace" / "outputs" / "image_text"`；`@app.get("/api/v1/library")` 在 `server.py:1595`；认证依赖 `verify_credentials`。 |
| 产出目录核实 | `ls -la video-pipeline/output; ls -la workspace/outputs/image_text`；同样核对 `/Users/fan/program/apps/xianyu/...` | 两处 worktree 路径及权威业务仓路径当前均不存在，命令原始输出为 `No such file or directory`；代码使用的真实业务落点与卡基准一致，不凭空创建目录，缺失时返回空列表。 |
| 方案契约 | 读取 `docs/projects/xy/plans/009-frontend-showcase.md` | 6.1 要求只读 JSON、扫描产出、字段 `{task_id,title,date,duration,size,type,path}`、日期倒序；本实现仅涉及 6.1，未推进 6.2–6.4。 |
| 现有测试 | 读取 `tests/admin/test_library.py` | 文件 416 行，20 个用例，覆盖视频、图文、空态、坏 JSON、字段降级、不可读条目、实时发现、日期倒序、认证、只读边界。 |
| 范围对账 | `git diff --name-only origin/main...HEAD` | `admin/api/server.py`；`tests/admin/test_library.py`。 |
| 差异卫生 | `git diff --check origin/main...HEAD` | `diff_check_exit=0`。 |

## 2. 自测输出

以下命令均在业务 worktree 执行，原始结果与退出码记录如下：

#

## 0. 卡标题复述

卡标题：**任务卡 xy060 · M6.1 内容库 API（DSH 执行）**。

- 目标：在 xianyu 现有 admin 只读适配层中实现或补齐 M6.1「内容库 API」：扫描既有视频产出目录与图文产物目录，按稳定契约输出只读 JSON 元数据列表，供后续展示台消费；每次请求实时发现新产出，不引入发布或工作流副作用。
- 非目标：不实现或修改 M6.2 工作流 API、M6.3 视频/图文预览页面、M6.4 工作流可视化页面；不修改视频/图文生产核心、pipeline 状态机、worker、调度、发布、数据库 schema 或外部工作流 API；不触发发布、不启动生产任务、不增加后台常驻扫描、不接入鉴权以外的新运行时依赖；不改变既有 admin 页面。
- 红线落实：仅核对并保留业务改动在 admin 只读适配层及本卡对应测试；未触碰 `src/xianyu/`、视频管线核心、worker/调度/发布、数据库；未发布、未写数据库、未写真实产出目录、未调用工作流 API；未修改 CCC 主仓卡；本结果文件未纳入业务提交。
- 人工批注：无；已核对卡内「## 人工批注」与「## 批注落实」。

## 1. 探针输出

工作目录：`/Users/fan/program/apps/.ccc-wt/xy/xy060`。

| 核实项 | 命令/证据 | 原始结果摘要 |
|---|---|---|
| 业务入口 | `grep -n 'library\|scan_library' admin/api/server.py` | `scan_library` 位于 `admin/api/server.py:1559`；`GET /api/v1/library` 位于 `admin/api/server.py:1595`。 |
| 认证边界 | `grep -n 'verify_credentials\|library' admin/api/server.py` | 路由使用 `Depends(verify_credentials)`；既有 Basic Auth 边界沿用。 |
| 真实产出目录 | `grep -n 'LIBRARY_OUTPUT_DIR\|LIBRARY_ARTICLE_OUTPUT_DIR' admin/api/server.py` | 视频目录为 `ROOT / "video-pipeline" / "output"`；图文目录为 `ROOT / "workspace" / "outputs" / "image_text"`。 worktree 当前目录不存在时返回空列表。 |
| 既有测试 | `ls tests/admin/`；读取 `tests/admin/test_library.py` | `tests/admin/test_library.py` 存在，共 416 行；覆盖视频、图文、空态、坏 JSON、字段降级、实时发现、日期排序、认证和只读边界。 |
| 业务文档 | 读取 `README.md`、`AGENTS.md`、`CLAUDE.md` | 核实 Python/FastAPI、admin API 与测试/lint 入口及仓库红线。 |
| 范围对账 | `git diff origin/main...HEAD --name-only` | 仅：`admin/api/server.py`、`tests/admin/test_library.py`。 |
| 工作树 | `git status --short` | 仅有预置环境软链接 `.venv` 未跟踪；未出现业务文件改动。 |

## 2. 自测输出

#

## 0. 卡标题复述

卡标题：**xy060 · M6.1 内容库 API（DSH 执行）**

- 目标：在 xianyu 现有 admin 只读适配层中实现/补齐 M6.1「内容库 API」：扫描既有视频产出目录与图文产物目录，按稳定契约输出只读 JSON 元数据列表，供后续展示台消费；每次请求实时发现新产出，不引入发布或工作流副作用。
- 非目标：不实现/修改 M6.2 工作流 API、M6.3 视频/图文预览页面、M6.4 工作流可视化页面；不修改视频/图文生产核心、pipeline 状态机、worker、调度、发布、数据库 schema 或外部工作流 API；不触发发布、不启动生产任务、不增加后台常驻扫描、不接入鉴权以外的新运行时依赖；不改变既有 admin 页面。
- 红线（落实结果）：只在引擎 worktree 内改动业务代码（仅 admin/api/server.py 与 tests/admin/test_library.py）；未触碰 src/xianyu/、视频管线核心、worker/调度/发布、数据库；未发布/未写 DB/未写产出目录/未删除真实产物/未调用工作流 API；未改 CCC 主仓卡；`.ccc-result.md` 未纳入业务仓提交。
- 批注：本卡无人工批注（卡内「## 人工批注」「## 批注落实」均为"无批注"），已核对无需落实。

## 1. 探针输出

独立只读核实（命令与原始输出摘要；全部在引擎 worktree `/Users/fan/program/apps/.ccc-wt/xy/xy060` 内执行）：

| 核实项 | 证据 | 结果 |
|---|---|---|
| 卡分支与远端 | `git branch --show-current` = `codex/xy060-content-library-api`；`git status` 仅 `.venv` 未跟踪 | 任务分支就绪 |
| admin API 入口 | `admin/api/server.py`（FastAPI，`app = FastAPI(title="xianyu admin api")`，HTTP Basic Auth 经 `verify_credentials`） | 确认既有只读适配层 |
| 既有路由 | `/api/health`、`/api/stats/summary`、`/api/topics`、`/api/contents` 等沿用 `Depends(verify_credentials)` | 认证边界沿用 |
| 内容库现状 | `server.py:1595` 已有 `@app.get("/api/v1/library")`，`server.py:1559` `scan_library()` 实时扫描 | 已有 M6.1 实现，需对账 |
| 视频产出目录 | worktree 内 `video-pipeline/output` 不存在（空态）；真实仓 `/Users/fan/program/apps/xianyu/video-pipeline/output` 亦不存在（`ls` 无输出） | 以代码路径 `ROOT/"video-pipeline"/"output"` 为准，空态路径 |
| 图文产出目录 | worktree 内 `workspace/outputs` 不存在；真实仓 `workspace/outputs/image_text` 不存在 | 以代码路径 `ROOT/"workspace"/"outputs"/"image_text"` 为准 |
| 现有测试 | `tests/admin/test_library.py`（416 行，20 个用例）已覆盖视频/图文/空态/坏JSON/降级/排序/新产出/认证/只读 | 测试已齐全 |
| 方案基准 | `docs/projects/xy/plans/009-frontend-showcase.md`：6.1 验收 = 字段完整、自动收录、只读 JSON；`docs/projects/xy/README.md` 业务档案 | 契约一致 |

## 2. 自测输出

#

## 维护区

1. 方案同步：`[是]` —— 仅涉及 `xy-plan-009` 的 6.1「内容库 API」；未宣称 6.2、6.3、6.4 完成。证据：任务卡第 8、93 行约束与业务实现 `admin/api/server.py:1409-1614`。
2. 教训沉淀：`[无]` —— 本次未新增或修改 CCC 主仓真实存在的 `docs/notes/YYYY-MM-DD-*.md` 或 `lessons.md` 文档；按卡要求不以口头过程记录替代教训沉淀。
3. 档案/README：`[否]` —— 未改变项目结构、技术栈或路径；`git diff --name-only origin/main...HEAD` 仅包含 `admin/api/server.py` 与 `tests/admin/test_library.py`，未修改 README、项目档案或生产核心。
4. 线路图：`[否]` —— M6.1 交付未改变 xianyu 下一步；未修改 GOAL/roadmap，未顺带推进 M6.2–M6.4。
