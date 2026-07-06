# `ccc-cost-report.sh` — Token / 成本估算

> 扫描 `.ccc/reports/*.md` / `.ccc/plans/*.md`，估算 token 数 + cost（按模型 tier 分摊）。

## 用途

帮助了解 CCC 任务产生的文档体积和估算 token 消耗。

## 用法

```bash
bash scripts/ccc-cost-report.sh <workspace>
bash scripts/ccc-cost-report.sh /Users/apple/program/abc
```

## Exit codes

- 0: success
- 1: workspace 不存在或无可读文件

## 输出示例

```
=== abc / CCC / xianyu Cost Summary ===
Total .md files scanned:    18
Total lines:                 4291
Total bytes:              152330
Total body chars (excl FM): 138204
Estimated tokens (÷4):      34551

By type:
  reports: 1234 lines, ~12.0KB, ~3084 tokens
  plans:   56 lines,  ~5.6KB,  ~1500 tokens
  phases:  123 lines, ~3.2KB, ~923 tokens

By project (estimate per ccc-domain):
  abc:     14.2KB, ~3550 tokens
  qx-obs:  11.8KB, ~2950 tokens
```

## 算法

1. 扫描 `<workspace>/.ccc/{reports,plans,phases,verdicts,abnormal-reports}/`
2. 解析 frontmatter（如果存在）
3. 估算 `body_chars = file_size - frontmatter_size`
4. `tokens ≈ body_chars / 4`
5. 按 .md 类型分组

## 关联

- `docs/lessons.md` § Lesson 27 (`claude -p` 真实语义)
- `references/red-lines.md` § 红线 14 (flywheel 候选需人工 review)
