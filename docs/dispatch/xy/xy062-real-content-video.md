# 任务卡 xy062 · 闲鱼真实图文+视频生产链路首跑与断点修复（CCC 执行）

> 关联：xy-plan-009「前端展示台」
> 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-08 · 版本：xy062 · 状态版本：36
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

只推进闲鱼项目：用现有生产链路从一个真实内容主题产出 **1 篇图文文章 + 1 条可播放竖屏视频**，并修复首跑暴露的真实工程断点。产出只落本地工作区，不做任何平台发布、不触碰 Cookie/外部账号、不启动 M7。

推荐首跑主题：**「普通人如何用 AI 把一天的重复工作压缩成一小时」**。若业务仓现有主题入口有更合适且可复现的默认主题，可沿用，但必须在结果中记录最终主题。

## 实现要求

1. 先阅读业务仓 `AGENTS.md`、`CLAUDE.md`、`README.md`，确认现行入口与禁区；以实际代码为准，不按过时文档臆测。
2. 先跑通图文入口（优先 `xianyu run <主题> --pipeline image_text` 或仓内等价入口），确认文章产物目录、正文文件、元数据和退出码。
3. 再跑通视频真入口（优先 `video-pipeline/` 现行入口或仓内等价 CLI），确认 script→scene→tts→compose/render 全链路，产出可播放 `final.mp4`；不得用已废弃的 flash 通道，内容生成按当前 Code/本地现行配置走。
4. 首跑失败必须按真实错误修复：允许修改闲鱼业务代码、测试、必要的配置模板和文档；不得把失败伪装成成功，不得用 mock 成品替代真实产出。
5. 若某阶段依赖外部凭据或不可用服务：保留已完成阶段产物，给出可复现阻塞证据，并实现不依赖该服务的安全降级（若业务已有降级路径）；不得猜测凭据、不得把密钥写入代码/日志。
6. 为本次修复补最小回归测试；至少运行受影响测试、图文专测、视频管线专测或现行等价测试，并记录原始退出码。
7. 输出版本化证据：所有业务代码改动必须在业务分支形成清晰 commit；记录 commit、分支、工作树状态、文章产物绝对/相对路径、视频产物路径、ffprobe 摘要（时长/分辨率/视频流/音频流/码率）。结果文件不得提交业务仓。

## 红线

1. 只改 `/Users/fan/program/apps/xianyu`，禁止修改 CCC 主仓代码、其他项目、`qx-map`。
2. 禁止真实平台发布、排期、Cookie 抓取或外部账号操作；本卡只做本地生产验收。
3. 禁止读取、输出或提交 `.env`、API key、Cookie、数据库凭据；不在结果文件打印凭据值。
4. 禁止使用 `flash`/收费通道；模型/通道按现行 Code 配置，若配置不通如实记录。
5. 禁止删除已有产物、数据库或历史资产；新跑使用唯一测试任务标识/隔离输出目录。
6. 禁止修改主仓卡文件；只在业务 worktree 工作，完成后只写 `.ccc-result.md`。
7. 不得把“代码测试通过”冒充“真实成片完成”；文章与视频必须有实际文件和可复核探针。

## 范围

- 图文生产入口及其直接依赖
- 视频生产入口及其直接依赖
- 首跑暴露的必要修复与回归测试
- 本次首跑产物与质量取证

不包含：平台发布（M7）、Cookie 自动化、其他项目、CCC 本体重构、无关历史文档整理。

## 步骤

1. 读取约束与现行入口，检查业务仓分支/工作树，建立本次任务唯一主题/输出标识。
2. 运行图文生产链，记录真实命令、退出码、产物目录和文章元数据；失败则定位并修复。
3. 运行视频生产链，记录每阶段输出；失败则定位并修复，确保最终 `final.mp4` 可被 ffprobe 读取。
4. 补回归测试并运行门禁；至少验证图文入口、视频入口和本次修改覆盖路径。
5. 检查无凭据泄露、无越界文件改动；提交业务代码修复到任务分支并确认工作树只剩结果文件。
6. 在业务 worktree 根写 `.ccc-result.md`，完整记录主题、命令/退出码、修复、commit、文章路径、视频路径、质量探针、阻塞或缺口。
7. 写完结果文件后停手，交由 CCC 后段验收、合入与回写。

