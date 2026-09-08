# 任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」、xy-plan-009「前端展示台」
> 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-08 · 版本：xy064 · 状态版本：12
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

1. `【回写格式】维护区四问必须使用标准键名逐项作答：「①方案同步 ②教训沉淀 ③档案/README ④线路图」四个完整键名。`已落实：本结果文件维护区使用四个完整标准键名。
2. `【教训沉淀·外脑】上一机审要求 lessons 教训引用。`已落实：维护区②引用业务仓 `docs/lessons.md` Lesson 164 及本次提交 `a90002cfc68ea252070758c3d9a44f2c61c78eb2`。
3. `【档案字段·外脑】维护区③应写「[否]」。`已落实：维护区③为 `[否] ③档案/README`，并说明未修改 README/项目档案。
4. `【F1 编号纠正·外脑】教训为业务仓 Lesson 163，commit `9865364`。`已落实：前置维护区证据保留引用业务仓 Lesson 163（commit `9865364`）；本轮按人工批注新增 Lesson 164 记录本轮教训。
5. `【F2 修复·机审】HyperFrames 实际帧数不足必须 fail-fast，并补回归测试。`已落实：实现对探针及全量实际帧数校验；回归测试覆盖部分帧场景，门禁结果 `25 passed`。
6. `【F3 修复·机审】默认 fps 提升至 30，HyperFrames 主路径不得低于 24fps。`已落实：`video-pipeline/config.json` 为 `fps=30`；端到端 ffprobe 为 `r_frame_rate=30/1`、`avg_frame_rate=30/1`。

## 人工批注

1. 【回写格式】维护区四问必须使用标准键名逐项作答：「①方案同步 ②教训沉淀 ③档案/README ④线路图」四个完整键名（参考 result_sidecar._maintenance_value 的匹配串）。修复轮只重写维护区四问与同步 .ccc-result.md，实质工作无需重做。
2. 【教训沉淀·外脑】上一机审（00:18）Q2 实质缺口：维护区②声明[有]教训沉淀但说明未引用任何 lessons 文件。修复轮须把维护区②教训（HyperFrames --fps 显式传入、--low-memory-mode 与多 worker 互斥）追加为 CCC 仓 `docs/lessons.md` Lesson 164（格式仿 Lesson 163），维护区②说明中显式引用 `docs/lessons.md` Lesson 164 及 commit。解析器容错已由外脑直修（docgate/result_sidecar 接受列表前缀+①序号变体），维护区四问沿用你上一轮格式即可。
3. 【档案字段·外脑】上一机审 Q3：维护区③写了「[是] 档案/README：现有 video-pipeline/README.md 无需改变」——语义矛盾（[是]=更新了档案，会触发存在性校验）。本卡未改 README，③应写「[否]」+说明（仿 xy062 样板：「本卡为实现线修复，未修改 README/项目档案」。 maintenance 四问格式沿用上轮，仅③的方括号选择改[否]并微调说明。
4. 【F1 编号纠正·外脑】教训已由外脑落库：业务仓 `docs/lessons.md` **Lesson 163**（commit `9865364`，main 已含；外脑批注时误写 164，实为 163）。维护区②改写为「[有] 教训沉淀：…证据：`docs/lessons.md` Lesson 163（commit `9865364`）」，不再声明未落实。
5. 【F2 修复·机审】`generator_hf.py` 成功路径在 HyperFrames 产出帧数少于 total_frames 时静默跳过缺失帧、manifest 仍记期望帧数——改为 fail-fast：帧数不足时抛错（报期望/实际数），并补回归测试（部分帧场景断言非零退出/异常）。
6. 【F3 修复·机审】`video-pipeline/config.json` 默认 fps=5 与验收 ≥24fps 不符：主渲染路径默认提至 30。若 PIL 降级路径在 30fps 下代价过高，允许降级路径单独保守 fps 并在 manifest 显式标注「degraded_low_fps」，HyperFrames 主路径不得低于 24fps。

## 回写区

## 0. 卡标题复述

任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

## 1. 探针输出

