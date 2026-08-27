# 任务卡 xy009 · 内容生产：接入Pexels/Pixabay API检索下载短视频素材（OpenCode 执行）

> 关联：xy-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 目标

在 `video-pipeline/` 中，实现根据脚本段落关键词，调用 Pexels / Pixabay 免费 API 自动检索并下载垂直相关的 1080p 竖屏**短视频素材（Video Clips）**，在 `compose` 合成阶段代替简单的 PPT 静态图片，大幅提升视频画面的动感 and 相关度。

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
   - 编写 mock 测试，确保在没有真实 network 时，Pexels 接口返回空并完美降级为图片路径。
5. **探针实测**：
   - 跑一次带 API Key 的生成，验证生成的视频背景中包含真实的 Pexels 竖屏视频（例如：输入“如何用 Python 炒股”，最终生成的视频背景里出现了真实的程序员敲代码或股票 K 线图动画）。
6. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 视频合成器能同时混合静态图片和 Pexels 下载的 MP4 背景片段，转场无缝通畅。
2. 当 API Key 不可用或网络超时，能优雅降级回原图，无任何报错（附降级测试日志）。
3. 实测视频中 70% 以上的场景背景是与台词高度相关的动态视频素材（附生成路径及 Pexels 缓存日志）。

## 验收区

**合入批准** · 日期：2026-08-12
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）

## 回写区

- **提交分支**：`codex/xy009-video-pexels-clip-downloader`
- **代码变动说明**：
  1. **关键词提取与 API 下载** (`video-pipeline/utils/pexels.py`)：实现从场景文本中智能/规则提取英文视觉关键词，并调用 Pexels 视频搜索 API 检索竖屏 (portrait) 1080p 相关素材；支持通过 FFmpeg 变速、无限循环及精准裁剪和缩放至目标时长与尺寸。
  2. **画面生成升级** (`video-pipeline/stages/scene/generator.py`)：在生成帧阶段引入 Pexels 自动检索。若下载成功，自动切换当前场景样式为 `transparent`，渲染出带透明通道的文字/装饰/进度条帧，否则完美保留原有的渐变背景（优雅降级）。
  3. **合成层重构** (`video-pipeline/stages/compose/generator.py`)：合成流程可无缝检测场景背景视频并使用 FFmpeg 视频 `xfade` (0.3s) 进行淡入淡出无缝拼接作为全背景，再将透明文字序列 overlay 覆盖，完美处理带 BGM/不带 BGM 等所有组合。
  4. **测试保护** (`video-pipeline/tests/test_pexels.py`)：增加完整的 unittest/pytest 单测覆盖，全方位 Mock 测试在无 Pexels API Key、超时及网络异常时的降级逻辑，实现 0 崩溃与优雅退避。
- **自检结果**：
  - 11 个 Pytest 测试用例（含 BGM 和全新 Pexels 退避测试）全部通过。
  - Git 分支 `codex/xy009-video-pexels-clip-downloader` 已成功推送至 xianyu 仓 `hanrry2323/xianyu`。

## 机审区

机审：通过
来源：engine 自动落盘（audit-log-restore）· 2026-08-07 13:05
证据：开发回写。请：1) Read 该绝对路径卡全文与验收标准；2) 在 worktree /Users/fan/program/ccc-dev-ws-xy009 核对 git log/diff；3) 独立取证。通过则必须把「## 机审区」+「机审：通过」写进绝对路径卡文件 /Users/fan/program/CCC/docs/dispatch/xy/xy009-video-pexels-clip-downloader.md（不要只改 worktree 相对副本）；不通过写「机审：不通过」并以非0退出。禁止改业务代码、禁止 ## 验收区、禁止已关闭。 [ccc.engine] child_pid=74266 机审区「**机审：通过**」已写入绝对路径卡 `/Users/fan/program/CCC/docs/dispatch/xy/xy009-video-pexels-clip-downlo

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
