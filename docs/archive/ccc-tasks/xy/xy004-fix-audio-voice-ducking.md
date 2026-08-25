# 任务卡 xy004 · 音频处理：修复语音闪避(ducking)功能异常（OpenCode 执行）

> 关联：xy-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 目标

修复视频合成中的音频语音闪避（voice-ducking）功能：实现当人声（TTS）说话时背景音乐（BGM）自动压低、人声结束时背景音乐恢复平滑过渡，消除 Lessons.md 中 `audio-voice-duck` 连续失败异常。

## 红线（先看）

1. 只动 xianyu 仓 `video-pipeline/` 与音频处理相关代码；不碰平台（CCC）与其他项目。
2. 不直推 main；代码走卡内分支 `codex/xy004-fix-audio-voice-ducking`。
3. 必须是真实的音频电平压低（使用 pydub 或 ffmpeg-filter 闪避），不得用简单的拼接或无闪避混音敷衍。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- xianyu 仓内负责音频处理、TTS 与 BGM 混音部分的代码（如 `src/xianyu/content/audio_ducking.py` 或 video-pipeline 中相应音频模块）。
- 语音闪避算法参数支持配置（人声检测阈值、背景音压低 db 数、淡入/淡出过渡时长）。
- 对应的单元测试与集成测试（tests/ 下音频/混音用例）。

## 步骤

1. **还原现状**：在 2017 查看 `docs/lessons.md` 中 `audio-voice-duck` 挂账异常；读音频处理模块源码，定位为何连续失败（通常是 ffmpeg 进程管道异常或 pydub 内存溢出）。在回写区说明。
2. **重构/修复音频闪避算法**：
   - 提取人声 TTS 的音轨音量和时间区间（或利用 VAD 算法/简单时间切片）。
   - 在有人声说话的区间，将 BGM 的 Gain 压低（如 12-15dB），并在切入/切出点施加 100ms-300ms 的淡入淡出，消除突兀爆音。
   - 保证输出音频与视频总长完美对齐，无长度截断。
3. **补齐测试**：在 `tests/` 下为音频闪避重写单测，覆盖：纯背景音、人声+背景音混音、极短音频、多段间歇人声等边界，且 100% 通过。
4. **探针实测**：跑一遍带 TTS 的视频生成脚本，确认产出的音轨在人声处有明显的背景音压低现象。
5. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 音频语音闪避功能 100% 修复，视频生成过程中无异常中断或非零退出。
2. 实测生成的音轨，在人声说话时 BGM 音量平滑压低，人声停顿处 BGM 平滑恢复，无突兀爆音与切断（附实测波形分析或音频试听日志）。
3. 音频闪避相关单测（`pytest tests/` 相应模块）全过。

## 补充信息

- 遗留失败记录：Lessons 1 记录 `audio-voice-duck` 重试 3 次全部失败，属于阻断性异常。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 验收区

**合入批准** · 日期：2026-08-12
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 1. 还原现状与根因分析
- **异常原因**：通过深度排查，发现不仅由于参数在管线上层未完全公开导致失败，还存在以下三项影响集成运行与闪避效果的实质性 Bug：
  1. **FFmpeg 语法错误**：`dynaudnorm` 滤镜中存在 `[s=0.001]` 格式错误，被 FFmpeg 误识别为多余的输出 Label 从而报错 `More output link labels specified for filter 'dynaudnorm' than it has outputs: 2 > 1`。
  2. **Sidechain 顺序反向**：在 `mix_audio` 中，`sidechaincompress` 输入流顺序错误（写成了 `[tts_norm][bgm_proc]`），导致 TTS 被当作主输入，而 BGM 被误作为侧链，使得 TTS 说话结束后的 BGM 区间全部静音。
  3. **音频总长端点截断**：由于 `sidechaincompress` 在侧链控制流（TTS）到达 EOF 时会自动提前终止处理，导致整段混音输出强制被截断到 TTS 长度。
  
### 2. 重构与修复方案
- **参数与管线修复**：在 `mix_audio` 和 `build_bgm_filter_chain` 中完全支持并向主管线透传配置 `ducking_threshold` (默认 0.02)、`ducking_attack` (默认 50.0) 和 `ducking_release` (默认 400.0) 参数。
- **修复语法与输入顺序**：修正 `dynaudnorm` typo 为 `dynaudnorm=p=0.95:s=0.001`；修正 sidechain compress 的输入顺序为 `[bgm_proc][tts_norm]`，恢复正确的 BGM 控制流机制。
- **引入 APAD 补齐**：在 `tts_norm` 上应用 `apad=whole_dur={duration}` 补齐静音并配合 `amix=duration=longest`，彻底消除了侧链提前 EOF 导致的视频尾部断音/截断问题。

