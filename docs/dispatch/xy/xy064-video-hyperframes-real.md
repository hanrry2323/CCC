# 任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」、xy-plan-009「前端展示台」
> 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-08 · 版本：xy064 · 状态版本：22
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

1. 【回写格式】→ 已落实；本结果文件第 3 节按「①方案同步 ②教训沉淀 ③档案/README ④线路图」四个完整键名逐项作答。
2. 【教训沉淀·外脑】→ 已落实；第 3 节②引用 CCC 仓 `docs/lessons.md` Lesson 164（commit `fe3fadbdc`）与业务仓 `docs/lessons.md` Lesson 163（commit `9865364`）。
3. 【档案字段·外脑】→ 已落实；第 3 节③为 `[否]`，说明本卡为实现线修复未修改 README/项目档案。
4. 【F1 编号纠正·外脑】→ 已落实；第 3 节②明确引用业务仓 main 的 Lesson 163（commit `9865364`），不再误写 164；维护区②为 `[有]`。
5. 【F2 修复·机审】→ 已落实（前轮 `c424f51`/`2723edf`）；本轮门禁全量 `31 passed`（含帧数不足 fail-fast 回归，先于本轮 commit 已存在）。
6. 【F3 修复·机审】→ 已落实（前轮）；fps 30 主路径证据在前轮回写区 ffprobe `r_frame_rate=30/1`，本轮不改配置。
7. 【F4 修复·第6轮机审】→ 已落实（`c9a2aa0` 分层 catch）；本轮全量回归 `31 passed`（含 `test_scene_run_bubbles_hyperframes_data_error` / `test_scene_run_falls_back_to_pil_on_ordinary_hf_error`）。
8. 【F5 修复·第7轮机审】→ 已落实（`4336009`）；`test_generate_bubbles_probe_data_error_instead_of_fallback` 定向 `1 passed`（见第 2 节）。
9. 【F6 修复·第8轮机审】→ 已落实（本轮 commit `14ab750`）：①探针数据异常 re-raise 前 `shutil.rmtree(hf_project_dir, ignore_errors=True)`（`generator_hf.py` 探针 except 分支）+ 新增回归 `test_generate_removes_project_before_bubbling_probe_data_error`；②进程组清理收敛：`_run_hyperframes` 统一 finally，`_terminate_process_group` 覆盖非零退出/OSError/超时全失败分支（不再因 leader 已退出而早退），新增回归 `test_run_hyperframes_nonzero_exit_kills_orphan_children`（断言组内无残留子进程）与 `test_run_hyperframes_oserror_kills_process_group`（断言 OSError 后进程组终止）；③全部定向测试通过，见第 2 节。

## 0. 卡标题复述

任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

## 0. 卡标题复述

任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

## 人工批注

1. 【回写格式】维护区四问必须使用标准键名逐项作答：「①方案同步 ②教训沉淀 ③档案/README ④线路图」四个完整键名（参考 result_sidecar._maintenance_value 的匹配串）。修复轮只重写维护区四问与同步 .ccc-result.md，实质工作无需重做。
2. 【教训沉淀·外脑】上一机审（00:18）Q2 实质缺口：维护区②声明[有]教训沉淀但说明未引用任何 lessons 文件。修复轮须把维护区②教训（HyperFrames --fps 显式传入、--low-memory-mode 与多 worker 互斥）追加为 CCC 仓 `docs/lessons.md` Lesson 164（格式仿 Lesson 163），维护区②说明中显式引用 `docs/lessons.md` Lesson 164 及 commit。解析器容错已由外脑直修（docgate/result_sidecar 接受列表前缀+①序号变体），维护区四问沿用你上一轮格式即可。
3. 【档案字段·外脑】上一机审 Q3：维护区③写了「[是] 档案/README：现有 video-pipeline/README.md 无需改变」——语义矛盾（[是]=更新了档案，会触发存在性校验）。本卡未改 README，③应写「[否]」+说明（仿 xy062 样板：「本卡为实现线修复，未修改 README/项目档案」。 maintenance 四问格式沿用上轮，仅③的方括号选择改[否]并微调说明。
4. 【F1 编号纠正·外脑】教训已由外脑落库：业务仓 `docs/lessons.md` **Lesson 163**（commit `9865364`，main 已含；外脑批注时误写 164，实为 163）。维护区②改写为「[有] 教训沉淀：…证据：`docs/lessons.md` Lesson 163（commit `9865364`）」，不再声明未落实。
5. 【F2 修复·机审】`generator_hf.py` 成功路径在 HyperFrames 产出帧数少于 total_frames 时静默跳过缺失帧、manifest 仍记期望帧数——改为 fail-fast：帧数不足时抛错（报期望/实际数），并补回归测试（部分帧场景断言非零退出/异常）。
6. 【F3 修复·机审】`video-pipeline/config.json` 默认 fps=5 与验收 ≥24fps 不符：主渲染路径默认提至 30。若 PIL 降级路径在 30fps 下代价过高，允许降级路径单独保守 fps 并在 manifest 显式标注「degraded_low_fps」，HyperFrames 主路径不得低于 24fps。
7. 【F4 修复·第6轮机审】`stages/scene/generator.py:775` 的 `except Exception` 把 generator_hf 的帧数不足 fail-fast（RuntimeError）吞掉后静默切 PIL 且无标记——修法：①generator_hf.py 定义 `class HyperFramesDataError(RuntimeError)`，帧数不足两处 raise 改用它；②generator.py catch 分层：`except HyperFramesDataError: raise`（数据完整性异常冒泡使流水线失败）+ `except Exception` 才降级 PIL；③补回归测试（部分帧场景断言 HyperFramesDataError 冒泡、不被吞）。另：F1 已由外脑闭环——CCC 仓 docs/lessons.md 已落 Lesson 164（commit 见 main），本轮维护区②无需再改。
8. 【F5 修复·第7轮机审】`generator_hf.py` generate() 内部包裹 `_probe_timing()` 的 `except (OSError, subprocess.SubprocessError, TimeoutError, RuntimeError)`（:351 附近）把探针阶段抛出的 HyperFramesDataError 也捕获转 PIL——修法：该 except 体首行加 `if isinstance(exc, HyperFramesDataError): raise`（数据完整性异常冒泡，仅环境类异常允许降级）；补回归测试：mock 探针部分帧场景，断言 generate() 向上抛 HyperFramesDataError 而非返回 PIL 降级结果。
9. 【F6 修复·第8轮机审】失败路径零残留收尾（本轮机审仅剩两点）：①generate() 中 re-raise HyperFramesDataError 前（及一切向 上冒泡的 except 分支）先 `shutil.rmtree(hf_project_dir, ignore_errors=True)`，保证失败运行零残留；②非超时异常路径（非零退出/OS 错误）同样保证进程组清理——将 killpg 清理收敛到统一的 finally/单一清理函数，覆盖所有失败分支；③各补一条回归测试（失败路径断言 hf_project 不存在、无孤儿进程）。