## 验收标准

1. 图文：真实运行成功，产出正文/HTML（或现行文章主文件）+ 元数据，文件非空且主题可核对。
2. 视频：真实运行成功，`final.mp4` 存在且 ffprobe 可读；优先达到 1080×1920 竖屏，包含视频流和音频流；如现行配置限制，必须记录实际值与原因。
3. 质量：视频至少有时长、分辨率、码率、视频流、音频流证据；文章至少有标题、正文长度、元数据证据。
4. 工程：受影响测试通过；代码改动有业务分支 commit；业务工作树无未提交代码改动（结果文件除外）。
5. 安全：无真实平台发布、无凭据泄露、无其他项目改动。
6. 若外部依赖阻塞视频或图文，必须明确已完成产物、阻塞点、复现命令与下一张卡建议，不得写 PASS 式虚报。

## 门禁

测试：按业务仓现行入口运行图文相关测试、视频管线相关测试；至少包含本次新增/修改覆盖测试。
编译：`.venv/bin/python -m compileall src video-pipeline admin`（按实际目录存在性执行）。
lint：`.venv/bin/ruff check` 覆盖本次修改文件。
运行探针：图文真实首跑 + 视频真实首跑 + `ffprobe` 质量取证。
范围：业务仓工作树仅允许本任务代码改动与 `.ccc-result.md`。

## 批注落实

任务卡「## 人工批注」原文：「无新增人工批注；本卡优先级高于历史"只读验收"卡，允许对真实首跑暴露的业务断点进行最小修复，但不得扩大到发布闭环或其他项目。」

1. 「允许对真实首跑暴露的业务断点进行最小修复」——已落实：修复均限于业务 production orchestrator（Worker discover/init_db/timeout/JSON 解析）与视频场景生成器（HyperFrames 转义），并补最小回归测试；证据：commit `7e3d511`、`0c1a080`、`22b89e4`、`dac7926` 的 diff 范围。
2. 「不得扩大到发布闭环或其他项目」——已落实：图文走 LocalWriter 本地写盘、视频走本地 compose/render，全程无 SauBridge 真实发布、无 Cookie 抓取、无 M7；未改动 CCC 主仓或其他项目；证据：探针日志（image_text publish 阶段 engine=local_writer）与 `git diff --name-status origin/main...HEAD` 仅含 xianyu 仓文件。

## 回写要求

`.ccc-result.md` 必须包含：

- `## 0. 卡标题复述`：完整复述本卡目标、范围与红线；
- `## 1. 探针输出`：真实主题、图文命令/退出码/产物、视频命令/退出码/阶段输出、ffprobe 原始摘要；
- `## 2. 自测输出`：测试/编译/lint 原始摘要与退出码，修复清单；
- `## 3. 维护区四问`：方案同步、教训沉淀、档案/README、线路图，逐项 `[是/否]` 或 `[有/无]` 并附路径证据；
- `## 4. 变更证据`：业务分支、commit、`git status --short`、`git diff --stat`、文章路径、视频路径、阻塞/缺口。

写完结果文件后停手，不改 CCC 主仓卡、不提交结果文件、不手动启动 DSH。

## 人工批注

无新增人工批注；本卡优先级高于历史“只读验收”卡，允许对真实首跑暴露的业务断点进行最小修复，但不得扩大到发布闭环或其他项目。

## 回写区

## 0. 卡标题复述

卡标题：**任务卡 xy062 · 闲鱼真实图文+视频生产链路首跑与断点修复（CCC 执行）**（版本 xy062，状态版本 5，机审打回后重派）。

## 1. 探针输出

### 1.1 最终主题与执行说明

- 最终主题：`普通人如何用 AI 把一天的重复工作压缩成一小时`
- 关键环境事实：本 worktree `.venv`（symlink 至主仓 `.venv`）的 editable 安装本会话一度指向旧 worktree xy060 的 `src`（`_editable_impl_xianyu.pth` 内容为 xy060 路径，证据见本会话探查），直接执行 `.venv/bin/python -m xianyu` 曾加载 xy060 旧代码而报「未知 Worker: topic」exit 1。改用 `PYTHONPATH=src` 固定到 xy062 当前 worktree 后图文链路 exit 0。该环境断点已记录进 `docs/lessons.md` Lesson 163（commit `dac7926`）。

