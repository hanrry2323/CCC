# CCC Board Protocol v1 — 跨 IDE 任务编排协议

> **协议版本**: v1.2
> **状态**: stable
> **最后更新**: 2026-07-12
> **作用域**: CCC 0.26.0+

> **一句话定义**: 任意 IDE 工具（Trae/Cursor/Zed/VS Code/OpenCode）读本协议 → 写标准 JSONL → 看板全自动流转。
>
> **设计原则**:
> 1. **协议级别 = 可独立读懂**: 不需要查代码就能写出合格 task
> 2. **不耦合**: IDE 不需要装 plugin，agent 不需要改行为
> 3. **单节点**: CCC 保持单节点任务编排内核，不做多用户/权限
> 4. **向后兼容**: 缺失字段补默认；新字段写入老 task 不破坏读取

---

## 0. 版本兼容矩阵

| CCC 版本 | 接受 schema_version | 向后兼容要求 |
|----------|---------------------|-------------|
| ≥ 0.28.0 | 缺失 / "1.0" / "1.1" / "1.2" | v1.0 / v1.1 任务仍能识别，在 CE 解决 |
| < 0.28.0 | 仅 "1.0"（无 color_* 字段） | 不识别 color_* 字段+ phases_schema 校验 → 静默忽略（兼容模式） |

**严格模式（strict=True）**：仅 CCC 内部 validate_task_jsonl 使用。IDE 端写 task 不要求严格模式。

---

## 1. Task 文件格式

每任务一个 `.jsonl` 文件：

```
<workspace>/.ccc/board/<column>/<task_id>.jsonl
```

7 列（column）：
- `backlog` — 起点（IDE/QXO/外部工具唯一允许直接写入的列）
- `planned` — product 拆分后
- `in_progress` — dev 执行中
- `testing` — reviewer/tester 验收中
- `verified` — 验收通过，待 kb 归档
- `released` — 已发布
- `abnormal` — quarantine/异常

---

## 2. 字段定义（11 条）

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `id` | string | ✅ | — | kebab-case，仅 `[a-zA-Z0-9_-]`，sanitize 后非空非 "invalid" |
| `title` | string | ✅ | — | 非空，≤ 500 字符 |
| `description` | string | ❌ | `""` | 任务描述，≤ 10000 字符 |
| `status` | string | ✅ | — | 取值 ∈ {backlog, planned, in_progress, testing, verified, released, abnormal} |
| `created_at` | string (ISO 8601) | ✅ | — | 格式 `YYYY-MM-DDTHH:MM:SS+08:00`（北京时间） |
| `updated_at` | string (ISO 8601) | ✅ | — | 同上（北京时间） |
| `assignee` | string\|null | ❌ | `null` | 负责人 |
| `tags` | string[] | ❌ | `[]` | 标签数组，元素为字符串 |
| `note` | string\|null | ❌ | `null` | 备注 |
| `schema_version` | string | ❌ | `"1.0"` | 协议版本 |
| `color_group` | string (A-Z 单字符) | ❌ | `null` | 颜色分组（详见 §5） |
| `color_depth` | int (≥ 0) | ❌ | `0` | 颜色深度（详见 §5） |
| `complexity` | string | ❌ | `"medium"` | 任务复杂度 v0.28.1: `small`\|`medium`\|`large`（详见 §12） |

**未知字段**：strict=False 时忽略不报错；strict=True 时拒绝。

---

## 3. Agent ↔ 列映射表（协议核心契约）

> **不可违反**：每种 agent 只从一个列取任务，写入另一个（或相同）列。

| Agent | 读列 | 写列 | 附加产物 | 备注 |
|-------|------|------|----------|------|
| **IDE/QXO/外部工具** | (无) | `backlog` | — | **唯一允许直接写 backlog 的来源** |
| **product** | `backlog` | `planned` | `.ccc/plans/<id>.plan.md` + `.ccc/phases/<id>.phases.json` | 拆任务 + 写 plan + phases |
| **dev** | `planned` (或 `abnormal`) | `in_progress` | `.ccc/reports/<id>.report.md` | 执行 phase 1..N；R-04 advisory lock |
| **reviewer** | `in_progress` | `testing` / `abnormal` | `.ccc/reports/<id>.review.md` | R-04 + R-12 fallback quarantine |
| **tester** | `testing` | `verified` / `abnormal` | — | pytest + plan 验收 |
| **kb** | `verified` | `released` | CHANGELOG + git tag | 归档沉淀 |
| **regress** | `released` | `backlog` (回归) | — | 发现 bug 移回 backlog |
| **ops** | 全列读 | 仅清理维护 | — | quarantine / cleanup |
| **audit** | 跨 workspace 读 | `backlog` (跨 ws 投递) | — | v0.22.1 已有 |

---

## 4. 校验规则

所有 task 在写入看板前必须通过 `validate_task_jsonl(data)` 检查。返回 `(is_valid, errors)` 元组。

