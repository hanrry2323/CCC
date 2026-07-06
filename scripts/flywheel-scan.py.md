# `flywheel-scan.py` — Knowledge Flywheel v0.7 扫描

> 扫描 `.ccc/reports/*.md` + `.ccc/verdicts/*.md`，提取失败模式并**仅生成**候选 lesson（**绝不**直接写入 `docs/lessons.md`）。

## 用途

V0.7 知识飞轮 pilot。沉淀工程教训但**红色 14 强制人工 gate** — `flywheel-scan.py` 只生成 `flywheel-candidate-<date>.md` 候选，**人不批准不能 merge** 到 authoritative location。

## 用法

```bash
python3 scripts/flywheel-scan.py
```

参数零 — 自动读当前目录的 `.ccc/`，扫所有 reports + verdicts。

## Exit codes

- 0: success（无论有无 findings 都 exit 0）
- 1: `.ccc/` 目录缺失

## Failure Patterns (6 类)

| 类别 | 触发正则 | 含义 |
|------|----------|------|
| infrastructure_or_runtime | `\b(error\|exception\|failed\|timeout\|crashed\|hanged)\b` | 基础设施或运行时 |
| circular_import | `\b(circular\s+import\|recursion\s+error)\b` | 循环导入 |
| permission | `\b(permission\s+denied\|access\s+denied\|forbidden)\b` | 权限 |
| severity_marker | `\b(p0\|critical\|severity)\b` | 严重度标记 |
| red_line_violation | `\b(red\s*line\s*\d+)\b` | 红线违反 |
| verification_gap | `\b(verifier\|verification\s+failed)\b` | 验收 gap |

## Dedup 算法

每个 finding 用 `sha256[:12] of (snippet + label)` 去重。

## 输出位置

`<workspace>/.ccc/abnormal-reports/flywheel-candidate-<YYYY-MM-DD>.md`

文件结构：
```markdown
# Flywheel Candidate Lesson — <date>

> ⚠️ This is a candidate — per Red Line 14 it must be
> human-reviewed before being merged into docs/lessons.md.

**Source files scanned**: N
**Unique findings**: M

## Findings
### infrastructure_or_runtime (in <file>)
- snippet: ...
```

## 红线 14 (Flywheel 候选)

> "禁止飞轮候选未经人工 review 直接写入"

- **Why**: AI 自动归纳失败模式容易"伪发现"——把一次性 / 边缘 case / 项目专属问题误判为通用模式
- **机制**: `flywheel-scan.py` 只生成 `.ccc/abnormal-reports/flywheel-candidate-<date>.md`，**绝不直接写** `docs/lessons.md`
- **触犯后果**: Warning — 减少人工 gate 必经入口；如果直接合入，1 周内回滚

## Example

```bash
python3 scripts/flywheel-scan.py
# [flywheel] wrote candidate: .ccc/abnormal-reports/flywheel-candidate-2026-07-06.md
# [flywheel] 4 unique findings (dedupe by sha256[:12])
# [flywheel] NEXT: human reviews .ccc/abnormal-reports/flywheel-candidate-2026-07-06.md
```

## 关联

- `references/red-lines.md` § 红线 14 (flywheel 候选必须人工 review)
- `docs/lessons.md` (人工 review 后才写入)
- `templates/phases.phases.json` (v0.7 → 1.0 阶段计划)
