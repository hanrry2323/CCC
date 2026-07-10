# board-task-schema — task JSONL 格式标准

> **用途**：定义 CCC 看板 task 文件的 JSON 格式，作为 CCC-QXO 共享契约的基础。
> QXO 按此格式写入 `.ccc/board/backlog/`，CCC 自动拾取处理。
>
> v0.19 新增。

---

## 1. Task 文件

每任务一个 `.jsonl` 文件，文件名为 `<task_id>.jsonl`，放在对应列目录下。

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 唯一标识，建议用 kebab-case（如 `feat-login`），文件名称与之相同 |
| `title` | string | 是 | 任务标题，一句话描述 |
| `description` | string | 否 | 详细描述，多行文本 |
| `status` | string | 是 | 看板列名，取值：`backlog` / `planned` / `in_progress` / `testing` / `verified` / `released` / `abnormal` |
| `created_at` | string | 是 | ISO 8601 格式 UTC 时间戳，如 `2026-07-08T12:00:00Z` |
| `updated_at` | string | 是 | 最后更新时间，格式同上 |
| `assignee` | string\|null | 否 | 负责人，缺省 null |
| `tags` | string[] | 否 | 标签列表，如 `["bug", "urgent"]` |
| `note` | string\|null | 否 | 额外备注，abnormal 列带异常原因 |
### 示例

```json
{
  "id": "fix-login-500",
  "title": "修复登录接口 500 错误",
  "description": "用户反馈登录时偶现 500，排查后端异常",
  "status": "backlog",
  "created_at": "2026-07-08T12:00:00Z",
  "updated_at": "2026-07-08T12:00:00Z",
  "assignee": null,
  "tags": ["bug", "p0"],
  "note": null,
  "schema_version": "1.0"
}
```

### 存储位置

```
<workspace>/.ccc/board/
├── backlog/       # 待处理
├── planned/       # 已计划（有 plan.md + phases.json）
├── in_progress/   # 执行中
├── testing/       # 待测试
├── verified/      # 已验证
├── released/      # 已发布
└── abnormal/      # 异常隔离
```

---

## 2. 事件文件

每个 task 的流转历史记录在 `.ccc/board/events/<task_id>.events.jsonl`。

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `event` | string | 是 | 事件类型，当前仅 `"move"` |
| `task_id` | string | 是 | 对应 task 的 id |
| `from` | string | 是 | 源列名 |
| `to` | string | 是 | 目标列名 |
| `timestamp` | string | 是 | ISO 8601 格式 |

### 示例

```json
{"event": "move", "task_id": "fix-login-500", "from": "none", "to": "backlog", "timestamp": "2026-07-08T12:00:00Z"}
{"event": "move", "task_id": "fix-login-500", "from": "backlog", "to": "planned", "timestamp": "2026-07-08T12:05:00Z"}
```

---

## 3. 状态总览

`index.json` 记录各列的任务数量：

```json
{
  "backlog": 0,
  "planned": 0,
  "in_progress": 0,
  "testing": 0,
  "verified": 0,
  "released": 23,
  "abnormal": 0
}
```

---

## 4. Phases 文件格式

phases.json 是 product 角色产出的执行计划文件。首行为 schema 元数据，后续每行为一个 phase。

### 格式

```json
{"schema_version": "1.1"}
{"phase": 1, "status": "pending", "scope": ["file.py"], "commit_message": "feat: ...", "commit": null, "subtasks": {"1.1": "done"}, "timeout": 300, "notes": "", "retry": 0, "retry_at": null, "depends_on": []}
{"phase": 2, "status": "pending", "scope": ["file2.py"], "depends_on": [1]}
```

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | 元数据行 | 格式版本号，当前 `"1.1"`。仅出现在首行 |
| `phase` | int | 是 | phase 编号（task 内唯一） |
| `status` | string | 是 | `pending` / `blocked` / `in_progress` / `done` / `verified` / `failed` / `skipped` |
| `scope` | string[] | 否 | 此 phase 涉及的文件列表 |
| `commit_message` | string | 否 | commit message |
| `commit` | string\|null | 否 | commit hash，执行后填充 |
| `subtasks` | dict | 否 | 子任务状态 |
| `timeout` | int | 否 | 超时秒数，默认 600 |
| `retry` | int | 否 | 当前重试次数 |
| `retry_at` | string\|null | 否 | 下次可重试的时间点 |
| `depends_on` | int[] | 否 | **v0.24**：依赖的前置 phase 编号列表。`[]` 或缺省 = 无依赖。Engine 在所有依赖 phase 状态为 `done`/`verified`/`skipped` 时才执行 |

### Phase 状态流转（v0.24）

```
pending → blocked → in_progress → done → verified
                                  ↘ failed → skipped（下游依赖跳）
```

- `blocked`：有 `depends_on` 未满足
- `skipped`：因依赖的 phase `failed`，本 phase 被跳过
- `failed`：phase 执行失败且重试耗尽；触发下游依赖 `skipped`

---

## 5. 列流转规则

```
backlog → planned → in_progress → testing → verified → released
                                                              ↓ (regress)
                                                         backlog(回归bug)
```

- **不可跳列**：必须逐列前进（红线 X4）
- **异常列**：任何列都可转入 abnormal（自动隔离），修复后回到 `backlog`
- **回归**：released 由 regress 回测，发现 bug 移回 backlog

---

## 6. 与 QXO 的互通

QXO 向 CCC 提交任务：

```bash
# QXO 写入 task 到 CCC 看板的 backlog
cat > /path/to/workspace/.ccc/board/backlog/my-task.jsonl << EOF
{
  "id": "qxo-task-001",
  "title": "QXO 生成的自动化任务",
  "description": "来自 QXO SelfLoop 的自动任务",
  "status": "backlog",
  "created_at": "2026-07-08T12:00:00Z",
  "updated_at": "2026-07-08T12:00:00Z",
  "tags": ["qxo"],
  "schema_version": "1.0"
}
EOF
```

CCC 下次 product 角色轮询时自动拾取该任务。
