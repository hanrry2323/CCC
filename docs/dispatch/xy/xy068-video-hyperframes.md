# 任务卡 xy068 · 生产视频链路接入 HyperFrames 30fps 真动效（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy068 · 状态版本：1
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

生产视频链路（`xianyu run --pipeline video`）当前用 ffmpeg 图片拼接（引擎=cinematic/ffmpeg），未接入 xy064 已验收的 HyperFrames 30fps 真动效渲染。本卡：

1. **生产 video worker 接入 HyperFrames**：`src/xianyu/content/video.py` 的渲染路径接入 HyperFrames 30fps 真动效（复用 `video-pipeline/stages/scene/generator_hf.py` 的动态超时/进程组清理/帧完整性逻辑），ffmpeg 仅作最终合成。主路径产出 30fps 真动效成片；HyperFrames 不可用时降级 ffmpeg 并如实记录。
2. **rewriter 标签修正**：`src/xianyu/content/rewriter.py` 的 `engine="ollama"` 改为 `engine="llm"`（实际已走 3456 通道，标签误导）；对应测试同步。
3. **成片落盘**：video pipeline 在 publish 前将最终 `final.mp4` 落盘到 `workspace/outputs/video/<batch>/`（publish 失败不阻止产物保留），ffprobe 取证（分辨率/帧率/时长/编码）。
4. **测试**：video worker 渲染路径单测（mock hyperframes/ffmpeg）、rewriter 标签断言；全部真实通过。

## 实现要求

1. 改动限于 `src/xianyu/content/video.py`、`src/xianyu/content/rewriter.py`、对应 `tests/`。
2. HyperFrames 接入优先复用现有 `video-pipeline/stages/scene/generator_hf.py`，不重造轮子；降级路径如实记录。
3. rewriter 标签 `engine` 从 `"ollama"` 改 `"llm"`，日志/返回/测试同步。
4. 成片落盘为独立产物步骤，与 publish 解耦（publish 失败仍保留成片）。

## 红线

1. 只改 xianyu 业务仓；不发布、不触碰 Cookie/外部账号、不启动 M7。
2. 不得伪造视频/降级证据；HyperFrames 不可用必须如实记录。
3. 不得删除既有产物/数据库；所有改动业务分支 commit；测试真实通过。
4. 不读取或输出凭据值。

## 范围

- `/Users/fan/program/apps/xianyu/src/xianyu/content/video.py`
- `/Users/fan/program/apps/xianyu/src/xianyu/content/rewriter.py`
- `/Users/fan/program/apps/xianyu/tests/test_cinematic_video.py`
- `/Users/fan/program/apps/xianyu/video-pipeline/stages/scene/generator_hf.py`

## 步骤

1. 读 video.py/rewriter.py 现状与 `video-pipeline/stages/scene/generator_hf.py` 接口；跑相关测试确认基线。
2. video worker 接入 HyperFrames 30fps（主路径），ffmpeg 降级兜底；补测试。
3. rewriter 标签 `ollama→llm` 修正；补测试。
4. 成片落盘步骤（publish 前）；ffprobe 取证。
5. 全量相关测试真实通过；业务分支 commit；`.ccc-result.md` 如实记录（含 HyperFrames/ffmpeg 实际路径证据）。

## 验收标准

1. video worker 主路径产出 30fps 真动效成片（ffprobe r_frame_rate=30/1），manifest 无 fallback 字样；降级时如实记录原因。
2. rewriter 返回/日志 `engine=llm`（非 ollama），测试断言通过。
3. `final.mp4` 落盘 `workspace/outputs/video/<batch>/`，ffprobe 取证（分辨率/帧率/时长/编码）。
4. 相关测试全部通过退出码 0；全量回归无新增失败。
5. 业务分支 commit 存在；工作树除结果文件外干净。
6. 不虚报：HyperFrames/ffmpeg 实际路径如实记录。

## 门禁

测试（content+video）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest tests/test_cinematic_video.py tests/content/test_rewriter.py -q`

## 回写要求

结果写入 `.ccc-result.md`，含：HyperFrames 接入 diff、降级路径证据、ffprobe 原始输出、rewriter 标签断言、成片落盘路径、维护区四问（标准键名）、变更证据。

## 人工批注

无

## 回写区

（待执行体回写）