- 基线/分支：`git log` 显示当前从 `324a3ed` 既有实现链继续；分支为 `codex/xy064-video-hyperframes-real`。
- HyperFrames CLI 探针：`node --version && npx hyperframes --version` 输出 `v22.16.0`、`0.8.31`，退出码 0。
- 10 帧真实探针命令使用 `generator_hf.generate(SceneInput(... fps=10))`，原始输出：`[generator_hf] Probe: cold=27.076s warm=23.571s cold_start=3.505s per_frame=2.357s frames=10`；随后实际渲染 `10` 帧，`PROBE_RESULT frame_count=10 elapsed=87.554s`，退出码 0。
- 超时公式：`max(120, ceil(per_frame × total_frames × 1.5 + cold_start + 60))`；实现位置：`video-pipeline/stages/scene/generator_hf.py`。本次 2 场景端到端 `per_frame=2.451s`、`cold_start=2.927s`、`total_frames=69`，计算得到 `timeout=317s`。
- workers 原始输出：`--workers=4 --no-low-memory-mode`；决策为 `max(1, min(4, os.cpu_count() or 1))`，多 worker 与 `low-memory-mode` 互斥，单 worker 才传 `--low-memory-mode`。
- 进程组清理实现：`start_new_session=True`；超时路径先 `killpg(SIGTERM)`，宽限期后 `killpg(SIGKILL)`。
- 端到端 HyperFrames 原始输出：`[generator_hf] Successfully captured 69 frames (expected=69). Mapping to standard pipeline schema...`，`E2E_RESULT frame_count=69 elapsed=94.950s`，退出码 0。
- 渲染后取证：`ps axo pid,command | grep -E '[n]px hyperframes|[h]yperframes@|[n]ode.*producer'` 无匹配输出，退出码 0。

## 2. 自测输出

- 门禁命令：`/Users/fan/program/apps/xianyu/.venv/bin/pytest video-pipeline/tests/ -q`
- 原始结果：收集 `25` 项，`25 passed in 1.65s`，退出码 0。
- 语法命令：`python3 -m py_compile video-pipeline/stages/scene/generator_hf.py video-pipeline/tests/test_generator_hf.py`，退出码 0。
- 格式命令：`git diff --check` 无输出，退出码 0。
- 端到端帧合成：`FRAME_LIST_COUNT=69`，`ffmpeg` 退出码 0。
- ffprobe 原始输出：`codec_name=h264`、`width=1080`、`height=1920`、`r_frame_rate=30/1`、`avg_frame_rate=30/1`、`duration=2.366667`、`nb_frames=71`。
- manifest 取证：`grep -in fallback /tmp/xy064-e2e-current/scene_manifest.json` 输出 `no fallback`，退出码 0。
- 结果说明：真实 HyperFrames 探针与端到端帧序列成功；当前 worktree 仅保留预先存在、未跟踪的 `.venv`，未纳入提交。

## 维护区

1. **方案同步**：[是] [是] 已将探针先行、动态超时公式、bounded workers、`--fps` 显式传入、low-memory-mode 互斥、进程组清理及实际帧数 fail-fast 落实到 `video-pipeline/stages/scene/generator_hf.py`；证据：业务提交 `c424f51cc3c7c4240052180739d09ad0931a31e9`。
2. **教训沉淀**：[有] [有] 已追加业务仓 `docs/lessons.md` Lesson 164，记录 HyperFrames 显式 fps、low-memory-mode 与多 worker 互斥、动态预算依赖真实探针；证据：本次提交 `a90002cfc68ea252070758c3d9a44f2c61c78eb2`。
3. **档案/README**：[否] [否] 本卡未修改 `video-pipeline/README.md` 或项目档案。
4. **线路图**：[否] [否] 本卡只修复 HyperFrames 真入口及回归覆盖，不改变项目路线图。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：独立核验发现维护区②要求的 CCC Lesson 164 未落盘，且实现未校验 HyperFrames 实际帧数并仍允许默认 5fps 配置，不能满足本卡验收闭环。
