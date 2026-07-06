# `ccc-exec-commit.sh` — Executor commit 兜底

> 当 Executor 退出后 working tree 有改动但 commit 未触发生效时，Plannner 允许调用此脚本完成提交。

## 用途

按 `phases.json` 的 status 字段对每个 phase 自动 commit。规避 Executor 退出后 working tree 留存。

## 用法

```bash
bash scripts/ccc-exec-commit.sh <workspace> <task>              # 处理所有待 commit phase
bash scripts/ccc-exec-commit.sh <workspace> <task> --phase N    # 仅指定 phase
```

## Exit codes

- 0: 全部完成
- 1: 部分失败
- 2: 参数错误
- 3: 已 commit hash 的 phase 自动 skip

## 算法

1. 读 `<workspace>/.ccc/phases/<task>.phases.json`
2. 找 `commit == null && status == "done"` 的 phase
3. 对每个这样的 phase：
   - `git add <workspace_scope_files>` （来自 plan.md 的"只改文件"段）
   - `git commit -m "<phase_commit_message>"`
4. 写回 commit hash 到 phases.json

## Example

```bash
# 标准用法: 提交所有 done 状态的 phase
bash scripts/ccc-exec-commit.sh /Users/apple/program/abc abc-bootstrap

# 仅提交 phase 3
bash scripts/ccc-exec-commit.sh /Users/apple/program/abc abc-bootstrap --phase 3
```

## 关键约束（红线）

- **红线 4 (单 phase 单 commit)**: 每 phase 一个独立 commit
- **红线 8 (Planner 越界)**: Planner 调用此脚本**不算** C2 越界（合法 Fallback）
- **必须**先记入 abnormal-reports 的 "Fallback Commit" 段
- 连续 2 次 Fallback → 标记为需讨论

## 关联

- `references/red-lines.md` § 红线 8 Fallback
- `templates/phases.phases.json` 字段定义
- `.ccc/abnormal-reports/` 记录
