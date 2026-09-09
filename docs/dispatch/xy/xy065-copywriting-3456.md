# 任务卡 xy065 · 文案生成垂类化+3456 通道接入（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy065 · 状态版本：5
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

当前文案由本地 Ollama qwen2.5:7b 生成（449 字泛 AI 套话，无闲鱼垂类场景）。本卡完成两件事：

1. **生成模型切换 3456 通道**（老板已拍板 Code/flash 均可）：`src/xianyu/core/llm.py` 已是 OpenAI 兼容 `/v1/chat/completions` 协议，3456 通道同协议（**已实测 200**：`http://127.0.0.1:3456/v1/chat/completions`，model 名 `Code` 或 `flash`）。改法：Settings 支持环境变量覆盖 `LLM_BASE_URL`/`LLM_MODEL`（默认值切到 3456+Code），请求头加 `Authorization: Bearer <key>`——key 从环境变量 `ANTHROPIC_API_KEY` 运行时读取，**不得把 key 值写入任何文件或提交**；Ollama 保留为 env 可切回的降级兜底。
2. **文案垂类化+结构锁死**：改造 `src/xianyu/content/` 的选题/写作 prompt（writer.py/topic.py/prompts/）：①选题限闲鱼垂类（捡漏案例/闲置变现复盘/副业数据），每期围绕一个具体案例；②结构四段锁死：3 秒钩子（≤2 句）→ 痛点场景 → 3 条干货（每条含具体数字或案例）→ 行动号召；③字数目标 350±50。
3. **测试**：llm.py 的 endpoint/header/model 逻辑单测（mock http，不真调外部服务）；prompt 结构约束的单测（关键词/段落数断言）。全部测试真实通过。

## 实现要求

1. 改动限于：`src/xianyu/core/config.py`、`src/xianyu/core/llm.py`、`src/xianyu/content/`（writer/topic/prompts）、对应 `tests/`。
2. 环境变量优先、默认值兜底：`LLM_BASE_URL`（默认 `http://127.0.0.1:3456/v1`）、`LLM_MODEL`(默认 `Code`)；`OLLAMA_*` 保留可切回。
3. key 只从 `os.environ` 运行时读取（`ANTHROPIC_API_KEY`，可被 `LLM_API_KEY` 覆盖）；任何测试/文档/代码中不得出现 key 明文。
4. 3456 不可达时按现有 fallback 语义降级（如实记录降级，不虚报）。

## 红线

1. 只改 xianyu 业务仓；不发布、不触碰 Cookie/外部账号、不启动 M7。
2. 禁止把任何凭据值写入文件、测试、日志或提交。
3. 不得删除既有产物/数据库；所有改动业务分支 commit；测试真实通过。
4. 结果如实记录；不得把降级写成成功。

## 范围

- `/Users/fan/program/apps/xianyu/src/xianyu/core/config.py`
- `/Users/fan/program/apps/xianyu/src/xianyu/core/llm.py`
- `/Users/fan/program/apps/xianyu/src/xianyu/content/writer.py`
- `/Users/fan/program/apps/xianyu/tests/core/test_llm.py`

## 步骤

1. 读业务仓约束与 llm.py/config.py 现状；跑 `tests/core/test_llm.py` 确认基线。
2. 实现 3456 通道接入（env 覆盖+Authorization 头+默认值切换）。
3. 实现垂类选题与四段结构 prompt 约束。
4. 补单测（mock http）：endpoint/header/model 断言、prompt 结构断言、降级路径断言。
5. 全量相关测试真实通过；业务分支 commit；`.ccc-result.md` 如实记录（含探针原始输出）。

## 验收标准

1. `LLM_BASE_URL`/`LLM_MODEL` 环境变量生效；默认指向 3456+Code；Authorization 头正确携带（单测断言）。
2. prompt 四段结构+字数约束在代码中可断言；单测覆盖。
3. `tests/core/test_llm.py` 及相关 content 测试全部通过退出码 0；全量回归无新增失败。
4. 代码/测试/文档中无任何凭据明文。
5. 业务分支 commit 存在；工作树除结果文件外干净。
6. 不虚报：3456 不可达的降级路径如实记录。

## 门禁