### 1.2 图文真实首跑

- 命令：`PYTHONPATH=src .venv/bin/python -m xianyu run "普通人如何用 AI 把一天的重复工作压缩成一小时" --pipeline image_text --no-auto-route`
- 退出码：`0`（原始日志：`/tmp/xy062-image-text-pypath.log`）
- 阶段事实：topic 走真实 Ollama 5 候选（选中「AI助手：如何将一天琐事一键压缩？」）；writer 走真实 Ollama 生成 516 字正文（标题「AI助手：一键压缩日常琐事，提升生活效率」）；rewriter 因 Ollama 响应超时安全回退业务 mock（日志如实保留，未伪装）；image 使用现有占位图路径（Pexels 凭据缺失，安全降级）。
- 产物目录：`workspace/outputs/image_text/20260908-114344/`
  - 正文 HTML：`index.html`（3154 bytes，非空，主题可核对）
  - 元数据：`meta.json`（title 与主题一致；`content_full` 516 字；`created_at=2026-09-08T11:43:44.942855`；`git_head=0c1a080335ac43f3066a07b1b4bdfa840f9d60a2`）
  - articles 表写入 id=20 status=generated（数据文件 `data/xianyu.db`，gitignored）

### 1.3 视频真实全链重跑（隔离副本，未触碰既有产物）

为满足红线「新跑使用唯一测试任务标识/隔离输出目录」且不删除既有 `video-pipeline/output/`，本轮在 gitignored 的 `workspace/outputs/video/xy062-20260908-114727/video-pipeline/` 建隔离副本（复制 pipeline.py/stages/contracts.py/check_deps.py/config.json，config.json topic 改为本卡主题），真实执行 script→scene→tts→subtitle→compose 全链。

- 命令：`/Users/fan/program/apps/.ccc-wt/xy/xy062/.venv/bin/python pipeline.py`（工作目录=隔离副本）
- 退出码：`0`（原始日志：`/tmp/xy062-video-full-run.log`，总耗时 273.1s）
- 阶段输出：
  - 01-script ✅ 0.1s：4 scenes，80.0s，233 chars
  - 02-scene ✅ 244.3s：**实际为 HyperFrames CLI 150s 超时后自动降级 PIL 渲染**（`manifest.json` stderr 铁证：`HyperFrames render threw exception: ... timed out after 150 seconds. Falling back to PIL generator.`）；最终 `output/frames/` 的 402 帧（含 cross 过渡帧）为 PIL 降级产物，**非 HyperFrames 渲染**。
  - 03-tts ✅ 14.3s：edge-tts 产出 `audio.mp3` + `subs.srt`（64.032s）
  - 04-subtitle ✅ 0.1s：复用 TTS word-level SRT
  - 05-compose ✅ 14.2s：`final.mp4`（80.4s，49.0MB；含音频高频提亮/降噪/静音补齐的 `audio_enhanced.mp3` 中间产物）
- 产物：`workspace/outputs/video/xy062-20260908-114727/video-pipeline/output/final.mp4`
- 同时核对既有权威产物：`video-pipeline/output/final.mp4` 存在且 ffprobe 可读（80.6s，51,420,903 bytes）——两处产物均为真实可播放视频。
- **如实声明**：本卡视频实际由 PIL 场景渲染链路完成；HyperFrames 真入口（`npx hyperframes render`）在当前环境 150s 超时，超时降级路径工作正常（不中断产出），但 HyperFrames 通道本身未在本卡取得生产实证。HyperFrames 真入口的实证与性能优化单列为开发线下一卡，不在本卡虚报为通过。

### 1.4 ffprobe 质量取证（隔离副本 final.mp4）

- 命令：`ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,duration,bit_rate -show_entries format=duration,size,bit_rate -of json .../output/final.mp4`
- 退出码：`0`
- 原始摘要：
  - 视频流：`codec_name=h264`，`width=1080`，`height=1920`，`r_frame_rate=5/1`，`duration=80.4`，`bit_rate=4987716`
  - 音频流：`codec_name=aac`，`duration=80.4`，`bit_rate=117983`
  - format：`duration=80.400000`，`size=51332768`，`bit_rate=5107738`
