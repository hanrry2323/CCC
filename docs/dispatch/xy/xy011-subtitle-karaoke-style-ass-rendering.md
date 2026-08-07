# 任务卡 xy011 · 字幕重构：引入双色卡拉OK高亮与高表现力ASS滤镜渲染（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

重构 `video-pipeline/stages/subtitle/` 的字幕生成和渲染机制，摒弃单行死白无样式的简陋文本层，引入基于标准 **ASS (Advanced SubStation Alpha)** 字幕模板的高级渲染，支持**卡拉OK式当前词高亮、字体自动检测、双色描边**，极大提升字幕视觉高级感。

## 红线（先看）

1. 只动 xianyu 仓 `video-pipeline/` 字幕生成与 FFmpeg 渲染相关代码；不碰平台（CCC）与其他项目。
2. 不直推 main；代码走卡内分支 `codex/xy011-subtitle-karaoke-style-ass-rendering`。
3. FONTFILE 路径必须支持运行时 auto-detect（在 macOS、Linux、Docker 下各有 fallback），禁止因写死某单一平台字体路径导致另一平台渲染崩溃。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- `stages/subtitle/generator.py`（字幕阶段）生成逻辑。
- 引入或完善基于 `edge-tts` WordBoundary 词时间戳到 ASS 卡拉OK标签（如 `{\kf50}` 等）的转换器。
- FFmpeg 最终合成命令中的 `ass` / `subtitles` 滤镜配置。

## 步骤

1. **实现 Word-level 时间戳导出**：
   - 在 TTS 生成（`stages/tts/`）或 Subtitle 生成阶段，完整保留每个中文词（Word）和精确毫秒时间戳的对应（利用 edge-tts 的 WordBoundary 接收事件或降级估算）。
2. **编写 ASS 字幕格式渲染器**：
   - 在 `stages/subtitle/generator.py` 中，不生成普通 `.srt`，而是生成带样式头部（`[V4+ Styles]`）的 `.ass` 文件。
   - 制定统一的高表现力字幕 Style（例如：`Fontname=os.environ.get("FONTFILE", "HarmonyOS Sans SC")`, `Fontsize=16`, `PrimaryColour=&H00FFFFFF`（主色白）, `SecondaryColour=&H0000FFFF`（当前词卡拉OK色黄/粉）, `OutlineColour=&H00000000`（描边黑）, `BorderStyle=1`, `Outline=2`）。
   - 解析词时间戳，为字幕行的词尾自动计算间隔，填充 `{\k50}`（卡拉OK进度）标记。
3. **升级 FFmpeg 字幕渲染滤镜**：
   - 修改 `compose` 模块中执行 FFmpeg 拼接的命令，用 `-vf "ass=subtitles.ass"`（或 `-vf "subtitles=subtitles.srt"` 带样式）代替纯背景拼字，确保字幕完美透射到视频层。
4. **单测覆盖**：
   - 编写针对 ASS 字幕生成、卡拉OK标签换算等逻辑的单元测试，保证生成格式 100% 正确无乱码。
5. **探针自测**：
   - 跑一遍带字幕的合成，确认视频字幕具有双色描边且在说话时有流畅的当前字/当前词逐字卡拉OK高亮变色动效。
6. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 字幕模块顺利生成标准 ASS 文本，且在不同平台下编译无字体路径丢失（未报错）。
2. 合成出的视频，字幕具有显著的**描边双色**和**卡拉OK当前词高亮/变色**动效，视觉体验大厂化。
3. 单元测试全过。

## 补充信息

- 遗留痛点：目前 B站等分发平台上的视频由于无描边、字体小而糊，被判为“劣质/垃圾”很大程度归咎于此。本卡是画风升维的胜负手。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：
