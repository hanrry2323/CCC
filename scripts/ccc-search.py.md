# `ccc-search.py` — CCC 工件 grep 搜索

> 在 `<workspace>/.ccc/{plans,phases,reports,verdicts,abnormal-reports,dispatches}/` 全文 grep，支持语义化输出。

## 用途

快速定位哪个 task 提到 "chunk_id" / "lesson 28" / 某个 phase commit hash 等。

## 用法

```bash
python3 scripts/ccc-search.py <pattern> [--workspace <path>]
python3 scripts/ccc-search.py "v1.0 PoC"
python3 scripts/ccc-search.py "lesson 28" --workspace /Users/apple/program/abc
```

## Exit codes

- 0: 有匹配
- 1: 无匹配
- 2: 参数错误

## 输出格式

```
[HIT] .ccc/plans/v1.0-automation.plan.md
  line 12: ## include v1.0 PoC verification
  line 78: - **verification PoC**: real ABC cluster bus
...
[2 file(s) / 4 hit(s) / pattern: 'v1.0 PoC']
```

## Algorithm

1. walk `.ccc/{plans,phases,reports,verdicts,abnormal-reports,dispatches}/`
2. `grep -nE <pattern>` per file
3. 输出 `[HIT] file:line:context` 形式
4. 汇总 N file(s) / M hit(s)

## Example

```bash
# 全文找 lesson 28
python3 scripts/ccc-search.py "lesson 28"

# 在 abc 项目中搜
python3 scripts/ccc-search.py "mac2017" --workspace ~/program/abc

# 找所有提到 commit hash 8a19431 (v1.0 release commit)
python3 scripts/ccc-search.py "8a19431"
```

## 关联

- `references/red-lines.md` § 红线 10 (跨会话隐式记忆 → 显式 grep)
- `docs/lessons.md` § Lesson 30 (独立 verifier 工程价值)
