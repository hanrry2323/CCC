# Skill: bug-fix

> 职能：bug 修复（proactive-epic 链路）
> 库路径：skills/bug-fix

## 职责

响应 proactive 信号（CI 失败 / git_hook 异常 / external 触发），定位并修复 bug：
- 读取 failure_pack / 异常信号
- 定位根因
- 最小化修复
- 跑回归探针验证

## 工作方式

1. 读取 proactive payload（source + failure_pack + payload_hash）
2. 定位失败任务 / 异常文件
3. 分析根因（日志 / stack trace / diff）
4. 最小化修复（≤3 文件）
5. 运行验收探针 + 回归探针
6. 探针全绿 → auto-commit（含 task_id + fix 标记）

## 验收方式

- 原探针 + 回归探针全绿
- git diff 符合最小化 scope
- commit 信息含 fix 标记

## 配套 Prompt

prompts/bug-fix-prompt

## 默认执行器

opencode
