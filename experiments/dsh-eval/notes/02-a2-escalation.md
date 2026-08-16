# 实验 A2 · escalation 审批语义

- **状态**：✅ 完成（部分，见结论）
- **批次**：B1 安全
- **环境**：测试实例（headless code 模式，一次性）
- **日期**：2026-08-16

## 结论

**越权写被沙箱直接拦截（fail-closed），升级必须显式带 `sandbox_permissions` + `justification` 重试并触发审批；headless 无审批通道时升级一律拒绝。**「granted 后多轮 retry 是否重复审批」的路径在 headless **无法端到端实测**（无批准者），保持源码级确认（per-call stamping）+ 实测缺口。

## 方法

headless code 模式跑两轮探针：
- 轮1：程序两次 `tools.write` 到工作区外 `/Users/fan`（不带升级参数）→ 观察沙箱拒绝行为 + approval 事件数。
- 轮2：程序两次 `tools.write` 到工作区外，**显式带 `sandbox_permissions: danger-full-access` + `justification`** → 观察审批事件 + fail-closed 行为。

会话：`session-50cce55a-1151-4a0c-93d1-5c07bb590524`（轮1）、`session-1eb8a04a-c848-4639-98bd-baf989be1355`（轮2）。

## 结果

轮1（不带升级参数）：
```
t1_ERR [sandbox: file access denied under workspace-write mode]
       [sandbox: escalation available — retry this exact operation once with sandbox_permissions + justification; the approval prompt asks the user]
t2_ERR 同上
```
- code-dispatch: 2（两次 write 都派发）、approval 事件: 1、无文件落盘。

轮2（带 sandbox_permissions + justification）：
```
e1_ERR sandbox escalation to "danger-full-access" requires approval, but no approval channel is available
e2_ERR 同上
```
- dispatch args 含 `sandbox_permissions`、`justification`（透传正常）；approval 事件: 5；无落盘。

## 证据与解读

| 观察 | 结论 |
|---|---|
| 不带升级参数 → 沙箱直接拒 + 提示可升级 | 越权操作不会静默升级，必须先显式请求 |
| 升级参数 → approval/asked 事件触发 | 升级必经审批（approval 事件从 1→5） |
| 无审批通道 → `no approval channel is available` 拒绝 | **fail-closed**：headless 无 answerer 一律拒，不裸放 |
| 两次拒绝均未落盘 | 拒绝终局，无绕过 |

## 未覆盖

- **granted 后多轮 retry 是否重新审批**：需一个能"批准"的 answerer（GUI/程序化注入），headless 无法测。源码为 per-call stamping（allowed-once 才放行，dsh-user-approval/lib/index.js:185 附近），但未端到端验证。
- 建议后续：在 web 实例或带 answerer 的测试环境补测（如可注入 approval 决策的 profile）。

## 风险 / 对 CCC 借鉴的影响

- headless/无人值守场景下 **升级全部失败**——这是特性（fail-closed）也是限制（无法无人审批升级）。CCC 若用 DSH headless 做执行体，升级类操作要么预置高权限、要么人工盯。
- `ask` 策略 + 无通道 = 安全默认，值得吸收到 CCC 执行体边界。
