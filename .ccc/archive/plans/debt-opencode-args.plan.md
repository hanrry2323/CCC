# debt-opencode-args

> 标题: 修复 opencode-exec.py 调用参数错误
> 创建: 2026-07-07T12:45:01Z

## 目标

## 问题
dev_role() 第 162 行传的是 plan.md 路径，但 opencode-exec.py 要求的是 --phase <id> --prompt <file>。

当前调用：
```
python3 opencode-exec.py .ccc/plans/task.plan.md
```
实际上必须：
```
python3 opencode-exec.py --phase task-p1 --prompt /tmp/exec-prompt.txt [--timeout 300]
```

## 执行方案
1. dev_role() 从 plan.md 读取内容，写入 temp prompt 文件
2. 调 opencode-exec.py 正确传参：--phase <id> --prompt <tempfile> --timeout <from phases.json>
3. 删除 temp 文件
4. 验证：跑 python3 ccc-board.py dev 观察结果

## Phase

(由 dev 拆)

## Commit 计划

- dev 完成后自动 commit + push
