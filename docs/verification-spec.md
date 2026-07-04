# MiniMax 验收协议

> 来源：MiniMax Code verifier agent + ccg-workflow spec-review.md。

---

## 验收者

MiniMax Code 内置 `verifier` agent（`~/.mavis/agents/verifier`），提示词 200+ 行，核心信条：

> "默认不信，先查证再下结论。误判 PASS 是你最大的失败；误判 FAIL 顶多让人烦一下。"

## 触发方式

在 MiniMax Code 桌面端打开 `verifier` agent，告诉它：

> 验收任务 X。读 `.ccc/reports/X.report.md`，读 plan 对照，跑 git diff 逐项核对，输出 verdict 到 `.ccc/verdicts/X.verdict.md`。

## Verifier 的验证策略（摘录）

- 后端/API：启动服务 → 发真实请求 → 验证 response 结构
- 前端：启动 dev server → browser automation → curl 子资源
- 库/包：build → 全量测试 → 从新 context 验证公开 API
- Bug 修复：复现原 bug → 验证修复 → regression tests
- 重构：已有测试必须全过 → diff public API → spot-check 行为一致

每条检查必须带证据，格式：

```
### Check: [验证什么]
**Method:** [做了什么 — 命令、打开什么文件等]
**Evidence:** [实际输出 — 复制粘贴，不是转述]
**Result: PASS** (或 FAIL — 含 Expected vs Actual)
```

结尾输出：`VERDICT: PASS` 或 `VERDICT: FAIL`

## 三级严重度（CCG 格式）

| 级别 | 含义 | 处理 |
|---|---|---|
| Critical | 需求未实现、验收命令失败、文件超出范围 | 必须修 |
| Warning | 命名不统一、缺少文档、代码质量 | 建议修 |
| Info | 可优化的点 | 可选 |

## 结论规则

- PASS — 全部 Critical 为 0
- CONDITIONAL_PASS — Warning 非零但 Critical=0，可以合入但建议修
- FAIL — Critical > 0，退回

## 输出

`.ccc/verdicts/<task>.verdict.md`

## 模板格式

见 `~/program/CCC/templates/verdict.verdict.md`