| # | 字段 | 规则 |
|---|------|------|
| 1 | `id` | 必填；sanitize 后非 "invalid"；仅 `[a-zA-Z0-9_-]` |
| 2 | `title` | 必填；非空字符串；≤ 500 字符 |
| 3 | `status` | 必填；∈ COLUMNS |
| 4 | `created_at` / `updated_at` | 必填；ISO 8601 格式（推荐北京时间 `+08:00`，Validator 接受 `Z` 向后兼容） |
| 5 | `description` | 类型=str（可空字符串） |
| 6 | `assignee` | 类型=str\|null |
| 7 | `tags` | 类型=list[str] |
| 8 | `note` | 类型=str\|null |
| 9 | `schema_version` | 缺省补 `"1.0"`；仅校验是字符串 |
| 10 | `color_group` | 缺省 `null`；存在时 ∈ [A-Z] 单字符 |
| 11 | `color_depth` | 缺省 `0`；存在时 ≥ 0 整数 |
| 12 | `complexity` | 缺省 `"medium"`；存在时 ∈ {small, medium, large} |

**容错**（strict=False 默认）：
- 缺失字段 → 补默认（不报错）
- 未知字段 → 忽略（不报错）
- 类型不符 → 记 errors（第一条为人类可读摘要）

**严格模式**（strict=True，仅 IDE 端强校验用）：
- 不接受未知字段
- 不接受类型不符

---

## 5. 颜色分层协议

> **作用**：同发布批次的 task 自动同色，看板上一眼可识别任务所属。

| 字段 | 取值 | 含义 |
|------|------|------|
| `color_group` | A-Z 单字符 | 标识发布批次（A=批次1, B=批次2, ...） |
| `color_depth` | ≥ 0 整数 | 0=父任务深色，1=子任务浅色，以此类推 |

**赋值规则**（product 拆解时自动）：
- 父任务（顶层）：`color_group = assign_color_group(parent)`，depth=0
- 子任务（拆出的 phase）：`color_group = parent.color_group`，depth=parent.color_depth + 1

**HSL 计算公式**：
```
hue = (ord(group) - ord("A")) * 360 / 26
lightness = max(20%, 55% - depth * 15%)
```

**UI 渲染**：每个 task 卡片左边框色 = `hsl(hue, 55%, lightness)`；无 color_group 字段回退默认色。

**视觉示例**：
```
大任务 A (color_group: "A", color_depth: 0) → hsl(0, 55%, 55%) 橙红深
  ├── A1 (color_group: "A", color_depth: 1) → hsl(0, 55%, 40%) 橙红更深
  ├── A2 (color_group: "A", color_depth: 1) → hsl(0, 55%, 40%) 橙红更深
大任务 B (color_group: "B", color_depth: 0) → hsl(13.8, 55%, 55%) 橙黄深
  ├── B1 (color_group: "B", color_depth: 1) → ...
```

---

## 6. 列迁移规则

```
backlog → planned → in_progress → testing → verified → released
                                                       ↓
                                          abnormal ←─┘ (任意列可入 abnormal)
```

完整白名单（`_board_store.py:37-55`）：

```python
COLUMN_TRANSITIONS = {
    "planned":     ["backlog"],
    "in_progress": ["planned"],
    "testing":     ["in_progress", "abnormal"],  # abnormal 重投
    "verified":    ["testing"],
    "released":    ["verified"],
    "backlog":     ["released", "in_progress", "abnormal", "planned"],  # 回归重拆
    "abnormal":    ["in_progress", "testing", "verified", "released"],
}
```

**禁止迁移**（无白名单记录）：
- `backlog → in_progress`（跳过 planned）
- `planned → testing`（跳过 in_progress）
- `in_progress → released`（跳过 testing+verified）

---

## 7. 事件格式

每列迁移触发事件，写入 `.ccc/board/events/<task_id>.events.jsonl`：

```json
{"event": "move", "task_id": "fix-login-500", "from": "none", "to": "backlog", "timestamp": "2026-07-11T14:00:00Z"}
```

事件类型：

| type | 触发 | 字段 |
|------|------|------|
| `move` | 列迁移 | task_id, from, to, timestamp |
| `assign` | product 拆解 | task_id, parent, depth, timestamp |
| `quarantine` | reviewer fallback / 异常 | task_id, reason, level, timestamp |

---

## 8. 结构化 Error Response Schema

IDE 写 task 失败时（POST `/api/tasks`）返回：

```json
{
  "ok": false,
  "error": "validation_failed",
  "message": "task 校验未通过",
  "details": [
    {"field": "id", "rule": "kebab-case", "got": "task 001"},
    {"field": "status", "rule": "in COLUMNS", "got": "todo"}
  ],
  "fix_hint": "id 仅允许 a-zA-Z0-9_-；status 必须为 backlog/planned/.../abnormal"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `ok` | ✅ | 固定 `false`（错误时） |
| `error` | ✅ | 错误代码：`validation_failed` / `unauthorized` / `internal_error` |
| `message` | ✅ | 人类可读一句话 |
| `details` | ❌ | 错误详情列表（每项含 field/rule/got） |
| `fix_hint` | ❌ | 修复建议（≤ 200 字符） |

成功响应（`ok: true`）：

```json
{"ok": true, "task_id": "fix-login-500"}
```

---

## 9. 多语言示例

### Python（推荐）

```python
import json
from pathlib import Path

