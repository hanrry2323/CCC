# 任务卡 xy068 · 生产视频链路接入 HyperFrames 30fps 真动效（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：打回（CC 审核不通过） · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy068 · 状态版本：3
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

## 0. 卡标题复述

任务卡 xy068 · 生产视频链路接入 HyperFrames 30fps 真动效（开发线 Build）：生产视频链路（`xianyu run --pipeline video`）当前用 ffmpeg 图片拼接（引擎=cinematic/ffmpeg），未接入 xy064 已验收的 HyperFrames 30fps 真动效渲染。本卡要求：① 生产 video worker（`src/xianyu/content/video.py`）渲染路径接入 HyperFrames 30fps 真动效（复用 `video-pipeline/stages/scene/generator_hf.py` 的动态超时/进程组清理/帧完整性逻辑），ffmpeg 仅作最终合成，主路径产出 30fps 真动效成片，HyperFrames 不可用时降级 ffmpeg 并如实记录；② rewriter 标签 `engine="ollama"` 改 `"llm"`（实际走 3456 通道），测试同步；③ 成片落盘 `workspace/outputs/video/<batch>/final.mp4`（publish 前，publish 失败不阻止产物保留）+ ffprobe 取证；④ 测试真实通过。人工批注为「无」占位。

## 1. 探针输出

**基线**：分支 `codex/xy068-video-hyperframes` 基于 `5fc1b1e`（=main）。改动前门禁基线：`pytest tests/test_cinematic_video.py tests/content/test_rewriter.py -q` → **41 passed**。

**环境探针**：
- `npx hyperframes@0.6.97 --version` → `0.6.97`（HyperFrames CLI 可用）
- `video-pipeline/stages/scene/generator_hf.py` 复用探针：在 xianyu venv 中 `sys.path` 加入 `video-pipeline/` 后 `from stages.scene import generator_hf` 导入成功（其内部 `sys.path.insert(HERE.parent.parent)` 与生产加载逻辑一致）；`contracts.SceneInput/SceneSpec` 可用
- 全量回归环境归因（与 xy068 改动无关的既有失败，均在权威仓 main=5fc1b1e 实测复现或工作树环境差异）：
  - `tests/admin/test_preview.py` 8 failed —— 权威仓 main 同路径复现（8 failed，同集合）
  - `tests/openclaw/test_plugin_integration.py::test_xianyu_run_help_via_module` / `test_xianyu_run_module_invocation_path` —— 权威仓 main 同路径复现（2 failed）；根因：共享 venv 的 editable install 指向陈旧 xy060 工作树 src（`_editable_impl_xianyu.pth`），`python -m xianyu` 解析异常
  - `test_plugin_syntax_loads` / `test_plugin_declares_xianyu_run_tool` —— 工作树 `openclaw-plugin/` 无 `node_modules`（gitignore 目录，worktree 不携带）→ node `ERR_MODULE_NOT_FOUND: typebox`；权威仓有 node_modules 故通过

**真实端到端探针（HyperFrames 真入口）**：`worker.process()` 真渲染（npx hyperframes@0.6.97，fps=30，5 场景，workers=4）：
```
[video] HyperFrames 渲染启动: 5 场景 1080x1920 @30fps style_seed='minimal'
[generator_hf] Running HyperFrames CLI render: npx hyperframes@0.6.97 render --format=png-sequence --fps=30 -o ... (frames=576, timeout=2982s, workers=4)
[generator_hf] Successfully captured 576 frames (expected=576). Mapping to standard pipeline schema...
[video] HyperFrames 渲染成功: /private/tmp/xianyu_video/hf_frames_c73e427a (576 帧)
[video] ffmpeg 最终合成: 576 帧 @30fps → /tmp/xy068_e2e/out/final.mp4
E2E_ENGINE: hyperframes
E2E_FALLBACK_REASON: (none)
E2E_MANIFEST: /private/tmp/xianyu_video/hf_frames_c73e427a/scene_manifest.json
```
- manifest 无 fallback 字样：`grep -o "fallback" scene_manifest.json | wc -l` = **0**
- 帧数核验：manifest 5 场景（90+120+120+120+90=540）+ 过渡 4×9=36 = **576**，`ls hf_frames_c73e427a/*.png | wc -l` = 576，与 ffprobe nb_frames=576 一致

## 2. 自测输出

**门禁测试**（卡门禁命令原文，`.venv/bin/pytest tests/test_cinematic_video.py tests/content/test_rewriter.py -q`）：
```
============================== 49 passed in 4.08s ==============================
[exit code: 0]
```
（基线 41 → 49：新增 8 例——HF 主路径/降级/30fps 输入断言/PIL 降级识别/有序帧重建/落盘取证/capabilities hyperframes、rewriter mock 兜底 engine）

