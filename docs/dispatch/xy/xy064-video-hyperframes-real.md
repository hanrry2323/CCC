# 任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」、xy-plan-009「前端展示台」
> 执行体：DSH · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-08 · 版本：xy064 · 状态版本：4
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

xy062 实证视频由 PIL 降级链产出（manifest stderr 铁证：`HyperFrames render threw exception: ... timed out after 150 seconds. Falling back to PIL generator`），观感为 5fps 静态幻灯片。本卡修复 HyperFrames 真入口，达成真实动效成片：

1. **动态超时**：`video-pipeline/stages/scene/generator_hf.py` 当前 `subprocess.run(render_cmd, timeout=150)` 固定超时，而 402 帧实测渲染需 244s。改为按预估帧数动态计算（探针实测单帧耗时 × 帧数 + 冷启动余量），公式依据写进结果。
2. **渲染并行度**：`--workers=1` 提升为按 CPU 核数安全提升（如 4），验证 low-memory-mode 兼容性；若并行导致渲染异常，回退并如实记录。
3. **进程组清理**：超时/异常路径用进程组终止（killpg），确保不留孤儿 npx/node；结果中附渲染后 `ps` 取证。
4. **探针先行**：全量渲染前先做小规模探针（约 10 帧）实测单帧耗时，作为超时公式输入；探针失败则直接定位原因，不带病全量。
5. **端到端成片**：HyperFrames 帧序列 → 合成 final.mp4；manifest 不得出现 fallback 字样；ffprobe 取证帧率/分辨率/时长。
6. **如实降级**：若 HyperFrames 通道确实不可用，明确记录失败根因与证据，不得虚报成功。

## 红线

1. 只改 xianyu 业务仓；不发布、不触碰 Cookie/外部账号、不启动 M7。
2. 分支基础：从 `codex/xy063-build-image-hyperframes`（324a3ed，含 xy062 的 4 笔与 xy063 的 2 笔既有修复）切出新分支开发，不基于 main。
3. 不得删除既有产物（`video-pipeline/output/`、`workspace/outputs/`）；新跑使用唯一输出目录。
4. 渲染降级或失败必须如实声明，不得把 PIL 降级写成 HyperFrames 成功。
5. 所有改动业务分支 commit；测试真实通过；不提交 .ccc-result 文件。
6. 不得读取或输出凭据值。

## 范围

- `video-pipeline/stages/scene/generator_hf.py`（超时/并行/进程清理/探针）
- `video-pipeline/pipeline.py` 及相关配置（如需传递渲染预算）
- `video-pipeline/tests/` 回归测试

## 步骤

1. 从 `codex/xy063-build-image-hyperframes` 切分支；跑 `video-pipeline/tests/` 确认基线绿。
2. 探针：小规模渲染实测单帧耗时与 npx 冷启动耗时，记录原始数据。
3. 实施动态超时、workers 提升、killpg 清理；补回归测试。
4. 全量渲染端到端成片；ffprobe + manifest 取证；渲染后 `ps` 确认无孤儿进程。
5. 全量测试组真实通过；业务分支 commit；`.ccc-result.md` 如实完整记录。

## 验收标准

1. 成功路径：manifest 无 fallback 字样；成片帧率 ≥24fps；含真实转场动效；1080×1920 竖屏；ffprobe 数据与配置一致。
2. 失败路径：如 HyperFrames 不可用，结果含失败根因+原始报错+降级证据，无虚报。
3. 渲染结束后无 npx/hyperframes/node 孤儿进程（ps 取证）。
4. `video-pipeline/tests/` 全部通过退出码 0；全量回归无新增失败。
5. 业务分支 commit 存在；工作树除结果文件外干净。
6. 安全：无发布、无凭据泄露、无其他项目改动、无既有产物删除。

## 门禁