### 3. 测试结果与探针实测
- **单元测试**：在 `tests/video/test_bgm.py` 中运行 44 个单测 100% 通过（跑测命令：`.venv/bin/pytest tests/video/test_bgm.py --no-cov`）。
- **Ruff Lint**：`ruff check src/xianyu` 100% 通过。
- **探针实测日志（带 TTS+BGM，15s 总长）**：
  在 `apps/xianyu` 运行 `python3 probe_mix.py && python3 analyze_ducking.py` 得到以下实时波形分析：
  ```
  Analyzing WAV: /Users/fan/program/apps/xianyu/data/mixed_output.wav
  Channels: 1, Sample Width: 2, Framerate: 44100, Frames: 661500 (Exactly 15.000s)

  === Waveform Level Analysis (RMS dB over time) ===
  Time: 00s - 01s | -26.98 dB | ██████████████████████████████████ (TTS active, BGM ducked smoothly)
  Time: 01s - 02s | -26.76 dB | ██████████████████████████████████
  Time: 02s - 03s | -26.76 dB | ██████████████████████████████████
  Time: 03s - 04s | -26.76 dB | ██████████████████████████████████
  Time: 04s - 05s | -26.76 dB | ██████████████████████████████████
  Time: 05s - 06s | -36.72 dB | ███████████████████              (TTS ends, BGM release phase)
  Time: 06s - 07s | -33.70 dB | ████████████████████████
  Time: 07s - 08s | -31.98 dB | ███████████████████████████        (BGM recovered smoothly)
  Time: 08s - 09s | -31.98 dB | ███████████████████████████
  Time: 09s - 10s | -31.98 dB | ███████████████████████████
  Time: 10s - 11s | -31.98 dB | ███████████████████████████
  Time: 11s - 12s | -31.98 dB | ███████████████████████████
  Time: 12s - 13s | -33.50 dB | ████████████████████████          (BGM starts fading out)
  Time: 13s - 14s | -37.84 dB | ██████████████████
  Time: 14s - 15s | -46.29 dB | █████                              (BGM faded out completely)
  ```

### 4. Push 证据
- **Commit Hash**：`c5710d5011268a6b2c8117ba843f2f8b4bb87fb6`
- **推送分支**：`codex/xy004-fix-audio-voice-ducking`

## 机审区

（2017 机审席，2026-08-07 复审）

**机审：通过**

独立取证摘要（worktree `ccc-dev-ws-xy004` / xianyu 仓 `apps/xianyu`，分支 `codex/xy004-fix-audio-voice-ducking`）：

1. **Push 证据 SHA 一致**：回写区 `c5710d5011268a6b2c8117ba843f2f8b4bb87fb6` == 本地 HEAD == `origin/codex/xy004-fix-audio-voice-ducking`（已推远端）；上轮「SHA 不符」整改闭环。
2. **代码为真且修复三处实质 Bug**：`src/xianyu/video/bgm.py`——① `dynaudnorm=s=0.001`（原错 `[s=0.001]` typo）修复；② `sidechaincompress` 输入顺序改 `[bgm_proc][tts_norm]`（原 `[tts_norm][bgm_proc]` 致 TTS 结束区间全静音）；③ BGM 侧链经 `apad=whole_dur={duration}` 补齐 + `amix=duration=longest` 消除侧链提前 EOF 截断；另加 `get_audio_duration`/ffprobe 时长探测、短 BGM `acrossfade` 循环、threshold/attack/release 三参可配。三参经 `content/video.py` 由 `ctx` 贯通主/降级管线；`get_audio_duration` 已导出。
3. **返工边界干净**：diff 仅触及 `src/xianyu/video/bgm.py`、`src/xianyu/content/video.py`、`src/xianyu/video/__init__.py`、`tests/video/test_bgm.py`，全部为音频/视频管线范围内；未碰平台，未直推 main。
4. **单测独立复跑全过**：`.venv/bin/pytest tests/video/test_bgm.py --no-cov` → **44 passed**（与回写区一致），覆盖自定义 ducking 参数、极短音频、循环跨淡等边界。
5. **探针实测佐证补齐**（上轮「缺实测」整改闭环）：`probe_mix.py`/`analyze_ducking.py` 为真实实测脚本，直接调用 `mix_audio(duration=15.0, ducking=True, …)` 产 `data/mixed_output.wav`；`analyze_ducking.py` 按 16-bit/44.1k/1s RMS 窗口输出 dB；回写区波形 44100×15.0 = 661500 frames（恰 15.000s）算术自洽，TTS 段 BGM 压低约 -26.8dB、释放恢复约 -32dB、尾段淡出，逻辑符合闪避预期。

结论：核心实现为真为可用，push 证据与探针实测两处机器可验证入口均已满足本卡验收标准。机审通过。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
