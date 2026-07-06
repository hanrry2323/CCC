# CCC USAGE — 3 类用户指南

> CCC 是 **Connect–Claude Code** SKILL 资产，本文按 3 类使用者分别给出指南：
> 1. **CCC user**（用 CCC SKILL 跑任务）
> 2. **Skill consumer**（在另一个项目用 CCC SKILL）
> 3. **Agent maintainer**（改 CCC 工程的代码）

---

## 1. CCC User — 跑 CCC 任务

### 1.1 适用场景

- 你有 1 个 ≥2 阶段的任务想自动化（plan / execute / verify）
- 你想强制三角色纪律，避免自证幻象
- 你想保留完整 red lines 守门 + 4 文件契约

### 1.2 30 秒上手

```bash
# 在你项目根（已有 .ccc/ 目录）
echo "plan task X: implement feature Y" > .ccc/plans/task-x.plan.md

# 启动 Planner（Mavis / Claude Code / 自选 IDE）
# 加载 ~/.claude/skills/ccc-protocol（或 ~/program/CCC/SKILL.md）

# Planner 读 profile.md → 写 plans + phases.json
# Executor 自动 commit（ccc-exec-commit.sh 兜底）
# Verifier 独立 session → 写 verdicts/<task>.verdict.md（≥50 行红线 11）
```

### 1.3 关键命令

```bash
# Status（看任务进度）
bash ~/program/CCC/scripts/ccc status

# Live 模式（5 秒刷新）
bash ~/program/CCC/scripts/ccc status -w 5

# 搜索 .ccc 工件
python3 ~/program/CCC/scripts/ccc-search.py "lesson 28"

# 触发知识飞轮（v0.7）
python3 ~/program/CCC/scripts/flywheel-scan.py

# Cluster 健康度（v1.0）
bash ~/program/CCC/tools/cluster-doctor.sh

# 自动 commit（兜底）
bash ~/program/CCC/scripts/ccc-exec-commit.sh <workspace> <task>
```

### 1.4 例：完整 abc 项目

```bash
cd ~/program/abc

# 1. Planner 阶段（Mavis 内）
echo "see plans/v1.0-automation.plan.md" >> .ccc/plans/abc-v1.0.plan.md
# 写 phases.json 标记 pending

# 2. Executor 阶段（claude -p 独立跑）
claude -p "按 .ccc/plans/abc-v1.0.plan.md 执行" \
    --permission-mode bypassPermissions \
    --max-budget-usd 30

# 3. Verifier 阶段（独立 session 写 verdict）
claude -p "作为独立 verifier 验证 abc v1.0 (≥3 probes + ≥50 行 verdict)"
```

### 1.5 红线 必读

- **红线 11** — Verifier 必写 verdict 文件（≥50 行），不能口头 PASS
- **红线 18** — Capability match 默认开启 (Test verifies)
- **红线 20** — bash 跨设备脚本必须 v3 portability（avoid `bash -c '\$VAR'`）

---

## 2. Skill Consumer — 在另一个项目用 CCC

### 2.1 适用场景

- 你有 1 个现有 Python/TS/Go 项目，想接 CCC 三角色纪律
- 你不想自己写 SKILL frontmatter 兼容性
- 你想直接利用现成的 4 文件契约 + red lines 守门

### 2.2 Install CCC skill 到你的 IDE

#### Claude Code 用户

```bash
# symlink (CCC 改动 IDE 立即可见)
ln -sfn ~/program/CCC ~/.claude/skills/ccc-protocol
# 验证
ls -la ~/.claude/skills/ccc-protocol/SKILL.md
```

#### Cursor / 其他编辑器

```bash
# Cursor 共用 Claude Code 路径
ls ~/.claude/skills/ccc-protocol/SKILL.md

# 或者手工放 Cursor 自己的 skills/
ln -sfn ~/program/CCC ~/.cursor/skills/ccc-protocol
```

#### 验证安装

```bash
bash ~/program/CCC/scripts/install-ccc-as-skill.sh --check
# 期望输出: 6 项 OK + SKILL.md frontmatter 检查通过
```

### 2.3 初始化 .ccc/ 到你的项目

```bash
# 在你的项目根
python3 ~/program/CCC/scripts/ccc-init.py /path/to/your-project
# → 写 .ccc/profile.md + 推荐 subdirs

# 手动 .gitignore（如果没自动配）
cat >> .gitignore <<'EOF'

# CCC
.ccc/abnormal-reports/
!.ccc/plans/
!.ccc/phases/
!.ccc/reports/
EOF
```

### 2.4 加载 CCC skill

