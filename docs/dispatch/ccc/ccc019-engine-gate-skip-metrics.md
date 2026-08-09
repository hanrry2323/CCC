# 任务卡 ccc019 · engine gate skip metrics（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 目标

在引擎门禁跳过时记录指标：每次因环境缺失跳过门禁时，写入 structlog 日志（含 card_id、gate_name、reason）。

## 红线（先看）

1. 只加日志，不改门禁逻辑
2. 零硬编码
3. 若本卡含 `## 人工批注`，执行体必须先读批注

## 范围

- `server/engine/main.py`：门禁跳过段追加指标日志
- `server/tests/test_engine_main.py`：新增测试

## 步骤

1. 在 `_dispatch_and_collect` 门禁跳过处追加 structlog 日志
2. 日志格式：`gate_skip card=xxx gate=xxx reason=env_missing`
3. 新增测试用例
4. pytest 全绿
5. commit+push 到卡内分支；卡头改为「已回写」
6. **停手**## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 门禁跳过时可见 structlog 日志
2. `pytest server/tests/test_engine_main.py` 全绿
3. 零硬编码

## 门禁

范围: true

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. 在 `server/engine/main.py` 门禁跳过处，引入并定义了 `structlog` logger。
2. 当由于环境缺失（`cmd_exists` 为 `False`）跳过门禁时，在日志警告后追加了 `structlog` 级别的 info 日志：
   `metrics_logger.info("gate_skip", card=work.id, gate=gate_name, reason="env_missing")`
   完全满足指标记录的要求。

### 测试结果
1. 在 `server/tests/test_engine_main.py` 中新增单元测试 `test_gate_skip_env_missing_metrics_logged`。
2. 该测试通过 Mock `structlog` logger 来捕获日志输出，验证在由于环境缺失跳过门禁时是否确实生成了指定格式 of 日志。
3. 执行 `pytest` 全量测试，81 个测试用例全数通过。

### push 证据
- 提交分支：`codex/ccc019-engine-gate-skip-metrics`
- commit hash: `c00637223bd8d028b1daf35039574525267c733b`

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 禁区：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭
