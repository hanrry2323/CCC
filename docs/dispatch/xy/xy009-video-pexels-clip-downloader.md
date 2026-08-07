# 任务卡 xy009 · 内容生产：接入Pexels/Pixabay API检索下载短视频素材（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

在 `video-pipeline/` 中，实现根据脚本段落关键词，调用 Pexels / Pixabay 免费 API 自动检索并下载垂直相关的 1080p 竖屏**短视频素材（Video Clips）**，在 `compose` 合成阶段代替简单的 PPT 静态图片，大幅提升视频画面的动感和相关度。

## 红线（先看）

1. 只动 xianyu 仓 `video-pipeline/` 内的代码；不碰平台（CCC）与其他项目。
2. 不直推 main；代码走卡内分支 `codex/xy009-video-pexels-clip-downloader`。
3. 必须在 config.json 中提供可选的 `PEXELS_API_KEY`。在无 key 或网络请求超时、无法匹配时，必须**优雅降级**到既有的图片 + Ken Burns 模式，禁止直接崩溃。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- `stages/scene/generator.py`（画面生成阶段）或新建 `utils/pexels.py` 素材检索下载。
- 对脚本每句话进行 LLM 英文关键词提取（如 `extract_keywords_for_scene`），用于检索相关视频。
- `compose` 模块兼容对 MP4 短视频素材和 JPG 静态图片的混合拼接。

## 步骤

1. **写一个关键词提炼器**：在 `stages/scene/generator.py` 中，使用 LLM 将每句话（或每段场景）翻译并提取为 1-2 个具体的英文视觉关键词（例如：“介绍二手相机的坑” → `used camera, photography`）。
2. **开发 API 检索接口**：
   - 编写 `utils/pexels.py`，调用 Pexels Video Search API（`https://api.pexels.com/videos/search`），参数指定 `orientation=portrait`（竖屏优先）及 `size=medium`（1080p）。
   - 下载命中的前 3 个相关视频片段中短小、清晰的片段（5-10 秒），保存至临时缓存，按时间轴做变速或截断以匹配该句 TTS 的长度。
3. **重构合成器以兼容视频**：
   - 修改 `stages/compose/generator.py`，使 FFmpeg 或 Moviepy 合成流程不仅能接收 `.jpg`，还能接收 `.mp4` 素材作为背景。
   - 实现视频素材的无缝淡入淡出（Crossfade）拼接。
4. **单测覆盖**：
   - 编写 mock 测试，确保在没有真实网络时，Pexels 接口返回空并完美降级为图片路径。
5. **探针实测**：
   - 跑一次带 API Key 的生成，验证生成的视频背景中包含真实的 Pexels 竖屏视频（例如：输入“如何用 Python 炒股”，最终生成的视频背景里出现了真实的程序员敲代码或股票 K 线图动画）。
6. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 视频合成器能同时混合静态图片和 Pexels 下载的 MP4 背景片段，转场无缝通畅。
2. 当 API Key 不可用或网络超时，能优雅降级回原图，无任何报错（附降级测试日志）。
3. 实测视频中 70% 以上的场景背景是与台词高度相关的动态视频素材（附生成路径及 Pexels 缓存日志）。