## 回写区

## 0. 卡标题复述

任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

## 1. 探针输出

- HyperFrames CLI 可用性探针：`npx hyperframes --version` → `0.8.32`，`EXIT=0`。
- 渲染进程取证（本轮修改后的失败路径清理行为，通过真实子进程回归驱动）：`test_run_hyperframes_nonzero_exit_kills_orphan_children` 用真实 `/bin/sh -c 'sleep 60 >/dev/null 2>&1 & sleep 0.3; exit 3'`，非零退出后 killpg 清理，轮询 `os.killpg(pgid, 0)` 直至组内无可信号成员，原始轮询结果（5 次独立试运行）：`EPERM`/`ESRCH`（macOS 消亡窗口语义，两种均代表组内无活成员），未出现超时残留。
- 探针数据异常冒泡前清理（`test_generate_removes_project_before_bubbling_probe_data_error`）：`_probe_timing` mock 抛出 `HyperFramesDataError("probe render 1 produced insufficient frames: expected=10, actual=1")` 后，断言 `(out / "hf_project").exists() == False`，失败运行零残留。
- 前轮真实渲染探针数据（本 F6 轮未重跑全量，沿用卡回写区既有记录）：`Probe: cold=34.087s warm=26.800s cold_start=7.287s per_frame=2.680s frames=10`；动态超时公式 `timeout = max(120, ceil(per_frame × total_frames × 1.5 + cold_start + 60))`。

## 2. 自测输出

- 门禁命令：`/Users/fan/program/apps/xianyu/.venv/bin/pytest video-pipeline/tests/ -q`
  - 原始结果：`31 passed in 2.29s`（`test_compose_bgm 6 + test_generator_hf 14 + test_scene_templates 5 + test_tts_emotion_selector 6`）
  - 退出码：`0`。
- 定向回归：`/Users/fan/program/apps/xianyu/.venv/bin/pytest video-pipeline/tests/test_generator_hf.py -q`
  - 原始结果：`14 passed in 1.64s`（新增 F6 三条 + F5/F4 既有回归在内）
  - 退出码：`0`。
- 语法检查：`/Users/fan/program/apps/xianyu/.venv/bin/python -m py_compile video-pipeline/stages/scene/generator_hf.py video-pipeline/tests/test_generator_hf.py` → 无输出，退出码 `0`。
- 差异检查：`git diff --check` → 无输出，退出码 `0`。
- 渲染后进程取证：`ps axo pid,command | grep -E '[n]px hyperframes|[h]yperframes@|[n]ode.*producer'` → 无匹配输出（无孤儿渲染进程）。

## 维护区

1. **方案同步**：[是] F6（第8轮机审两点收尾）已落实：探针数据异常 re-raise 前清理临时工程零残留；进程组清理收敛为 `_run_hyperframes` 统一 finally + `_terminate_process_group` 单一清理函数，覆盖非零退出/OSError/超时全失败分支。连同前轮动态超时、bounded workers、`--fps`、探针/全量帧数 fail-fast、scene.run 分层 catch，证据 commit：`14ab750`（本轮）、`4336009`（F5）、`c9a2aa0`（F4）、`c424f51`/`2723edf`（F2）、`ad7d5ba`；门禁 `31 passed`。
2. **教训沉淀**：[有] HyperFrames 失败路径须同时满足「零残留 + 进程组清理」：leader 退出后子进程仍可存活，killpg 必须在统一 finally 中对全部失败分支生效且不能因 leader 已退出而早退；macOS 上刚被 SIGTERM 的组 killpg(0) 可能报 EPERM 而非 ESRCH，断言应以「组内无可信号成员」为准。证据：CCC 仓 `docs/lessons.md` Lesson 164（commit `fe3fadbdc`）、业务仓 main `docs/lessons.md` Lesson 163（commit `9865364`）。
3. **档案/README**：[否] 本卡为实现线修复，未修改 README/项目档案。
4. **线路图**：[否] 本卡只修复 HyperFrames 真入口的失败清理与回归覆盖，不改变项目路线图。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：探针数据异常冒泡修复已存在，但失败路径未清理临时工程且非超时异常/非零退出未保证进程组清理，当前不满足零残留与异常清理验收条件。
