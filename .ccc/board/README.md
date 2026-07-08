# CCC 任务看板

7 角色多阶段开发系统。任务在 6 列间流转：

```
backlog → planned → in_progress → testing → verified → released
   ↑          ↓          ↓            ↓          ↓
 product    product     dev       tester    reviewer    releaser
                                         (or kb)
```

每列 = 一个目录，里面放该阶段的任务 JSONL 文件：

| 列 | 目录 | 含义 |
|----|------|------|
| backlog | `.ccc/board/backlog/` | 老板/用户提的原始需求，未拆分 |
| planned | `.ccc/board/planned/` | 产品经理拆好，plan.md + phases.json 写好 |
| in_progress | `.ccc/board/in_progress/` | 开发工程师正在写 |
| testing | `.ccc/board/testing/` | 测试工程师在跑 pytest |
| verified | `.ccc/board/verified/` | 代码审查员/Verifier 通过 |
| released | `.ccc/board/released/` | 推远端 + tag |

JSONL 格式（每行 1 个 task）：
```json
{"id":"v0.16-e2e","title":"e2e 验证看板","status":"backlog","created_at":"2026-07-07T17:30:00Z","updated_at":"2026-07-07T17:30:00Z","assignee":null,"tags":["e2e","v0.16"]}
```

`index.json` 状态总览（自动生成）：
```json
{
  "backlog": 0,
  "planned": 1,
  "in_progress": 0,
  "testing": 0,
  "verified": 0,
  "released": 0
}
```

## 7 角色

| 角色 | 频率 | 扫哪列 | 处理后挪到 |
|------|------|--------|------------|
| product | 4h | backlog | planned (写 plan.md + phases.json) |
| dev | 10min | planned + in_progress | in_progress → testing |
| reviewer | 2h | testing | testing → verified (过 ruff/mypy) |
| tester | 4h | testing | testing → verified (过 pytest) |
| ops | 30min | (所有列) | 健康检查 + 告警 |
| kb | 23:00 | verified | verified → released (归档) |
| regress | 23:30 | released | released → backlog (回归回测 + 建 bug) |

## 任务流转示例

1. 老板说"按 CCC 跑 X" → product 写 task 到 backlog
2. 4h 后 product 跑：扫 backlog → 写 plan.md → 挪 planned
3. 10min 后 dev 跑：扫 planned → 调 opencode-exec → 挪 testing
4. 2h 后 reviewer 跑：扫 testing → ruff/mypy → 通过则挪 verified
5. 4h 后 tester 跑：扫 testing → pytest → 通过则挪 verified
6. 23:00 kb 跑：扫 verified → 归档 + tag → 挪 released
7. 23:30 regress 跑：扫 released → 回测 → 回归 bug 倒回 backlog