打开你的 IDE（Claude Code / Cursor / Zed），输入：

```
按 ccc 流程跑 X 任务
```

→ IDE 加载 SKILL.md → 注入 4 文件契约 + 11 + 2 红线 + 30 lessons → 进入 Planner 角色。

### 2.5 自己项目的 dispatch（v1.0 PoC）

```bash
# 启动 cluster-bus
python3 ~/program/CCC/scripts/cluster-bus.py &

# 注册本机为节点
curl -X POST localhost:9100/api/node/register \
  -d '{"node_id":"dev","host":"127.0.0.1","port":8888,"capabilities":["shell","claude-p","git"]}'

# Dispatch 任务（人工 review triple）
echo "yes" | python3 ~/program/CCC/scripts/ccc-dispatch.py \
  --plan your-project/.ccc/plans/task.plan.md \
  --workspace your-project
# → 输出 [node_id, model_tier, est_cost_seconds] + 写 dispatch artifact
```

---

## 3. Agent Maintainer — 改 CCC 工程

### 3.1 适用场景

- 你要修 bug / 加 feature / 重构 CCC 脚本本身
- 你要扩 red lines / 改 SKILL.md / 加新 references/

### 3.2 开发流程

```
1. 开 task (issue / backlog entry / 老板说)
   ↓
2. 写 plan.md  (含 范围 / 改动 N / commit 计划 / 验收清单)
   ↓
3. 写 phases.json (JSON Lines 格式, 每 phase 1 行)
   ↓
4. 写 code (含验证命令)
   ↓
5. 跑 test (red lines 自动守门)
   ↓
6. git commit (单 phase 单 commit, message 含 verification 段)
   ↓
7. 写 report.md (≥100 行, 写实际 stdout 不是总结)
```

### 3.3 关键 dev 命令

```bash
# Syntax check (每个 .sh 必跑)
bash -n scripts/ccc-exec-commit.sh

# Python syntax
python3 -m py_compile scripts/cluster-bus.py

# Run all tests
python3 -m pytest tests/scripts/ tests/cluster/ -v

# Cluster doctor 检查健康
bash tools/cluster-doctor.sh

# Pre-commit hooks (CI 部分)
pre-commit run --all-files
```

### 3.4 关键红线和教训

| 红线 | 含义 | 自动化 |
|------|------|--------|
| 4 | 单 phase 单 commit | `scripts/ccc-exec-commit.sh` 强制 |
| 5 | phases.json 必写全 JSON Lines | `tests/scripts/test_*` 检查 |
| 11 | Verifier 必写 verdict 文件 | 单测检查 verdict 长度 ≥50 行 |
| 18 | capability match 默认开启 | `tests/cluster/test-capability-required.py` |
| 20 | bash v3 portability | `pre-commit` 检查 |

| Lesson | 沉淀 |
|--------|------|
| 27 | `claude -p` 是 print 模式，prompt 必须走 stdin |
| 28 | Verifier 必须有产物（口头 PASS ≠ PASS） |
| 29 | bash 单引号嵌套不展开变量（v3 portability） |
| 30 | 独立 verifier session 找真 bug |

### 3.5 改 CCC 后的发布流程

```bash
# 1. 跑完所有测试
python3 -m pytest tests/scripts/ tests/cluster/ -v

# 2. Cluster doctor PASS
bash tools/cluster-doctor.sh

# 3. 更新 CHANGELOG + DESIGN-VALIDATION + 版本号 (VERSION)
# 4. Commit + Tag
git tag -a v1.X.Y -m "..."
git push origin v1.X.Y

# 5. 给老板写一张交付汇报
```

---

## 4. 常见问题速查

- **SKILL 不加载？** → `references/troubleshooting.md` §1
- **心跳不响应？** → `references/troubleshooting.md` §2
- **Verdict 写入失败？** → `references/troubleshooting.md` §4
- **Dispatcher 无候选？** → `references/troubleshooting.md` §5
- **跨设备 sync 失败？** → `references/troubleshooting.md` §3

---

## 5. 相关文档

- [README.md](../README.md) — 项目 30 秒介绍
- [CLAUDE.md](../CLAUDE.md) — 框架总纲
- [DESIGN-VALIDATION.md](../DESIGN-VALIDATION.md) — 决策永久证据链
- [references/red-lines.md](../references/red-lines.md) — 13 红线
- [docs/GLOSSARY.md](GLOSSARY.md) — 30 术语 (T7)
- [docs/CONTRIBUTING.md](CONTRIBUTING.md) — dev workflow (T6)
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) — 5 类 fix (T8)
