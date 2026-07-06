# `ccc-init.py` — 新项目 `.ccc/` 目录初始化

> 给一个新项目生成 `.ccc/` 工作目录骨架 + profile.md 模板 + gitignore 增量配置。

## 用途

让用户把 CCC 框架用于一个新项目时，只需一条命令建好工作目录。

## 用法

```bash
python3 scripts/ccc-init.py <workspace>
python3 scripts/ccc-init.py /Users/apple/program/my-new-project
```

## Exit codes

- 0: success
- 1: workspace 不存在或无 `.git`
- 2: `.ccc/` 已存在（避免覆盖）

## 创建的内容

```
<workspace>/.ccc/
├── profile.md              # Agent 启动顺序第一读
├── plans/                  # Planner 产物
├── phases/                 # JSONL 格式
├── reports/                # Executor 产物
├── verdicts/               # Verifier 产物（≥50 行红线 11）
├── abnormal-reports/       # 异常 / 红线违反
└── dispatches/             # ccc-dispatch.py 产物（v1.0）

<workspace>/.gitignore     # 增量追加 .ccc/abnormal-reports/ 豁免
```

## Profile.md 模板字段

```markdown
# <project> — Project Profile

- 项目路径
- Agent 别名
- 主要语言 (Python / TS / Go)
- 主要框架
- 数据库
- 部署方式
```

## Example

```bash
# 给 abc 项目 init
python3 scripts/ccc-init.py ~/program/abc
# → 已在 ~/.gitignore 加 .ccc/abnormal-reports/ 豁免
# → 写 .ccc/profile.md (项目元数据)

# 已 init 过再跑
python3 scripts/ccc-init.py ~/program/abc
# → exit 2 (skip, .ccc/ already exists)
```

## 关联

- `templates/profile.profile.md` — profile.md 模板
- `templates/.ccc-profile.md` — 项目级 .ccc 配置模板
- `references/file-contract.md` — 4 文件契约定义
