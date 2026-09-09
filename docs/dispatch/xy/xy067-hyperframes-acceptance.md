# 任务卡 xy067 · HyperFrames 真入口验收闭环（开发线 Build · 业务代码已在 main）

> 关联：xy-plan-008「视频高表现力二期」、xy-plan-009「前端展示台」 · 执行体：DSH · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-09 · 版本：xy067 · 状态版本：1
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

xy064 的业务修复已全部合入 xianyu main（`f2ad113`，含 F1-F8：动态超时/workers/killpg/帧数 fail-fast/零残留/DataError 冒泡，35 项 video-pipeline 测试绿）。本卡完成「HyperFrames 真入口」的验收闭环（机审 PASS→关闭），不重复开发：

1. **独立核验**：确认 main 上 `video-pipeline/stages/scene/generator_hf.py` 动态超时、`_terminate_process_group`、`HyperFramesDataError` 冒泡等修复在位且与卡要求一致。
2. **端到端取证**：用当前配置（fps=30）重跑一次全量端到端渲染，`.ccc-result.md` 附原始 ffprobe 输出（codec/分辨率/帧率/时长）与 manifest 原文；无 fallback 字样；渲染后 `ps` 无孤儿进程。
3. **维护区四问**：以标准键名（①方案同步②教训沉淀③档案/README④线路图）如实作答；教训已落 `docs/lessons.md` Lesson 163/164（main 已含），②引用之。

## 实现要求

1. 不新增业务代码改动（main 已含全部修复）；仅验证+取证+如实回写。
2. 若发现 main 与卡验收标准不一致，如实记录并打回说明，不擅自改代码。

## 红线

1. 只改 xianyu 业务仓；不发布、不触碰 Cookie/外部账号、不启动 M7。
2. 不得删除既有产物；新跑使用唯一输出目录。
3. 结果如实记录；不得伪造 ffprobe/manifest 数据。
4. 不读取或输出凭据值。

## 范围

- `/Users/fan/program/apps/xianyu/video-pipeline/stages/scene/generator_hf.py`
- `/Users/fan/program/apps/xianyu/video-pipeline/tests/test_generator_hf.py`
- `/Users/fan/program/apps/xianyu/video-pipeline/config.json`
- `docs/lessons.md`

## 步骤

1. 确认 main 分支与代码在位；跑 `video-pipeline/tests/` 记录基线。
2. 用当前配置（fps=30）重跑全量端到端渲染，记录 ffprobe 原始输出与 manifest 原文。
3. 渲染后 `ps` 验证无孤儿进程。
4. 如实回写 `.ccc-result.md`：含独立核验结果、ffprobe/manifest 原文、测试输出、维护区四问（标准键名）、变更证据（commit/hash）。

## 验收标准

1. main 上 HyperFrames 真入口修复在位（动态超时/进程组清理/DataError 冒泡/帧数 fail-fast）。
2. 端到端成片 1080×1920、帧率 ≥24fps（当前配置 30fps），manifest 无 fallback 字样。
3. 渲染结束后无 npx/hyperframes/node 孤儿进程（ps 取证）。
4. `video-pipeline/tests/` 全部通过退出码 0。
5. 维护区四问以标准键名作答，教训引用 `docs/lessons.md` Lesson 163/164。
6. 无发布、无凭据泄露、无其他项目改动、无既有产物删除。
7. 不虚报：任何降级/缺失如实声明。

## 门禁

测试（视频组）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest video-pipeline/tests/ -q`

## 回写要求

结果写入 `.ccc-result.md`，含独立核验、ffprobe/manifest 原文、测试输出、维护区四问、commit/hash、进程取证。

## 人工批注

无

## 回写区

（待执行体回写）
