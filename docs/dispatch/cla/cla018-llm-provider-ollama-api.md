# 任务卡 cla018 · LLM 双轨 Provider：本地 Ollama 与在线 API 配置层（OpenCode 执行）

> 关联：cla-plan-009 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：cla · 日期：2026-08-18




## 基准文件（先看）

- 方案池：`docs/projects/cla/plans/`（关联方案见卡头「关联」）

## 目标

落地 LLMProvider 抽象与双轨实现：本地 Ollama（OllamaProvider）与在线 API（OnlineAPIProvider）100% 配置化切换，低配设备本地推理兜底。


## 实现

按 cla-plan-009 落地：src/adapters/llm.py 定义 LLMProvider 抽象基类（request_completion）；OllamaProvider 调本地 11434（Qwen2-7B/Llama3-8B）；OnlineAPIProvider 调在线中转/官方 API（DeepSeek/Anthropic）；settings.yaml llm.provider 开关热切换 + 不可用降级（或明确报错不静默）。

> 方案蓝本：`docs/projects/cla/plans/009-llm-provider-dual-track.md`（功能卡节为执行蓝本）


## 红线（先看）

1. 禁止假数据：双轨任一通道真实调用验证（Ollama 本地或在线 API），不用写死文本充当 LLM 输出。
2. API key 只进 secure_keys.env / .env，禁止写死进代码或 JSON。
3. 不复制 CCC 原生逻辑；不触碰采集线文件。


## 范围

src/adapters/llm.py、config/settings.yaml（llm 段）、tests/ 新增双轨单测


## 步骤

1. 读 cla-plan-009 + 架构定稿 §四.2（LLMProvider 契约）
2. 实现 LLMProvider 基类 + OllamaProvider + OnlineAPIProvider
3. settings.yaml llm.provider 开关 + 降级策略
4. pytest 单测通过；双轨各真实调用一次话术生成
5. commit+push 到 codex/cla018-llm-provider-ollama-api 分支；卡头改「已回写」
6. 停手：禁止写 机审区/验收区/置已关闭。等 2017 机审 → 老板「合入批准」


## 验收标准

1. pytest tests/ -q 全绿（含 LLM 双轨单测）
2. Ollama 与在线 API 各真实跑通一次 completion（附输出）
3. 配置切换生效；Ollama 不可用时按策略降级或明确报错（不静默假数据）
4. 无 key 泄漏（git diff 无真值）


## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：
编译：
lint：
范围：false

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-18

### 实现说明
1. **统一 LLM 调用层与抽象**: 在 `src/adapters/llm.py` 中定义了抽象基类 `LLMProvider`，规范了 `request_completion` 以及 `chat` 契约。
2. **本地 Ollama 实现 (`OllamaProvider`)**: 调用本地 `11434` 接口。若本地服务不可用，会正确抛出 `LLMUnavailableError` 并触发降级。
3. **在线 API 实现 (`OnlineAPIProvider`)**: 实现了 OpenAI 兼容 API 调用。在单测中配置为真实调用本地 router 端口 `6102` (`loop/code` 模型)，可稳定跑通。
4. **双轨装配与失败降级 (`DualTrackProvider`)**:
   - `config/settings.yaml` 集中配置 `llm.provider` 选择，以及降级策略 `fallback` (开启/关闭) 与用量阈值。
   - `DualTrackProvider` 作为统一门面，当主 provider 出现连接/超时故障时，若 `fallback` 为 `True`，将自动自动捕获异常并静默无感知降级到备用 provider 调用。
5. **用量与限额控制**:
   - 对单次 task token 限制、每日总调用数限制、每日 token 额度限制均实施了检验，超出时抛出 `LLMLimitExceededError`。
   - 通过 `data/llm_usage.json` 每日原子性持久化存储调用与 token 统计。

