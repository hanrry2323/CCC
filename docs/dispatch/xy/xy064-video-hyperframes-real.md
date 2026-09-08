# 任务卡 xy064 · 视频渲染 HyperFrames 真入口（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」、xy-plan-009「前端展示台」
> 执行体：DSH · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-08 · 版本：xy064 · 状态版本：1
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

## 人工批注

无

## 回写区

（待执行体回写）
