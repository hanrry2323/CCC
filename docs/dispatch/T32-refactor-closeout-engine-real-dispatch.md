# 任务卡 T32 · 重构收口：Engine 真实派发闭环（D1/M2 落地）（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§2 状态模型 / §7 执行体注册表 / §8 中转站）
> 依据：Codex 2026-08-03 全新取证重评——engine/main.py 仍为「T4 前不真拉执行体」占位（模拟拉起 + 不收单），未达 D1「Engine 定时/实时发单、派发、收单、更新看板」与 M2「首个任务经 Engine 全流程跑通」；注册表 schema 无启动命令字段
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03

## 目标

Engine 从「模拟拉起」变成「真实派发闭环」：按注册表配置真实拉起可后台 CLI 执行体、采集结果、按契约状态机收单并驱动看板；用 M1 本地临时演示卡跑通一条端到端流转。

## 红线（先看）

1. **演示用临时注册表 + 占位命令（echo/sleep）在 M1 本地验证管道**；禁止真拉生产执行体、禁止触碰 2017 运行面与生产 config.env。
2. 零硬编码：执行体命令/超时/工作目录全部走 config 或注册表（代码不出现工具名字面量，占位演示除外并注释）。
3. 无新第三方依赖（Python stdlib）；密钥不落盘；不改看板协议与任务卡格式。
4. 提交真实 commit；验收标准不可自行解释。

## 范围

server/engine/（dispatch.py、main.py、scheduler.py、store.py、task.py）、server/config/（loader.py、config.example.env、executors.example.json）、server/deploy/（如需）、server/engine/README.md、server/tests/。

## 步骤

1. 扩展注册表 schema：每条「可后台 CLI」行新增配置化字段（如 `命令` + `参数模板`，参数可含 {work_id}/{card_path} 占位）；loader.py 校验新增字段类型与必填性；config.example.env 增超时/日志目录等键（如 `EXECUTOR_TIMEOUT_SECONDS`、`EXECUTOR_LOG_DIR`）。
2. dispatch.py：AUTO 决策后生成真实启动命令（从注册表读取，绝不写死），`subprocess.Popen` + 超时 + 输出重定向到日志目录；启动失败 → 记录并回写为失败原因。
3. main.py：收单实现——按退出码与输出判定完成/失败，调用 store 按契约状态机流转（执行中 → 已回写/打回）；移除「T4 前不真拉」「模拟拉起」占位与 docstring 旧口径；持续模式保留心跳 + 新增催单日志（超时未回写任务）。
4. scheduler.py：只读巡检保持只读；变更类任务生成任务卡后进入 Engine 派发管道（不绕过）。
5. 端到端演示（M1 本地、临时目录）：临时 executors.json（命令=占位脚本/echo）+ 一张临时测试卡 → `engine --once` → 日志展示「真实拉起 → 执行完成 → 收单 → 状态流转」全链；输出 JSON 统计含 dispatched/collected 非零。
6. 单测补齐：派发命令生成、启动失败、超时、退出码 0/非 0、状态机非法转移；更新 engine/README 描述真实行为。
7. 三扫描自检（硬编码/密钥/外脑）后提交。

## 验收标准

1. `pytest server/tests -q` 全绿（新增派发/收单用例通过）。
2. 端到端演示日志（附在回写区）展示「真实拉起→完成→收单→状态流转」全链，非模拟。
3. 注册表/配置无代码内写死的执行体命令；`rg -n "模拟拉起|T4 前不真拉" server/` 零命中（含 README/docstring）。
4. 三扫描零命中；工作树仅剩许可预存项；真实提交。

## 回写要求

卡头状态更新为「已回写」；回写区填：schema 变更说明、派发/收单逻辑要点、端到端演示日志关键段、pytest 结果、commit hash。

## 回写区

**执行体**：Trae · 日期：