task = {
    "id": "fix-login-500",
    "title": "修复登录 500 错误",
    "description": "OAuth callback 返回 500，需修复后端 session 校验",
    "status": "backlog",
    "created_at": "2026-07-11T14:00:00Z",
    "updated_at": "2026-07-11T14:00:00Z",
    "assignee": None,
    "tags": ["bug", "auth"],
    "note": None,
    "schema_version": "1.0",
    "color_group": "A",
    "color_depth": 0,
}

# 写入 backlog
task_file = Path(".ccc/board/backlog") / f"{task['id']}.jsonl"
task_file.parent.mkdir(parents=True, exist_ok=True)
task_file.write_text(json.dumps(task, ensure_ascii=False) + "\n")
```

### Bash（一行写）

```bash
mkdir -p .ccc/board/backlog
cat > .ccc/board/backlog/fix-login-500.jsonl <<'EOF'
{"id": "fix-login-500", "title": "Fix login 500", "status": "backlog", "created_at": "2026-07-11T14:00:00Z", "updated_at": "2026-07-11T14:00:00Z"}
EOF
```

### Node.js

```js
const fs = require("fs");
const task = {
  id: "fix-login-500",
  title: "Fix login 500",
  status: "backlog",
  created_at: "2026-07-11T14:00:00Z",
  updated_at: "2026-07-11T14:00:00Z",
  schema_version: "1.0",
  color_group: "A",
  color_depth: 0,
};
fs.writeFileSync(".ccc/board/backlog/" + task.id + ".jsonl", JSON.stringify(task) + "\n");
```

### CLI（`ccc-board.py create`）

```bash
python3 scripts/ccc-board.py create \
  --id fix-login-500 \
  --title "Fix login 500" \
  --column backlog \
  --tags bug,auth
```

---

## 10. 向前兼容

- **缺失字段**：reader 必须补默认（不要抛 KeyError）
- **未知字段**：reader 静默忽略（不要抛 AttributeError）
- **版本协商**：schema_version 仅校验是字符串，不校验具体值
- **老 task（v0.25.1 无 color_*）**：UI 渲染回退默认色，不报错
- **新增字段（v0.27+）**：通过 §0 兼容矩阵声明；老 reader 忽略

---

## 11. 与 QXO 互通示例

QXO（或其他工具）按本协议写 task 后，CCC Engine 自动拾取：

1. QXO 写 `.ccc/board/backlog/<id>.jsonl`
2. CCC Engine 每 5s tick 扫 backlog → 调 product_role
3. product 拆分 → 写 plan + phases + planned
4. dev/reviewer/tester/kb 串行跑完
5. kb 写 CHANGELOG + git tag → released

**反之**：CCC 产出的 task 可被 QXO 通过同一目录读取（实时同步，无需 API）。

---

## 12. 错误排查 checklist

| 现象 | 排查 |
|------|------|
| IDE 写 task 无效 | 检查 status 是否在 7 列白名单 |
| 看板显示 task 但无颜色 | 检查 color_group 是否 ∈ A-Z |
| 列迁移失败 | 检查 from/to 是否在 COLUMN_TRANSITIONS |
| 老 task 加载报错 | 检查 created_at/updated_at 格式 |
| 颜色冲突 | assign_color_group 自动轮转，正常现象 |

---

---

## 12. 复杂度分流协议（v0.28.1）

> **目的**：按 task 规模决定走完整 7 角色 pipeline 还是简化路径，减少不必要的 reviewer/tester 轮次。

| 复杂度 | 含义 | 触发条件 | 角色路径 |
|--------|------|---------|---------|
| `small` | 小改 | plan_weight ≤ 50 | dev → released（跳过 reviewer/tester） |
| `medium` | 常规 | 50 < plan_weight ≤ 200 | 完整 7 角色（默认） |
| `large` | 大改 | plan_weight > 200 | 完整 7 角色 + 强制分批 |

**plan_weight 计算公式**（product_role 自动计算）：
```
plan_weight = lines(plan) + files_mentioned × 20 + sections × 10
```

**Engine 行为**：
- `small`：dev 完成后直接 kb 归档，不调 reviewer/tester
- `medium`：完整 pipeline（与 v0.28.0 一致）
- `large`：完整 pipeline + dev prompt 注入 `size_hint` 强制分批

**变更历史**:
- v1.2 (2026-07-12): 新增 §12 复杂度分流协议
- v1.0 (2026-07-11): 初版，CCC 0.26.0 落地
- v0.19 旧版: 仅 10 字段 + 1 示例，无协议契约
