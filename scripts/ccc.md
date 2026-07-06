# `ccc` CLI dispatcher

> 统一入口，扫描并展示 CCC 任务状态。

## 用途

快速查看所有 CCC task 的 phases 进度 + git head。

## 用法

```bash
bash scripts/ccc                          # status 显示最近 3 个 task
bash scripts/ccc status -w 5             # 5 秒刷新（live mode）
bash scripts/ccc search "v0.3"           # 搜索 .ccc 工件含 v0.3 的
bash scripts/ccc init <workspace>        # 初始化项目 .ccc/ 目录
bash scripts/ccc commit <workspace> <task>  # 自动 commit working tree
bash scripts/cccq                        # ccc status 简写（alias）
```

## 子命令

| 子命令 | 作用 |
|--------|------|
| `status [-w N]` | 列出本项目 .ccc/phases/ + 显示 git head |
| `search <pattern>` | grep 所有 .ccc/{plans,phases,reports,verdicts}/ |
| `init <workspace>` | mkdir .ccc/{plans,phases,reports,verdicts,abnormal-reports} + profile.md |
| `commit <workspace> <task>` | 读 phases.json → git add scope file → commit |

## Exit codes

- 0: success
- 1: 参数错误

## Example

```bash
# 查看当前 task 进度 + 看哪些 commit 缺失
bash scripts/ccc status

# 5 秒刷新模式用于 long-running task
bash scripts/ccc status -w 5

# 搜索历史中所有提到 "lesson 28" 的 plan
bash scripts/ccc search "lesson 28"
```

## 关联

- `references/execution-protocol.md` — 在 CCC 流程中的位置
- `docs/agent-commands.md` — older duplicate（v0.3 时期）
