# 任务卡 xy001 · 一键生成短视频脚本命令与产出流程（OpenCode 执行）

> 关联：xy-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 目标

给 xianyu 加一个「一键写视频脚本」小命令：输入一个主题，生成一份短视频脚本（含标题 + 分镜正文），存到统一产出文件夹，并留产出记录。

## 红线（先看）

1. 只动 2017 `/Users/fan/program/apps/xianyu` 仓；不碰平台（CCC server/engine/board）与其他项目。
2. 不直推 main；代码走卡内分支 `codex/xy001-write-video-script-command`。
3. 不得用 `released` 冒充意图完成：必须探针真跑通（见验收标准）。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- xianyu 仓内新增「一键写脚本」命令入口（CLI 或脚本，按仓内既有技术栈）。
- 统一产出文件夹（若仓内已有产出目录，则沿用；没有则新建并说明命名）。
- 产出记录（每产出一条脚本，落一条可追溯记录：时间 / 主题 / 文件名 / 结果）。

## 步骤

1. **先侦察现状（不得跳过）**：读 xianyu 仓结构，回答——
   - 现在文件生产流程是怎么样的？已有产出文件夹 / 产出记录机制吗？
   - 技术栈是什么（语言 / 命令入口 / 测试方式）？
   - 把侦察结论写进回写区「现状分析」。
2. **补齐短板**：如果现状缺统一产出文件夹或产出记录，就补上；有就用已有的，不重复造。
3. 实现「一键写视频脚本」命令：输入主题 → 生成脚本文件（标题 + 分镜正文）→ 写产出记录。
4. 探针真跑：`输入主题「卖二手相机」→ 命令 → 产出文件夹出现脚本文件`。
5. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「验收看板」终验。

## 验收标准

1. 敲一条命令、输入主题「卖二手相机」，能生成一份脚本文件，里面看得见标题 + 分镜正文（附实测命令与产物路径）。
2. 脚本文件落在统一产出文件夹，路径可复现（同一命令第二次跑也走同一文件夹）。
3. 产出记录存在且可追溯：本次生成的脚本在记录里有一条（时间 / 主题 / 文件名）。
4. 现状分析写清楚：xianyu 原本怎么产出文件，本卡补了什么 / 沿用了什么。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人工终验听「验收看板」后写 `## 验收区`+已关闭。

## 验收区

**合入批准** · 日期：2026-08-12
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 现状分析

xianyu 仓（`/Users/fan/program/apps/xianyu`）侦察结论：

- **文件生产流程**：CLI `xianyu run`（typer）端到端跑「话题 → 内容生成 → 路由 → 多平台发布」；内容生产在 `src/xianyu/content/`（writer/rewriter/tts/image/video），调本地 Ollama（`core/llm.chat_json`，qwen2.5:7b），失败回 mock 骨架。
- **既有产出目录**：`workspace/outputs/{audio,images,video}`（gitignored 运行时产物）——已有一套「统一产出文件夹」机制；脚本类无独立目录。本卡**沿用**该机制，新增 `workspace/outputs/scripts/`。
- **既有产出记录**：仅 `scripts/batch_generate.py` / `generate_10.py` 有批量 `batch-report.json`，无逐条脚本产出记录。本卡**补齐** `records.csv`（时间/主题/文件名/结果）逐条可追溯。
- **技术栈**：Python 3.12 · typer CLI · pytest(pytest-asyncio) · ruff · mypy strict。

### 实现说明

- 新增 `src/xianyu/content/video_script.py`：`generate_and_save(topic, duration_sec)` 一键入口 = 生成脚本（标题 + 分镜正文，LLM 失败骨架兜底保产物）→ 写入统一产出目录 → 落产出记录。复用了既有 `core/llm.chat_json` 与 `workspace/outputs/` 产出机制，未重复造轮子。
- 新增 CLI 命令 `xianyu video-script <主题> [--duration]`（`src/xianyu/cli.py`），默认 55s。
- 新增测试：`tests/content/test_video_script.py`（9 例，覆盖 ollama 成功 / 失败兜底 / 解析规整 / 写文件 / 记录 / 一键入口）+ `tests/test_cli.py` 2 条 CLI 用例。

### 测试结果

- 全量 pytest：**669 passed / 10 skipped / 3 failed**，覆盖率 **82.43%**（≥80 门禁过）。3 个失败（openclaw 插件集成 2 + bgm_tags 1）已在干净 `origin/main` 上复现，**与本卡改动无关**。
- `ruff check` 通过（涉改 4 文件）。
- **探针实测**（本机 Ollama 未启 → 走 mock 兜底路径，仍真产出）：
  - 命令：`.venv/bin/python -m xianyu.cli video-script "卖二手相机"`
  - 产物：`workspace/outputs/scripts/20260806-164350-卖二手相机.md` —— 含标题 `# 卖二手相机速成指南` + `## 分镜正文`（4 个分镜，各含标题/时长/正文）
  - 记录：`workspace/outputs/scripts/records.csv` 有对应行（timestamp / topic / file / result）
  - 同命令第二次运行进同一目录 → **路径可复现**。

### Push 证据

- 分支：`codex/xy001-write-video-script-command`（xianyu 仓，已推 `origin/codex/xy001-write-video-script-command`）
- commit：`bde76c3 feat(cli): add video-script one-key short video script generator`

## 机审区

**机审：通过** · Claude Code（2017 机审席）· 2026-08-07 00:53

> 机审结论已由 2017 机审席产出（`~/.ccc/logs/exec/xy001.audit.log`），但机审席未把 `## 机审区` 落盘到生产卡，engine 后置检查误判打回。本区由中枢按 audit.log 真实结论人工补录，不改变判定内容。

机审席独立取证（不采信回写区摘要），证据如下：
- 验收 1：敲 `video-script "卖二手相机"` 生成脚本文件，含标题 `# 卖二手相机速成指南` + `## 分镜正文`（4 个分镜各含标题/时长/正文）——独立实测复现。
- 验收 2：落统一产出文件夹 `workspace/outputs/scripts/`，路径可复现（同命令第二次跑进同一目录）。
- 验收 3：产出记录 `records.csv` 有本条（时间/主题/文件名/结果）——独立实测已追加。
- 验收 4：现状分析写清（复用 `workspace/outputs/` 机制沿用 + 补 `records.csv`）。
- 红线核对：只动 xianyu 仓；代码走 `codex/xy001-write-video-script-command` 分支未直推 main；探针真跑通；CCC 仓无业务深文档。
- 边界核查：2 个失败全在 `tests/openclaw/test_plugin_integration.py`（插件环境集成），与本卡无关；target 22 个测试全通过。

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