测试（核心+content）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest tests/core/test_llm.py tests/content/ -q`

## 回写要求

结果写入 `.ccc-result.md`，含：改动 diff 摘要、测试原始输出、env 覆盖断言的测试证据、（如做了真实调用）3456 响应原始片段（脱敏，不含 key）、维护区四问（标准键名）、变更证据。

## 批注落实

任务卡「## 人工批注」原文：1. 【教训引用·外脑】上轮机审 Q2：维护区②声明[有]教训沉淀但未引用 lessons 文件。教训已由外脑落业务仓 `docs/lessons.md` **Lesson 165**（provider 标识切换属行为契约+stash 对照归因法，即维护区②所述内容）。

1. 【教训引用】修复轮落实：维护区②说明末尾补「证据：`docs/lessons.md` Lesson 165」；教训实质（provider 标识行为契约+stash 对照法）为本卡执行体第一轮自报，外脑仅代为落库成文。代码（3459bc9）无需重做。

## 人工批注

无

## 回写区

## 0. 卡标题复述

任务卡 xy065「文案生成垂类化+3456 通道接入（开发线 Build）」：① 生成模型切换 3456 通道（`LLM_BASE_URL`/`LLM_MODEL` env 覆盖，默认 `http://127.0.0.1:3456/v1`+`Code`，请求头 `Authorization: Bearer <key>`，key 仅运行时从 `os.environ` 读 `ANTHROPIC_API_KEY`（可被 `LLM_API_KEY` 覆盖），Ollama 保留 env 可切回兜底）；② 文案垂类化+结构锁死（选题限闲鱼垂类：捡漏案例/闲置变现复盘/副业数据；结构四段：3 秒钩子≤2 句→痛点场景→3 条干货（每条含数字/案例）→行动号召；字数 350±50）；③ 单测（mock http 断言 endpoint/header/model；prompt 结构断言）全部真实通过。

## 1. 探针输出

| 探针 | 命令 | 输出 | 结论 |
|---|---|---|---|
| 基线门禁（改动前，即现 HEAD） | `/Users/fan/program/apps/xianyu/.venv/bin/pytest tests/core/test_llm.py tests/content/ -q` | `86 passed in 2.63s`，EXIT=0 | 门禁绿 ✓ |
| 全量回归 | `.venv/bin/pytest tests/ -q` | `4 failed, 769 passed, 8 skipped in 53.25s`，EXIT=1 | 4 失败全在 `tests/openclaw/test_plugin_integration.py`，见下 |
| openclaw 失败根因 | 单独重跑该文件（worktree 与权威仓 main 各一次） | `stderr: .../xianyu/.venv/bin/python: No module named xianyu`；权威仓 main 同文件同样失败（2/4），worktree 因符号链接 venv 布局多 2 个 | 环境性预存失败（子进程模块解析），与本卡改动文件零交集，非新增 |
| 3456 可达性 | `curl -s -o /dev/null -w "HTTP %{http_code}" -m 5 http://127.0.0.1:3456/v1/chat/completions -X POST ...` | `HTTP 200`，curl exit 0 | 3456 可达（与卡一致） |
| 默认通道（无 env） | `PYTHONPATH=src ... python -c "llm._endpoint()/llm._model()"` | `DEFAULT endpoint: http://127.0.0.1:3456/v1/chat/completions` / `DEFAULT model: Code` | 默认切 3456+Code ✓ |
| env 覆盖 | 同上设 `LLM_BASE_URL=http://env-probe:9999/v1` `LLM_MODEL=flash` | `ENV endpoint: http://env-probe:9999/v1/chat/completions` / `ENV model: flash` | env 优先 ✓ |
| Authorization 头 | 设 `ANTHROPIC_API_KEY=probe-key-not-real` 调 `llm._headers()` | `{'Content-Type': 'application/json', 'Authorization': 'Bearer probe-k...<redacted>'}` | key 运行时读 env，值脱敏展示 ✓ |
| 无 key | 清 key env 调 `_headers()` | `{'Content-Type': 'application/json'}`（无 Authorization） | ✓ |
| Ollama env 可切回 | 设 `OLLAMA_BASE_URL/OLLAMA_MODEL` | `OLLAMA endpoint: http://192.168.3.131:11434/v1/chat/completions` / `OLLAMA model: qwen2.5:7b` | env 可切回 ✓ |
| 真实 3456 调用 | `chat_text('用一句话介绍闲鱼捡漏，30字以内。', max_tokens=128, timeout=30)` | `REAL RESP len=16` / `REAL RESP head='闲鱼低价淘好物，全凭手速与眼力。'` | 真实链路通 ✓ |
| 降级路径（3456 不可达） | 设 `LLM_BASE_URL=http://127.0.0.1:9/v1` 跑 WriterWorker/TopicWorker | `[topic] LLM 调失败 → fallback mock: All connection attempts failed` → `TOPIC engine: mock \| success: True`；`[writer] ... → WRITER engine: mock \| success: True` | 按现有 fallback 语义降级，如实记录不虚报 ✓ |
| 凭据明文扫描 | `git diff 3459bc9^ 3459bc9` 全 diff grep 长串/`sk-`/Bearer 值 | 仅代码行（`headers["Authorization"] = f"Bearer {key}"`）、env 变量名、测试夹具（test-key 等假值）；无真实凭据明文 | 代码/测试/文档无凭据明文 ✓ |
| 批注落实证据核验 | `grep -n "Lesson 165" /Users/fan/program/apps/xianyu/docs/lessons.md` | `1651: ## Lesson 165：LLM provider 标识切换属行为变更，须同步测试断言；全量回归预存失败用 stash 对照归因`（commit `e2f1066`，分支 main） | Lesson 165 已由外脑落权威仓 ✓（本 worktree 分支不含该 commit，docs/lessons.md 不在白名单，未改动） |

