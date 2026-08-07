# 任务卡 xy016 · 视频出片链路全摸底与架构图 HTML 产出（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

全量摸清 xianyu 视频出片链路的现状（生成逻辑/链条/模块/输出目录/大模型调用方式），产出**一个自包含 HTML 架构图报告**，含文字结论与 Mermaid/图形化架构图，交付到 2017 桌面 `/Users/fan/Desktop/xianyu-video-pipeline-arch.html`（纯只读侦察，不改业务代码）。

## 红线（先看）

1. **只读摸底**：禁止修改 xianyu 仓任何业务代码/配置；只允许读文件、跑只读命令（`ls`/`cat`/`grep`/`find`/`git log`/`git diff` 只读参数、`plutil`/`launchctl list`）。
2. 禁止启动/重启任何生产服务或 launchd 守护；禁止执行会写文件的命令。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
4. HTML 文件只写到 `/Users/fan/Desktop/`，禁止写入 xianyu 仓目录；禁止在 CCC 仓新建业务文档。

## 范围

- 只读侦察：`/Users/fan/program/apps/xianyu`（重点是 `video-pipeline/` 与 `src/xianyu/video/`）
- 产出物：`/Users/fan/Desktop/xianyu-video-pipeline-arch.html`（唯一产出，不自包含外部资源，单文件可打开）

## 步骤

1. **摸清出片主链路**：读 `video-pipeline/` 的入口（`pipeline.py` / CLI 命令）与 `stages/` 各模块（compose / scene / script / subtitle / tts / bgm 等），画出从「选题 → 脚本 → 分镜/场景 → 字幕 → TTS 配音 → BGM 混音 → 画面合成 → 编码 → 成片」的完整链条与各阶段输入输出、配置文件（`config.json`）、调度方式（launchd？cron？手动命令？）。
2. **厘清双轨**：对比 `video-pipeline/`（生产）与 `src/xianyu/video/`（历史旁路）的调用关系——哪些入口在真实调用哪条链；`hyperframes/`、`remotion/` 是否被实际使用。
3. **摸清输出目录**：找出成片/中间产物的落盘路径（搜索 `output`/`output_dir`/`out_dir`/`保存`/`save` 等配置与代码），列出：最终视频文件放哪、命名规则、中间帧/音频/字幕产物放哪。
4. **摸清大模型调用**：这是老板最关心的点，必须逐项查清并在报告中明确回答：
   - 全链路是否调用 LLM？在哪几个环节调？（脚本生成/选题/字幕润色/标题等）
   - 调的是**本地大模型（llama / ollama / llama.cpp / vllm 等本地服务）**还是**在线大模型 API（OpenAI/Claude/DeepSeek/GLM/MiniMax 等）**？
   - 给出每个调用点的证据：代码文件+行号、请求 URL/base_url、模型名、API key 来源（`.env`/`config`）、超时与降级逻辑。
   - 若同时存在本地与在线，说明各自用途与切换条件。
5. **产出 HTML 报告**：单文件自包含 HTML（内联 CSS，架构图用 Mermaid.js CDN 或内联 SVG），内容必须包含：
   - 结论区：出片模式一句话总结 + 输出目录 + LLM 调用结论（本地/在线/混合）
   - 架构图：完整链路图（模块→模块，标注输入输出与产物路径）
   - 模块表：每模块职责/入口/产物/配置项
   - LLM 调用明细表：环节/类型(本地|在线)/模型名/证据(文件:行)/key 来源
   - 双轨说明：生产链 vs 旁路链 vs hyperframes/remotion 的现状
   - 疑问/未知项清单（摸不清的明确列出，不猜）
6. commit+push 到卡内分支（HTML 文件本身不入仓，只提交本卡的摸底要点与 HTML 落盘路径说明到回写区）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `/Users/fan/Desktop/xianyu-video-pipeline-arch.html` 存在且为单文件自包含 HTML（`ls -la` 可验证，浏览器可直接打开）。
2. HTML 内明确回答四问：①完整出片链路与模块 ②输出文件夹路径 ③是否有 LLM 调用 ④本地(llama 等)还是在线大模型，每问有证据（代码文件:行号 或 配置项）。
3. 报告含至少一张完整链路架构图与一张 LLM 调用明细表。
4. xianyu 仓 `git status` 干净（零业务代码改动，可 `git status --short` 验证）。
5. 回写区填：摸底结论摘要 + HTML 文件路径 + 未解疑问清单。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
