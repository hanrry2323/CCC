# 任务卡 xy066 · 图文配图语义选图增强（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy066 · 状态版本：8
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

xy062 遗留「配图占位」缺口：文章配图曾为 `[MOCK IMAGES]` 占位。`src/xianyu/content/image.py` 已具备 Pexels→picsum 真实图降级链（xy063 已实修），但缺「按文案段落语义选图」。本卡补齐：

1. **按段落语义选图**：从文案正文按段落提取关键词（优先取标题/每段首句核心名词；xy065 的四段结构可复用：钩子/痛点/干货/号召），为每段选 1 张语义匹配真图。
2. **每段一图产出**：图文产物 `index.html` 每段落配对应图；`image_paths` 指向真实图片文件（JPEG，≥5KB 校验沿用）。
3. **降级兜底**：Pexels 无凭据/失败 → picsum；仍失败 → 真实占位（本地生成的设计化文字卡图，**不得再输出 `[MOCK IMAGES]` 文本占位**）。
4. **测试**：段落关键词提取、每段一图映射、降级链单测（mock 网络）；全部真实通过。

## 实现要求

1. 改动限于 `src/xianyu/content/image.py`、`src/xianyu/content/writer.py`（如需传入段落结构）、对应 `tests/`。
2. 关键词提取为确定性函数（纯文本→关键词列表），可单测；不得依赖外部模型。
3. 降级路径必须产出真实图片文件（哪怕本地生成文字卡），不得输出占位文本。
4. 凭据读取沿用 `_pexels_key()`（env/共享凭据，运行时读取，日志不输出值）。

## 红线

1. 只改 xianyu 业务仓；不发布、不触碰 Cookie/外部账号、不启动 M7。
2. 禁止把任何凭据值写入文件、测试、日志或提交。
3. 不得伪造图片文件或虚报来源；每张图如实记录 source（pexels/picsum/local）。
4. 不得删除既有产物/数据库；所有改动业务分支 commit；测试真实通过。

## 范围

- `/Users/fan/program/apps/xianyu/src/xianyu/content/image.py`
- `/Users/fan/program/apps/xianyu/src/xianyu/content/writer.py`
- `/Users/fan/program/apps/xianyu/tests/content/test_image.py`

## 步骤

1. 读 image.py 现状与 `_fetch_image`/`_download_picsum`；跑 `tests/content/test_image.py` 确认基线。
2. 实现段落关键词提取（确定性）与每段一图映射。
3. 实现降级链：Pexels→picsum→本地文字卡图（真实文件）。
4. 补单测（mock 网络）：关键词提取、映射、三级降级。
5. 全量相关测试真实通过；业务分支 commit；`.ccc-result.md` 如实记录（含取样图片 source/大小）。

## 验收标准

1. 段落关键词提取为确定性纯函数，单测覆盖（含空段/无名词段）。
2. 每段一图映射正确；`index.html` 每段引用对应真实图片文件。
3. 三级降级链（pexels→picsum→本地）各路径单测通过；无凭据/失败时产出真实图片文件（非占位文本）。
4. `tests/content/test_image.py` 及内容相关测试全部通过退出码 0；全量回归无新增失败。
5. 代码/测试/文档无任何凭据明文。
6. 业务分支 commit 存在；工作树除结果文件外干净。
7. 不虚报：降级路径与图片来源如实记录。

## 门禁