## 2. 自测输出

- 门禁（卡命令原样）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest tests/core/test_llm.py tests/content/ -q` → `86 passed in 2.63s`，退出码 0。
- 单测覆盖核对（全部通过，属 86 之内）：
  - endpoint/header/model 断言：`test_endpoint_defaults_to_3456`、`test_model_defaults_to_code_when_unset`、`test_settings_env_override_llm_base_url_and_model`、`test_endpoint_model_obey_env_override`、`test_ollama_env_switches_endpoint`、`test_headers_include_authorization_when_anthropic_key_set`、`test_headers_llm_api_key_takes_precedence`、`test_headers_no_authorization_without_key`、`test_chat_json_sends_auth_header_and_model`、`test_chat_text_sends_auth_header`。
  - prompt 结构断言：`test_writer_prompt_contains_vertical_constraints`、`test_writer_prompt_contains_four_section_markers`、`test_writer_prompt_contains_word_count_target`、`test_validate_copy_structure_*`（缺标记/钩子超句/字数越界/常量自洽）、`test_topic_prompt_contains_vertical_categories`、`test_topic_prompt_requires_concrete_case`、`test_video_script_prompt_contains_four_section_markers`。
- 全量回归：`4 failed, 769 passed, 8 skipped`（53.25s）。4 个失败均在 `tests/openclaw/test_plugin_integration.py`，根因 `No module named xianyu`——测试以子进程 `python -m xianyu` 且不带 PYTHONPATH，模块解析失败；权威仓 main（无 xy065 改动）同文件亦失败，worktree 因 `.venv` 为指向权威仓 venv 的符号链接额外多 2 个失败。属环境预存问题，与本卡改动文件（core/config、core/llm、content/*、对应 tests）零交集，非本卡新增失败。
- 工作树状态：`git status --porcelain` 仅 `?? .venv`（wrapper 建仓时创建的符号链接，gitignore 的 `.venv/` 目录模式不匹配符号链接故显示 untracked；环境工件，非本卡产物，白名单外未动、未提交）。
- 修复轮说明：本轮回合未改任何代码（批注落实#2：代码 3459bc9 无需重做）；全部验证基于现 HEAD=3459bc9。

## 维护区

1. **方案同步**：[是] 3456 通道（env 覆盖+Authorization 头+默认 3456+Code+Ollama env 可切回）与闲鱼垂类四段结构 prompt 均已实现，门禁 86 passed 全绿，真实 3456 调用与降级路径均实测验证；验收 6 项逐条满足。
2. **教训沉淀**：[有] writer/topic 的 `engine` 标识从 "ollama" 切到 "llm" 属行为变更，已同步更新对应测试断言；全量回归 openclaw 预存失败（子进程模块解析，main 亦复现）经对照确认与本卡无关。证据：`docs/lessons.md` Lesson 165。
3. **档案/README**：[否] 未改任何文档（.env.example 不在白名单，未触碰）；llm.py/writer.py/topic.py/video_script.py 的模块 docstring 已内联说明新通道与结构约束。
4. **线路图**：[否] 本卡为开发线 Build，无线路图改动要求，未改规划文档。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：完成钩子：维护区只找到 1/4 问
