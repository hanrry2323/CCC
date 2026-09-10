# 任务卡 xy068 · 生产视频链路接入 HyperFrames 30fps 真动效（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：已关闭 · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy068 · 状态版本：6
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

## 批注落实

**批注原文（逐条引用）**：

1. 【Q2 教训引用·外脑】上轮机审：维护区②声明[有]但未引用 lessons 文件。教训已由外脑落业务仓 `docs/lessons.md` **Lesson 167**（契约连带测试/amix 截帧/测试环境陷阱，即你②所述三条）。修复轮：②说明末尾补「证据：docs/lessons.md Lesson 167」。

**逐条落实说明**：

1. **已落实**。证据链：① Lesson 167 已在业务仓权威树落库——`/Users/fan/program/apps/xianyu/docs/lessons.md` 第 1671 行存在 `## Lesson 167：生产 video 链路接 HF 的三大真实坑——契约连带测试/amix 截帧/测试环境陷阱（xy068）`，其三条教训与本卡维护区②所述三条一一对应（提交 `72e9d8d`，origin/main）；② 本结果文件维护区②说明末尾已补「证据：docs/lessons.md Lesson 167」（见 ## 3 维护区四问第 2 项）。代码未重做：批注明示「代码（分支已交付）无需重做」，本轮无任何业务文件改动。

## 人工批注

1. 【Q2 教训引用·外脑】上轮机审：维护区②声明[有]但未引用 lessons 文件。教训已由外脑落业务仓 `docs/lessons.md` **Lesson 167**（契约连带测试/amix 截帧/测试环境陷阱，即你②所述三条）。修复轮：②说明末尾补「证据：docs/lessons.md Lesson 167」。

## 回写区

## 0. 卡标题复述

任务卡 xy068 · 生产视频链路接入 HyperFrames 30fps 真动效（开发线 Build）：生产视频链路（`xianyu run --pipeline video`）当前用 ffmpeg 图片拼接（引擎=cinematic/ffmpeg），未接入 xy064 已验收的 HyperFrames 30fps 真动效渲染。本卡要求：① 生产 video worker（`src/xianyu/content/video.py`）渲染路径接入 HyperFrames 30fps 真动效（复用 `video-pipeline/stages/scene/generator_hf.py` 的动态超时/进程组清理/帧完整性逻辑），ffmpeg 仅作最终合成，主路径产出 30fps 真动效成片，HyperFrames 不可用时降级 ffmpeg 并如实记录；② rewriter 标签 `engine="ollama"` 改 `"llm"`（实际走 3456 通道），测试同步；③ 成片落盘 `workspace/outputs/video/<batch>/final.mp4`（publish 前，publish 失败不阻止产物保留）+ ffprobe 取证；④ 测试真实通过。**本轮为修复轮**：机审不通过原因为「维护区②声明[有]但未引用 lessons 文件」，人工批注指示在维护区②说明末尾补「证据：docs/lessons.md Lesson 167」，代码（分支已交付）无需重做。

## 1. 探针输出

**修复轮性质**：代码已于上轮交付，HEAD = `e13a480` = origin/codex/xy068-video-hyperframes（`git status -sb` 无 ahead/behind，已推送）。本轮零业务改动，探针聚焦批注落实所需的证据链。

- **教训引用探针**：`grep -n "Lesson 167" /Users/fan/program/apps/xianyu/docs/lessons.md` → `1671:## Lesson 167：生产 video 链路接 HF 的三大真实坑——契约连带测试/amix 截帧/测试环境陷阱（xy068）`（exit=0）。注意：本工作树分支切自 `e6bf28c`（Lesson 166 之后），工作树内 `docs/lessons.md` 不含 Lesson 167，属预期——教训由外脑落权威仓 origin/main（`72e9d8d`），引用指向业务仓权威树文件。
- **代码探针**：`src/xianyu/content/rewriter.py:98` = `"engine": "llm"`；全文件 `grep -n ollama` 零命中（engine 标签已修正，无 ollama 残留）。`src/xianyu/content/video.py` 含 16 处 `fallback` 相关代码（HF 降级路径在位，与上轮交付一致）。
- **工作树状态**：`git status -sb` = `## codex/xy068-video-hyperframes...origin/codex/xy068-video-hyperframes`，仅未跟踪 `.venv`（wrapper 环境符号链接 → 权威仓 venv，非业务文件，不提交、不动）。
- **上轮真实 e2e 取证**（代码零改动故不重跑；上轮证据已记录于任务卡回写区，产物在 /tmp 已清理）：npx hyperframes@0.6.97 真渲染 576 帧（5 场景 90+120+120+120+90 + 过渡 4×9），ffprobe `r_frame_rate=30/1`、`nb_frames=576`、h264/yuv420p，manifest `grep -o fallback` 计数 0。

## 2. 自测输出

**门禁测试**（卡门禁命令原文，`.venv/bin/pytest tests/test_cinematic_video.py tests/content/test_rewriter.py -q`，退出码用 `echo $?` 直接捕获非管道尾）：

```
============================== 49 passed in 2.97s ==============================
[exit code: 0]
```

- 上轮基线 41 → 49（新增 8 例：HF 主路径/降级/30fps 输入断言/PIL 降级识别/有序帧重建/落盘取证/capabilities hyperframes、rewriter mock 兜底 engine），本轮零改动后仍 49 passed。
- rewriter 标签断言（tests/content/test_rewriter.py）：`test_execute_generates_4_platform_versions` 断言 `d["engine"] == "llm"`；`test_execute_llm_failure_falls_back_to_mock_engine` 断言降级 `engine == "mock"`。
- 上轮全量回归：12 failed 均为既有/环境失败（openclaw-plugin 无 node_modules、共享 venv editable install 指向陈旧 xy060 等，归因见卡内探针输出），无 xy068 新增失败；本轮零改动不重复归因。

## 维护区

1. **方案同步**：[是] 生产 video 链路已从「ffmpeg 图片拼接」切换为「HyperFrames 30fps 真动效主路径 + ffmpeg 最终合成」，复用 video-pipeline generator_hf（动态超时/进程组清理/帧完整性），与 xy064 验收方案一致；新增「音频 apad 补齐到场景时间轴」修正（mix_audio 用 amix=duration=first 取 TTS 时长，短于时间轴时 -shortest 会截帧，e2e 实证后修复）；关联方案 xy-plan-008 的 video 接入项由本卡落地。本轮修复轮无方案变更。
2. **教训沉淀**：[有] 教训：① process() 返回值契约变更（Path→RenderOutcome）与新增 HF 主路径会连带影响直接调用它的其他测试文件（test_bgm.py），改契约前应先 grep 全部调用方；② mix_audio 的 amix=duration=first 不按场景时间轴补齐，HF 帧序列合成若用 -shortest 会静默截帧（e2e ffprobe 发现 nb_frames 382<576），需 apad=whole_dur 显式补齐；③ 工作树测试环境两处陷阱：openclaw-plugin 无 node_modules（gitignore 目录）、共享 venv editable install 指向陈旧 xy060——全量回归前需先归因既有环境失败，避免误判新增。证据：docs/lessons.md Lesson 167。
3. **档案/README**：[否] 无档案/README 变更需求；video.py 模块 docstring 已同步 HF 主路径说明，不涉及对外文档。
4. **线路图**：[否] 无线路图变更；本卡为 xy-plan-008 既定项落地，不引入新路线项。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：通过
- 理由：CC 审核通过，自动合入完成