测试（content）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest tests/content/test_image.py tests/content/test_writer.py -q`

## 回写要求

结果写入 `.ccc-result.md`，含：改动 diff 摘要、关键词提取示例、每段一图映射示例（段落→图 source/大小）、测试原始输出、降级路径实测、维护区四问（标准键名）、变更证据。

## 批注落实

任务卡「## 人工批注」原文：1.【Q2 教训引用】上轮机审：维护区②声明[有]但未引用 lessons 文件。教训已由外脑落业务仓 `docs/lessons.md` Lesson 166（动词密集段语义选图局限+LocalWriter 统一图区约束，即执行体②所述）。修复轮：②说明末尾补「证据：docs/lessons.md Lesson 166」。2.【Q3 空说明】维护区③「[否] 」说明为空，须写一句实情。3.【Q4 语义修正】维护区④[是]但未改规划文件，应改[否]。

1. 【Q2】修复轮在维护区②说明末尾补「证据：docs/lessons.md Lesson 166」；教训实质为执行体第一轮自报，外脑仅代落库成文。
2. 【Q3】修复轮将维护区③说明补为实情（无档案/README 变更）。
3. 【Q4】修复轮将维护区④改[否]+实情（本卡为开发线实现，无线路图变更）。代码（分支已交付）无需重做。

## 人工批注

无

## 回写区

## 0. 卡标题复述

**任务卡 xy066 · 图文配图语义选图增强（开发线 Build）** — 补齐 xy062 遗留「配图占位」缺口：从文案正文按段落提取关键词（确定性纯函数，优先取标题/每段首句核心名词，复用 xy065 四段结构：钩子/痛点/干货/号召），每段选 1 张语义匹配真图；图文产物 `index.html` 每段配对应图、`image_paths` 指向真实 JPEG（≥5KB 校验沿用）；三级降级兜底 Pexels→picsum→本地设计化文字卡图（**不得再输出 `[MOCK IMAGES]` 文本占位**）；段落关键词提取、每段一图映射、降级链单测（mock 网络）全部真实通过。凭据读取沿用 `_pexels_key()`，日志不输出值。范围：`src/xianyu/content/image.py`、`src/xianyu/content/writer.py`、`tests/content/test_image.py`。

## 1. 探针输出

### 基线（HEAD=e2df97b，分支 codex/xy066-image-semantic）
```
$ git rev-parse HEAD
e2df97ba7c83c6e7e23caf1b183882caa4f72de3
$ git rev-parse origin/codex/xy066-image-semantic
e2df97ba7c83c6e7e23caf1b183882caa4f72de3        # = HEAD，已 push 对齐
$ git branch --show-current
codex/xy066-image-semantic
$ git status --short
?? .venv        # 环境符号链接（→/Users/fan/program/apps/xianyu/.venv），历来不提交
```

### 分支 diff vs 基线 cce5340（与卡白名单一致）
```
src/xianyu/content/image.py  | 254 +++++++++++++++++++++++++++++++++++++-
src/xianyu/content/writer.py |  37 +++++-
tests/content/test_image.py  | 284 ++++++++++++++++++++++++++++++++++++++++++-
3 files changed, 562 insertions(+), 13 deletions(-)
```

### 测试计数归因（本轮实测，修正上轮记录中的分项偏差）
- 基线 cce5340：`test_image.py` 5 个用例 + `test_writer.py` 17 个用例 = **22 基线**。
- xy066 新增：`test_image.py` 净增 22 = **23 新增 − 1 移除**（移除 `test_execute_reports_real_source_failure`——该基线用例断言网络失败即 `success=False`；xy066 行为变更后单图模式同样降级本地文字卡图 `success=True, source=local`，由新增 `test_execute_single_image_falls_back_to_local_card` 取代）。
- 现态：`test_image.py` 27 + `test_writer.py` 17 = **44**。
- **分项修正**：上轮记录「worker 语义/降级 6」实为 **5**（`semantic_paragraphs_one_image_each`/`semantic_from_content`/`semantic_degrades_to_local`/`semantic_reports_failure`/`single_image_falls_back_to_local_card`）。合计 7 关键词 + 3 段落切分 + 2 每段一图 + 6 三级降级 + 5 worker = **23 新增**，减 1 移除 = 净增 **22**。44 passed / 新增 22 两个主数字完全成立且可复现。

### 教训证据位置探针（维护区②关键）
- `docs/lessons.md` 于本分支存在（55,379 字节），最后一条为 Lesson 165——**Lesson 166 不在本分支文件树**，原因是外脑将其落库到 `origin/main` 提交 `e6bf28c`，其父提交 `cce5340` 即本分支基线；分支合并 main 后自然含该文档。如实记录，未在本分支伪造/复制该文档。
```
$ git log --format="%H %s" -1 e6bf28c
e6bf28c5119c7546a961571e2d8b09e9eed63bb4 docs(lessons): Lesson 166——动词密集段语义选图局限+LocalWriter 统一图区约束（xy066）
$ git log --format="%H %s" -1 e6bf28c^
cce53405e3dc1ffb78af5cbe1695f5e053b6a1bb merge(xy065): 文案切 3456 通道+闲鱼垂类四段结构——env 覆盖/Authorization 头/Ollama 可切回（86 测试绿）
```
- Lesson 166 内容（来源 origin/main 提交，`git show e6bf28c:docs/lessons.md` 可见）：① 动词密集段（钩子/痛点）产出动词性关键词（如「只挂/就卖掉/是不是也把」）语义精度有限，属确定性纯函数已知边界；② LocalWriter 渲染统一图区，段落→图映射以 `paragraph_images` 交付下游，逐段内联排版属后续卡范围。
- 本会话未改动 `docs/lessons.md`（教训为外脑落库，执行体只引用）。

### 方案文件探针（维护区①依据）
- `docs/projects/xy/plans/008-high-expression-v2.md`（CCC 仓）：状态=**部分执行**；关联卡含 **xy066**（原文：`> 关联卡：xy059、xy064、xy067、xy065、xy066`）。满足 docgate Q1 AND 校验。

### 凭据红线探针（3 个白名单文件）
- `grep PEXELS/pexels_key/api_key/secret`：仅 `image.py:58 _pexels_key()`（env/`.env`/共享凭据运行时读取，日志只记状态）+ 测试 mock `""/secret-not-printed`；**无任何真实凭据值写入文件/测试/日志/提交**。

## 2. 自测输出

### 门禁（验收命令，退出码 0）
```
$ /Users/fan/program/apps/xianyu/.venv/bin/pytest tests/content/test_image.py tests/content/test_writer.py -q
============================== 44 passed in 5.44s ==============================
```
（exit code 0；`.venv` 为指向主仓 venv 的符号链接，pytest 经 pyproject `pythonpath=["src"]` 导入**本 worktree 分支代码**——下方关键字探针已打印 `module file: .../xy066/src/xianyu/content/image.py` 证实。）

### 关键词提取示例（确定性纯函数，本轮逐条实测复现，与上轮记录完全一致）
复现命令：`.venv/bin/python -c "import sys; sys.path.insert(0,'src'); from xianyu.content.image import extract_keywords ..."`

| 段落（节选） | extract_keywords 输出 |
|---|---|
| 【干货】第一，定价看 7 天成交价，别拍脑袋。 | `['定价', '成交价', '别拍脑袋']` |
| 【3秒钩子】这台 iPhone 11 我只挂 3 天就卖掉了，赚了 900。 | `['只挂', '就卖掉']` |
| 【行动号召】想学的，去闲鱼搜「闲置变现」跟我实操。 | `['想学', '去闲鱼搜', '闲置变现']` |
| 空段 `""` / 纯标点 `"！！！？？？"` | `[]`（调用方落默认关键词 `好物推荐`） |
| 同一输入重复调用 | 恒等（determinism: True） |
| 去重：`手机很新，手机很新，手机很新` | `['手机很新']` |
| 首句限定：`定价看 7 天成交价。第二句提相机参数。` | `['定价', '成交价']`（相机不进入） |

> 机审 F1 疑点核销：`_TAIL_NOISE`（的了着过看要到出起上下后边里来去是在有吧吗呢啊）不含「掉」，`天就卖掉` 修剪后仍为 `就卖掉`，与代码实现及上轮示例完全一致——上轮示例无失实，本轮复跑再证。

### 每段一图映射 + 三级降级实测（无凭据 + picsum 离线 → source=local，真实 JPEG）
复现命令：mock `_pexels_key→''`、`_download_picsum→RuntimeError`，对 xy065 四段结构文案调 `select_images_for_paragraphs`：

| 段落（节选） | keyword | source | 大小 |
|---|---|---|---|
| 【3秒钩子】这台 iPhone 11 我只挂 3 天… | 只挂 | local | 56,791 B |
| 【痛点场景】你是不是也把闲置挂在角落… | 是不是也把 | local | 65,181 B |
| 【干货】第一，定价看 7 天成交价… | 定价 | local | 57,042 B |
| 【行动号召】想学的，去闲鱼搜「闲置变现」… | 想学 | local | 58,170 B |

- 每段恰好 1 图、`image_paths` 全部真实 JPEG 文件；`[MOCK IMAGES]` 文本断言 `not in data` 通过。
- 佐证已知边界（与 Lesson 166 一致）：痛点段（动词密集）产出动词性关键词 `是不是也把`，语义精度有限，属确定性纯函数边界，如实记录。
- 单图样例：`_render_local_card('闲置变现')` → 64,296 B、JPEG 1080×1440、PIL verify OK、含 `[MOCK IMAGES]`=False（同命令实测）。

### 相关套件（image_text 集成 / orchestrator / local_writer）
```
$ pytest tests/e2e/test_image_text_integration.py tests/test_orchestrator.py tests/storage/test_local_writer.py -q
======================== 20 passed, 4 warnings in 4.02s ========================
```

### 全量回归（无 xy066 归因失败，12 failed 全部归因实证）
```
污染态（本 worktree，workspace/ 有 e2e 产物目录时）：
============================ 12 failed, 783 passed, 8 skipped in 53.61s =========
```
失败清单（8 + 4，与上轮完全一致）：
```
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_article_item_has_all_preview_fields
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_empty_response_structure
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_items_separable_by_type
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_video_item_has_all_preview_fields
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_video_path_ends_with_mp4
FAILED tests/admin/test_preview.py::TestPreviewHelper::test_duration_format_contract
FAILED tests/admin/test_preview.py::TestPreviewHelper::test_empty_items_list_safe
FAILED tests/admin/test_preview.py::TestPreviewHelper::test_separate_videos_and_articles
FAILED tests/openclaw/test_plugin_integration.py::test_plugin_declares_xianyu_run_tool
FAILED tests/openclaw/test_plugin_integration.py::test_plugin_syntax_loads
FAILED tests/openclaw/test_plugin_integration.py::test_xianyu_run_help_via_module
FAILED tests/openclaw/test_plugin_integration.py::test_xianyu_run_module_invocation_path
```
归因（均与 3 个白名单文件无关）：
1. **openclaw 4 失败（基线与环境问题）**：失败详情为 `ERR_MODULE_NOT_FOUND: Cannot find package 'typebox' imported from openclaw-plugin/dist/index.js` —— openclaw-plugin Node 依赖缺失，属环境/依赖问题；上轮已证干净基线（cce5340）同样 4 failed，与本卡无关。
2. **admin preview 8 失败（workspace 污染，本轮直接实验证实）**：`workspace/outputs/image_text/` 为 gitignore 运行时目录，本仓 e2e 测试（image_text 集成 → LocalWriter 真实落盘）每次运行新增产物目录，`admin/api/server.py _scan_article_library()` 扫描该目录使 `/api/v1/library` 返回非空 → preview 8 用例断言失败。**隔离实验**：将该目录临时移出后跑 `pytest tests/admin/test_preview.py -q` → **13 passed, 1 warning**（13/13 全过），移回后恢复污染态 → 因果唯一指向 workspace 污染，属本仓测试隔离缺陷，非本卡。
3. 数量闭环：基线 22 + 净增 22 = 44（门禁全过）；全量 783 passed + 12 failed + 8 skipped = 803 与上轮一致，**xy066 新增 22 用例在门禁中全部通过，无新增失败**。

### 批注/机审闭环（修复轮核心）
机审「不通过」三条理由逐条处置：
1. **「44 passed/新增22 无法从分支代码与工作区复现」** → 复跑门禁得 `44 passed`（exit 0）；计数归因如上（22 基线 = 5+17；净增 22 = 23 新增 − 1 移除；现态 27+17=44）。主数字成立；分项「worker 语义/降级」由 6 修正为 5（详见探针节）。
2. **「关键词示例无法从分支代码与工作区复现」** → 三条示例 + 空段 + 纯标点逐条实测，输出与上轮记录**完全一致**；附复现命令与 `module file` 证据（导入的是本分支代码）。
3. **上轮人工批注三条（Q2/Q3/Q4）** → 已在维护区落实：②说明末尾含「证据：docs/lessons.md Lesson 166」；③说明补实情；④改[否]+实情。本轮复核闭环（Lesson 166 于 origin/main e6bf28c 存在且父提交=本分支基线；方案 008 部分执行+关联卡含 xy066；无档案/线路图变更）。

## 维护区

1. **方案同步**：[是] `src/xianyu/content/image.py`、`src/xianyu/content/writer.py`、`tests/content/test_image.py` 三文件交付于 `e2df97b`；本轮修复零代码改动，未触碰 LocalWriter/pipeline/密钥/数据库/既有产物；方案 xy-plan-008（部分执行，关联卡含 xy066）。
2. **教训沉淀**：[有] 动词密集段（钩子/痛点）产出动词性关键词（如「只挂/就卖掉/是不是也把」）语义精度有限，属确定性纯函数已知边界；LocalWriter 渲染统一图区而非逐段内联，段落→图映射以 `paragraph_images` 交付下游，逐段内联排版属后续卡范围。证据：docs/lessons.md Lesson 166（外脑落库 origin/main e6bf28c，父提交 cce5340=本分支基线；分支合并 main 后自然含该文档，本分支文件树如实暂缺）。
3. **档案/README**：[否] 本卡为开发线实现，无 docs/projects/xy/README.md 或项目档案变更（说明为实情，非空）。
4. **线路图**：[否] 本卡为图文配图语义化开发线实现，未修改 docs/roadmap.md 与 docs/projects/xy/README.md，无线路图变更（说明为实情，非空）。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：代码交付与红线零泄露成立，但执行结果存在不可独立复现的测试计数与关键词示例偏差（44 passed/新增22、示例输出均无法从分支代码与工作区复现），按审核红线须复跑门禁并修正记录后方可合入。