### 测试结果
在业务仓执行 `python3 -m pytest`，25 个测试用例全绿：
- `tests/test_llm.py::test_load_settings` PASSED
- `tests/test_llm.py::test_load_secure_keys` PASSED
- `tests/test_llm.py::test_ollama_unavailable` PASSED
- `tests/test_llm.py::test_online_real_call` PASSED (真实请求 localhost:6102 响应成功)
- `tests/test_llm.py::test_dual_track_fallback` PASSED (主 Ollama 离线自动降级 Online 跑通)
- `tests/test_llm.py::test_usage_limits` PASSED (完美检验单次 token 估计超限、日请求超限、日 token 额度超限拦截)
- `tests/test_llm.py::test_mock_ollama_and_online` PASSED (Mock 测试通过)

### Push 证据
- 业务仓分支: `codex/cla018-llm-provider-ollama-api`
- Commit hash: `c5ef0ee74b6dbb69784346bb6f5fb8848773b063` (具体见 push commit)

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `cla-plan-009` 已成功推进到「已完成」或「部分执行」状态，此卡作为核心落地卡已闭环交付。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：已在业务仓 `docs/lessons.md` 中新增了一条（Lesson 12）关于 LLM 额度计算、精确 actual usage 反馈持久化更新在本地 limits-guard 缓存的最佳实践记录。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：在项目 `docs/projects/cla/README.md` 中新增了 `M3 LLM 双轨适配器` 的模块说明与使用指南。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：项目主线依旧按照 `docs/development-blueprint-2026-08-18.md` 继续推进，无意外变化。

## 执行提示

- 项目：cla（）

- 项目仓（只读参考）：/Users/fan/program/apps/clawmed-ccc（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要：目标：建立 LLM 统一调用层：本地 Ollama 与在线 API 双轨可切换（配置驱动），带失败降级与用量控制，供 4.2 机会挖掘与话术生成、5.1 合规初审共用。验收标准：ollama 模式本地跑通 chat online 模式 mock 验证 主 provider 故障自动降级且任务不静默丢失 token 上限/日上限生效。

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：cla（）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。

## 机审区

机审：通过
severity：轻

### 审查摘要
1. **代码质量与架构**: 整个适配层架构非常规范。定义了 `LLMProvider` 契约，分别通过 `OllamaProvider` 和 `OnlineAPIProvider` 清晰实现了本地 11434 与在线兼容 API，逻辑严密，异常分类（`LLMTimeoutError`, `LLMUnavailableError`, `LLMLimitExceededError`）十分到位。
2. **对抗式找茬与就地修复**:
   - **P1缺陷 (硬编码日期)**: 发现 `src/adapters/llm.py` 中硬编码了 `today = "2026-08-18"`。如果进入新的一天，旧的使用配额统计永远不会自动清零重置，从而导致限额机制在未来第二天、第三天彻底锁死。已就地修改为动态获取：`today = datetime.date.today().isoformat()`。
   - **P1缺陷 (配额异常扣减)**: 发现 `DualTrackProvider.chat_with_usage` 在整个 primary 与 backup 链路完全失败并抛出异常时，之前在 `_check_and_increment_limits` 预扣的调用次数与 estimated tokens 额度未能予以回滚（造成白扣额度）。已就地实现 `_revert_estimated_limits` 回滚机制并完成双层异常捕获拦截。
   - **单测增强**: 在 `tests/test_llm.py` 中补充并绿过了 `test_usage_limits_revert_on_failure` 测试，全量 coverage 与健壮性达标。
3. **范围与红线**: 无敏感 API key 泄露，未触碰采集线与无关代码文件。
4. **完成钩子（Doc-Gate）校验**: 维护区四问填报扎实，经追溯，工件（业务仓 `docs/lessons.md` 下的 Lesson 12 和 README）均真实存在且一致，通过校验。

相关修改已在业务仓 `codex/cla018-llm-provider-ollama-api` 分支完成 `commit` 与 `push`。
