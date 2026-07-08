# phases.json 规范

## 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `phase` | int | 阶段编号，从 1 开始 |
| `status` | string | `pending` - `in_progress` - `done` / `failed` |
| `subtasks` | object | 键名自定，值同为 status |
| `commit` | string\|null | 完成后填 commit hash（7 位以上） |
| `notes` | string | 失败原因 / 重试 / 跳过说明 |

## 规则

- 每个 task 独立一个 phases.json 文件，不与其他 task 共用
- 行数 = phase 数。单 phase 也至少写 1 行
- 不许跳阶段更新（pending → done 必须经过 in_progress）
- 每个 phase 独立对应一个 commit
- failed phase 不删行，标记后继续
- phase 全完成后，按相同的行顺序更新，不插入新行