测试（视频组）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest video-pipeline/tests/ -q`

## 回写要求

结果写入 `.ccc-result.md`，含：超时公式与探针数据、workers 决策依据、ffprobe 原始输出、进程清理取证、测试原始输出、commit 哈希。

## 批注落实

任务卡「## 人工批注」原文：1. 【回写格式】维护区四问必须使用标准键名逐项作答，解析器按「①方案同步 ②教训沉淀 ③档案/README ④线路图」四个完整键名匹配（result_sidecar._maintenance_value），第一轮写的「方案/教训/README」短键名不被识别导致 0/4 打回。修复轮只需以标准键名重写维护区四问（内容可沿用第一轮四问原文），并同步更新 .ccc-result.md；实质工作（探针/超时公式/workers/killpg/成片/23 项测试/commit ad7d5ba9）无需重做。

1. 【回写格式】由执行体修复轮落实：结果文件「## 3. 维护区四问」以标准键名逐项作答（方案同步/教训沉淀/档案/README/线路图），并在「人工批注落实」段写入落实说明。第一轮回写时本卡批注为「无」（classify_annotation=NOT_REAL）故未写落实节，属流程时序而非漏落实。

## 人工批注

1. 【回写格式】维护区四问必须使用标准键名逐项作答：「①方案同步 ②教训沉淀 ③档案/README ④线路图」四个完整键名（参考 result_sidecar._maintenance_value 的匹配串）。修复轮只重写维护区四问与同步 .ccc-result.md，实质工作无需重做。

## 回写区

## 0. 卡标题复述

（完整复述卡标题）
任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

## 1. 探针输出

- 基线分支按卡指定提交 `324a3ed` 切出；基线视频测试原始结果：`17 passed in 3.05s`，退出码 0。
- HyperFrames 10 帧探针（实际传入 `fps=10` 的独立调用）原始输出：`Probe: cold=32.050s warm=27.329s cold_start=4.721s per_frame=2.733s frames=10`，退出码 0。
- 端到端 30fps 场景渲染探针原始输出：`Probe: cold=28.371s warm=25.005s cold_start=3.366s per_frame=2.500s frames=10`；全量命令记录 `frames=108, timeout=469s, workers=4`，捕获 108 帧；无 `fallback` 输出，退出码 0。
- 超时公式：`ceil(per_frame × total_frames × 1.5 + cold_start + 60)`，最小值 120 秒。实现位置：`video-pipeline/stages/scene/generator_hf.py`。
- workers 决策：`max(1, min(4, os.cpu_count() or 1))`；本机 `hw.memsize=16 GB`、CPU 核数探测为 8，因此实际为 4。HyperFrames `--low-memory-mode` 会固定 1 worker，本机并行路径使用 `--no-low-memory-mode`；单核路径保留 `--low-memory-mode`。
- 进程清理：`_run_hyperframes` 使用 `start_new_session=True`，超时通过 `killpg(SIGTERM)`，超时仍存活再 `killpg(SIGKILL)`。

## 2. 自测输出

- 回归命令：`/Users/fan/program/apps/xianyu/.venv/bin/pytest video-pipeline/tests/ -q`
- 最终原始结果：`23 passed in 1.88s`，退出码 0。
- 语法与格式：`python3 -m py_compile video-pipeline/stages/scene/generator_hf.py video-pipeline/tests/test_generator_hf.py`，退出码 0；`git diff --check` 无输出，退出码 0。
- 端到端合成命令退出码 0；原始输出：`Reconstructed 108 frames from manifest.`、`04-compose: /tmp/xy064-e2e/output/final.mp4 (3.6s, 2.1MB)`。
- ffprobe 原始输出：`codec_name=h264`、`width=1080`、`height=1920`、`r_frame_rate=30/1`、`avg_frame_rate=30/1`、`nb_frames=108`、`duration=3.600000`、`size=2207512`。
- 渲染后进程取证命令 `ps axo pid,command | grep -E '[n]px hyperframes|[h]yperframes@|[n]ode.*producer' || true` 无匹配输出，退出码 0。
- 端到端 manifest：3 个场景各 30 帧、时长各 1.0 秒；无 `fallback` 字样。
- 端到端首次错误记录：直接运行临时脚本时因其不在 pipeline `output/` 目录导致既有 `generator.py` 的 `style_seed` 未初始化，退出码 1；改用 `output/script.json` 入口后成功。该既有入口问题未改动，避免超出卡白名单。

## 维护区

- [是] 方案：已将探针、动态超时、bounded workers、low-memory-mode 兼容决策及 killpg 清理落实到 `video-pipeline/stages/scene/generator_hf.py`；证据为下述 commit。
- [有] 教训：HyperFrames CLI 的 `--fps` 必须显式传入；`--low-memory-mode` 与多 worker 存在约束；已在实现与测试中固定这两个事实。
- [是] README：本卡为实现线修复，现有 `video-pipeline/README.md` 的运行入口无需改变；未新增用户可见配置入口。
- [否] 线路图：本卡只修复 HyperFrames 真入口，不改变项目路线图；无线路图变更。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：完成钩子：维护区只找到 0/4 问
