# 任务卡 xy005 · 音频处理：重构BGM自动混音与音量标准化（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

重构 BGM 自动混音与全局音频电平音量标准化（level normalization），解决 Lessons 2-3 中 `audio-bgm-auto-mix` 和 `audio-level-norm` 全量失败异常，确保输出的视频音量大小均匀、无削波（clipping）爆音。

## 红线（先看）

1. 只动 xianyu 仓 `video-pipeline/` 与音频混合相关代码；不碰平台（CCC）与其他项目。
2. 不直推 main；代码走卡内分支 `codex/xy005-fix-audio-bgm-and-level-norm`。
3. 全局音量归一化必须采用 EBU R128（或 LUFS）限制标准（如归一化到 -14 LUFS 或 -16 LUFS），禁止粗暴的最大音量拉伸导致动态失真。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- xianyu 仓内音频标准化模块、混音处理模块。
- 引入或调用成熟音量归一化工具（如调用 `ffmpeg-normalize` 库、ffmpeg 的 `loudnorm` filter，或使用 pydub 的 `normalize`）。
- BGM 的自动循环、剪裁与分段淡入淡出混入代码。

## 步骤

1. **排查现状**：读 xianyu 仓中 `audio-bgm-auto-mix` 与 `audio-level-norm` 的原实现与失败日志（Lessons.md），定位是因缺少第三方库依赖，还是 FFmpeg filter 参数构建错误导致的。
2. **重构自动混音**：
   - 当背景音乐比视频短时，BGM 必须实现自动无缝循环拼接，且在拼接点进行交叉淡入淡出（Crossfade），防断裂音。
   - 当背景音乐比视频长时，自动截断并在视频结尾进行平滑淡出。
3. **实现音量标准化**：
   - 引入 R128/LUFS 标准音量归一化：建议使用 `pydub.effects.normalize` 或 FFmpeg filter `loudnorm=I=-14:LRA=11:TP=-1.5` 进行整体音频处理。
   - 确保归一化在 BGM 混入后、或在合成最终音轨时执行，防人声被 BGM 压制。
4. **单测覆盖**：在 `tests/` 新建/重构混音与标准化单测，100% 跑通。
5. **探针实测**：生成一段 1 分钟音视频，核验音量电平是否均匀（无忽大忽小、无爆音）。
6. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. BGM 自动混音在长短背景音乐下均能无缝自适应，无突兀音量断裂。
2. 全局音频实现音量标准化（-14 或 -16 LUFS 左右），峰值限制在 -1.5 dBTP 以下防止削波（附实测电平日志）。
3. 音频混音与标准化单测通过率 100%。

## 补充信息

- 遗留失败记录：Lessons 2-3 中 `audio-bgm-auto-mix` 与 `audio-level-norm` 进入异常状态，导致平台无法合成符合电平规范的视频。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：