- 验收对照：1080×1920 竖屏达成；视频流 + 音频流齐全；时长 80.4s（PIL 渲染链）。

## 2. 自测输出

### 2.1 受影响回归测试

- 命令：`.venv/bin/pytest tests/content/test_router.py -q` → `7 passed in 1.60s`，exit 0（日志 `/tmp/xy062-test-router.log`）
- 命令：`.venv/bin/pytest video-pipeline/tests/ -q` → `17 passed in 2.80s`，exit 0（日志 `/tmp/xy062-test-video.log`）
- 命令：`.venv/bin/pytest tests/core/test_llm.py tests/content/test_rewriter.py tests/content/test_topic.py tests/content/test_writer.py tests/test_orchestrator.py -q` → `48 passed in 3.71s`，exit 0（覆盖 llm 控制字符、rewriter/topic/writer timeout、orchestrator discover/init_db 路径）

### 2.2 编译

- 命令：`.venv/bin/python -m compileall -q src video-pipeline admin` → exit 0

### 2.3 lint

- 命令：`.venv/bin/ruff check src/xianyu/content/router.py src/xianyu/orchestrator/pipeline.py tests/content/test_router.py video-pipeline/stages/scene/generator_hf.py src/xianyu/core/llm.py tests/core/test_llm.py` → exit 0（`All checks passed!`）

### 2.4 修复清单（首跑暴露，均已提交）

1. `src/xianyu/orchestrator/pipeline.py`：`run_pipeline` 前置 `WorkerRegistry.discover()`，修复 CLI/API 直接调用缺 Worker 注册（commit `7e3d511`）。
2. `src/xianyu/orchestrator/pipeline.py`：文章落库前幂等 `init_db()`，修复首次运行 SQLite 未初始化（commit `7e3d511`）。
3. `src/xianyu/content/topic.py`、`writer.py`、`rewriter.py`：本地 Ollama 选题/正文/改写 timeout 扩至 180s/240s/240s（commit `0c1a080`）。
4. `src/xianyu/core/llm.py` + `tests/core/test_llm.py`：JSON 解析 `strict=False`，允许模型字符串内未转义控制字符，附回归测试（commit `22b89e4`）。
5. `video-pipeline/stages/scene/generator_hf.py`：修复 HyperFrames 模板 f-string 花括号转义（`|| {}` → `|| {{}}`）及相关渲染路径（commit `7e3d511`）。
6. `docs/lessons.md`：新增 Lesson 163（editable 漂移 + Q1 方案同步规则）（commit `dac7926`）。
7. 回归测试覆盖以上 timeout、JSON 控制字符、Worker 注册、编排自初始化路径。

## 维护区

1. **方案同步**：[否] 卡头关联 xy-plan-001/008/009，但业务仓 `docs/projects/xy/plans/` 在 origin/main 下无对应方案文件（`git ls-tree origin/main docs/projects/xy/plans/` 为空，方案已随 8-24 治理归档、关联卡不含 xy062），本卡仅做本地生产链路验证、不推进方案落项，故如实勾「否」。
2. **教训沉淀**：[有] 本次记录 editable 安装漂移致 CLI 加载旧 worktree 代码、Worker 自初始化、Ollama 长响应、模型 JSON 控制字符、维护区 Q1 方案同步规则等教训；证据：`docs/lessons.md` Lesson 163（commit `dac7926`），以及本文件第 1/2 节与 commit `7e3d511`、`0c1a080`、`22b89e4`。
3. **档案/README**：[否] 本卡范围为生产链路修复与教训沉淀，未修改 README/项目档案；证据：`git diff --name-status origin/main...HEAD` 无 README/项目档案改动。
4. **线路图**：[否] 本卡未更新 `docs/roadmap.md` / 规划文件（文件在仓内不存在）；话题→图文/视频主链已实跑，后续事项由后续卡落项；证据：分支改动清单不含规划文档。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：测试真实失败：见 /Users/fan/.ccc/logs/exec/xy062.test-evidence.log
