# 幂等 Commit (Red Line 15)

> **状态**: ✅ v1.1 实装  ·  **关联**: [`scripts/ccc-exec-commit.sh`](../scripts/ccc-exec-commit.sh)、[roadmap.md §红线 15](roadmap.md)、[tests/scripts/test_ccc_exec_commit_idempotency.py](../tests/scripts/test_ccc_exec_commit_idempotency.py)

## 为什么需要幂等

跨设备 / 跨 session 同步 commit 时，**重跑同一任务不应产生重复 commit**。
传统 commit message 是自然语言（`feat: add foo`），无法被机器快速识别"这次 commit 和上次是不是同一任务"。
CCC 用 `ccc-task-id=<id>` 标记把 task 与 commit 绑定，让 `git log --grep` 即可识别重复。

## 机制

### 1. `phases.json` 顶层必填字段 `task_id`

```json
{
  "task_id": "task-uuid-2026-07-06-001",
  "phases": [
    {
      "id": 1,
      "status": "done",
      "commit": null,
      "scope": ["scripts/ccc-exec-commit.sh"],
      "commit_message": "feat(commit): add ccc-task-id enforcement (phase 1/2) ccc-task-id=task-uuid-2026-07-06-001"
    }
  ]
}
```

> ⚠️ **缺 `task_id` 字段 → 脚本拒绝 (exit 1)**
> 任何 phases.json 缺顶层 `task_id` 都会在脚本入口处直接失败，避免后续 commit 缺锚点。

### 2. `commit_message` 必须含 `ccc-task-id=<task_id>`

每个 phase 的 `commit_message` 字段必须包含 `ccc-task-id=<task_id>` 标记。
**缺标记 → 该 phase 报错跳过，errors += 1，整次 exit 1**。

为什么不在脚本里自动注入？答：保持 Executor 决策权。
Executor 写 phases.json 时已经规划了 commit message，标记由 Executor 显式填入（Planner 草稿通常已含）。
脚本只做"是否合格"的硬性校验。

### 3. `ccc-task-id=<id>` 全局幂等

`ccc-exec-commit.sh` 进入主循环**之前**，先执行：

```bash
git log --grep="ccc-task-id=<task_id>" --oneline -1
```

如果 git log 中已有相同 task_id 的 commit → **整次调用直接 `exit 0`**，不做任何 add/commit。
这就是"re-run 命中 fast-forward，不产生重复 commit"。

## 三条路径速查

| 场景 | commit_message 含标记 | git log 已有同 task_id | 结果 |
|------|----------------------|------------------------|------|
| **首次成功** | ✅ | ❌ | exit 0，正常 commit |
| **缺标记拒绝** | ❌ | ❌ | exit 1，errors += 1，无 commit |
| **重复幂等** | ✅ | ✅ | exit 0，IDEMPOTENT 提示，无新 commit |
| **缺 task_id 拒绝** | — | — | exit 1，phases.json 顶层校验失败 |

## 使用流程

### Executor 写 phases.json

```python
import uuid
task_id = str(uuid.uuid4())  # 或用项目约定的命名规范
phases = {
    "task_id": task_id,
    "phases": [
        {
            "id": 1,
            "status": "done",
            "commit": None,
            "scope": ["path/to/file1.py", "path/to/file2.md"],
            "commit_message": f"feat(scope): description (phase 1/N) ccc-task-id={task_id}",
        }
    ],
}
```

### 运行 commit

```bash
bash scripts/ccc-exec-commit.sh <workspace> <task_name>
# 例: bash scripts/ccc-exec-commit.sh . chunk-id-idempotent-commit
```

### 跨设备同步

`ccc-task-id` 是跨设备唯一的语义锚点。M1 / mac2017 / HP 任一节点 commit 同 task_id，
其他节点 re-run 都命中幂等跳过 —— **保证分布式环境下 commit 唯一性**。

## 异常处理

| 错误信息 | 原因 | 修复 |
|---------|------|------|
| `phases.json 缺少顶层 'task_id' 字段` | schema 不全 | 在 phases.json 顶层加 `task_id` 字段 |
| `commit_message 缺少标记 'ccc-task-id=xxx'` | Executor 漏写标记 | 在 `commit_message` 末尾加 `ccc-task-id=<task_id>` |
| `工作区已有已暂存未提交的文件` | 外部脚本预 add | 先 `git reset HEAD <files>` 或 `git commit` 处理已暂存内容 |
| `IDEMPOTENT: task 已提交` | 正常 — 重复执行 | 无需操作，幂等符合预期 |

## 单元测试

`tests/scripts/test_ccc_exec_commit_idempotency.py` 覆盖：

1. `test_path1_with_marker_commits_successfully` — 含标记 → commit 成功 + phases.json commit 字段回填
2. `test_path2_without_marker_rejected` — 缺标记 → exit 非 0，无新 commit
3. `test_path3_repeated_run_idempotent` — 重复执行 → exit 0，无新 commit，IDEMPOTENT 提示
4. `test_phases_missing_task_id_rejected` — 缺 task_id 字段 → 入口拒绝
5. `test_script_syntax` — `bash -n` 语法零错误

运行：

```bash
python3 -m pytest tests/scripts/test_ccc_exec_commit_idempotency.py -v
```

## 设计权衡

- **未自动注入 task_id 到 commit_message** — 让 Executor 显式声明，强制 schema 完整性
- **未在 references/red-lines.md 写红线 15 正式条目** — 留待 CCC 维护者审阅后再定稿（避免 AI 直接写红线违反红线 18）
- **git log 幂等检测在主循环之前** — fast-fail，避免对已提交 phase 重复 git add/commit
- **未加 retry-count 字段** — v1.0 PoC 简化版，v1.2 路线再扩展

## 关联文档

- [`docs/roadmap.md` §红线 15](roadmap.md) — 设计草案与 v1.0 路线
- [`DESIGN-VALIDATION.md` §chunk_id 幂等性](../DESIGN-VALIDATION.md) — 反借鉴论证
- [`references/cluster-protocol.md`](../references/cluster-protocol.md) — 跨设备协议（v1.2 集成）