**改动涉及的全部测试文件**（`.venv/bin/pytest tests/test_cinematic_video.py tests/content/test_rewriter.py tests/video/test_bgm.py -q`）：
```
============================== 89 passed in 2.26s ==============================
[exit code: 0]
```

**rewriter 标签断言**（tests/content/test_rewriter.py）：
- `test_execute_generates_4_platform_versions`：`assert d["engine"] == "llm"` ✓（3456 通道标签，非 ollama）
- `test_execute_llm_failure_falls_back_to_mock_engine`：LLM 抛异常 → `engine == "mock"` ✓

**全量回归**（`pytest tests/ -q`）：**12 failed, 791 passed, 8 skipped** —— 12 个失败全部为既有/环境失败（见探针输出归因表），与 xy068 改动无关；**无新增失败**。关键验证：改动前权威仓 main 全量 = 13 failed（含本工作树不出现的 test_llm/test_daily_image_source 环境失败），两套失败集合均为环境噪声，不含任何 xy068 触发的失败。

**真实成片 ffprobe 原始取证**（`ffprobe -v error -show_streams -show_format workspace/outputs/video/xy068-e2e/final.mp4` 关键行原文）：
```
[STREAM index=0] codec_name=h264  profile=High  codec_type=video
width=1080  height=1920  pix_fmt=yuv420p  field_order=progressive
r_frame_rate=30/1  avg_frame_rate=30/1  duration=19.200000  nb_frames=576
[STREAM index=1] codec_name=aac  sample_rate=96000  channels=1  duration=19.200000
[FORMAT] format_name=mov,mp4  duration=19.200000  size=293644  probe_score=100
```

**成片落盘路径**：`/Users/fan/program/apps/.ccc-wt/xy/xy068/workspace/outputs/video/xy068-e2e/final.mp4`（293,644 B，30fps 真动效成片）

**降级路径证据（单元测试，mock hyperframes）**：
- `test_ffmpeg_fallback_to_progressive`：`_render_hyperframes` 抛 `RuntimeError("npx hyperframes is not available")` → FFmpeg 单命令失败 → 渐进模式成功 → `engine="ffmpeg"` 且 `fallback_reason` 含原因 ✓
- `test_try_hyperframes_compose_records_reason_on_failure`：降级原因串如实返回，frames_dir=None ✓
- `test_render_hyperframes_detects_pil_fallback`：generator_hf 内部降级 PIL 时 stderr 标记被捕获 → 抛 `RuntimeError("HyperFrames 不可用（generator_hf 内部降级 PIL）: ...")`，不把 PIL 帧冒充 HyperFrames ✓
- `test_total_ffmpeg_failure_returns_mock`：HF+FFmpeg 全失败 → mock ✓

**真实降级路径说明（不虚报）**：本机 npx hyperframes@0.6.97 可用，e2e 全程真 HyperFrames 入口（engine=hyperframes，fallback_reason=none）；降级到 ffmpeg 的代码路径由上述单元测试覆盖并如实记录原因；若生产环境 HyperFrames CLI 不可用，`get_capabilities()["hyperframes"]` 返回 False 且 execute 结果带 `fallback_reason`。

## 维护区

1. **方案同步**：[是] 生产 video 链路已从「ffmpeg 图片拼接」切换为「HyperFrames 30fps 真动效主路径 + ffmpeg 最终合成」，复用 video-pipeline generator_hf（动态超时/进程组清理/帧完整性），与 xy064 验收方案一致；新增「音频 apad 补齐到场景时间轴」修正（mix_audio 用 amix=duration=first 取 TTS 时长，短于时间轴时 -shortest 会截帧，e2e 实证后修复）；关联方案 xy-plan-008 的 video 接入项由本卡落地。
2. **教训沉淀**：[有] 教训：① process() 返回值契约变更（Path→RenderOutcome）与新增 HF 主路径会连带影响直接调用它的其他测试文件（test_bgm.py），改契约前应先 grep 全部调用方；② mix_audio 的 amix=duration=first 不按场景时间轴补齐，HF 帧序列合成若用 -shortest 会静默截帧（e2e ffprobe 发现 nb_frames 382<576），需 apad=whole_dur 显式补齐；③ 工作树测试环境两处陷阱：openclaw-plugin 无 node_modules（gitignore 目录）、共享 venv editable install 指向陈旧 xy060——全量回归前需先归因既有环境失败，避免误判新增。
3. **档案/README**：[否] 无档案/README 变更需求；video.py 模块 docstring 已同步 HF 主路径说明，不涉及对外文档。
4. **线路图**：[否] 无线路图变更；本卡为 xy-plan-008 既定项落地，不引入新路线项。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：Q2 声明了有教训沉淀[有]，但说明中未引用任何 docs/notes/*.md 或 lessons.md 文件
