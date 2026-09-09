# 任务卡 xy065 · 文案生成垂类化+3456 通道接入（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy065 · 状态版本：1
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

## 人工批注

无

## 回写区

（待执行体回写）
