# 任务卡 xy010 · 画面加固：全链路视频高码率高质量CRF编码升级（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

全面升级 `video-pipeline/` 合成全链路中的 FFmpeg 视频编码参数，解决目前「画面码率仅 0.12 Mbps 糊满噪点、文件过小（0.8 MB 无法发布）」的质量问题，确保生成的 1080p 竖屏视频码率在 3.5 Mbps 以上，画质达到平台高清发布标准。

## 红线（先看）

1. 只动 xianyu 仓 `video-pipeline/`（主要是 `pipeline.py`、`stages/compose/generator.py`）内编码参数相关逻辑；不碰平台（CCC）与其他项目。
2. 不直推 main；代码走卡内分支 `codex/xy010-video-high-bitrate-crf-encoding`。
3. 必须在 CRF 范围 `[20, 22]` 内应用，禁止为了压文件大小将 CRF 改大到 25 以上导致画质劣化。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- `video-pipeline/pipeline.py` 与 `stages/compose/generator.py` 中拼接渲染视频的核心 FFmpeg 参数数组。
- 支持从 config.json 配置或环境变量覆盖编码参数（CRF, bitrate, preset）。

## 步骤

1. **阅读 baseline**：在 2017 阅读 `/video-pipeline/VIDEO_QUALITY_DEV_PLAN.md` 第一节中的 FFmpeg 升级指标（目标码率 ≥3.5 Mbps，文件大小 ≥9 MB）。
2. **重构视频渲染参数**：
   - 寻找 `pipeline.py` 和 `compose` 阶段最终执行 `-c:v libx264` 的 FFmpeg 参数段。
   - 将原极其廉价的 `-preset veryfast -crf 28 -tune stillimage` 替换为：
     ```bash
     -c:v libx264 -profile:v high -level 4.2 -preset slow -crf 21 \
     -tune film -x264-params "bitrate=3500:vbv-maxrate=4000:vbv-bufsize=8000" \
     -pix_fmt yuv420p -b:a 192k
     ```
   - 保证音频流以 `192k` AAC 高品质格式编码（`-c:a aac -b:a 192k`）。
3. **适配并兼容二遍编码（2-pass）**：
   - 确保如果是 VBR 模式，两遍编码的文件状态流转正常，无遗留统计临时文件。
4. **单测运行**：
   - 为编码器生成参数编写单元测试，验证各模式下产出的 FFmpeg 拼接命令完全合规且含有高质量预设。
5. **探针实测**：
   - 跑一次视频生成，使用 `ffprobe` 检测最终产出视频文件的码率（bitrate）、分辨率（1080x1920）和 Preset 配置，确认码率真机测试在 `3.5 Mbps` 到 `5 Mbps` 之间。
6. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. FFmpeg 升级后的编码配置正常合入，不引起视频合成非零中断（未崩溃）。
2. 实测生成的 1分钟 1080p 视频文件大小在 `10 MB` 到 `35 MB` 之间。
3. `ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 <输出视频>` 结果不低于 `3500000` (3.5 Mbps)（附探针检测日志）。
