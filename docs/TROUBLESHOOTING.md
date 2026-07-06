# CCC TROUBLESHOOTING — 5 类常见问题 + Fix

> 5 类最常见 CCC 问题 + 症状 / 根因 / 修复 / 复测命令。
> 与 `docs/USAGE.md` §4 互链。

---

## §1 SKILL 不加载（Trae / Cursor / Claude Code）

### 症状
- 在 IDE 内说"按 ccc 流程跑 X"，agent 不回应
- 提示找不到 `SKILL.md` 或 frontmatter invalid

### 根因
1. SKILL 没装到 IDE skills 目录（`~/.claude/skills/ccc-protocol` 不存在）
2. SKILL.md frontmatter 缺 `name: ccc-protocol` 或 `description:` 字段
3. SKILL.md 文件权限 644 但父目录 700（Claude Code 不读）

### 修复

```bash
# 验证 install
bash ~/program/CCC/scripts/install-ccc-as-skill.sh --check
# → 6 项检查：OK / MISSING 提示

# 重装（force）
bash ~/program/CCC/scripts/install-ccc-as-skill.sh

# 验证 SKILL.md frontmatter
head -5 ~/.claude/skills/ccc-protocol/SKILL.md
# 期望:
# ---
# name: ccc-protocol
# description: |

# 修正权限
chmod 755 ~/.claude/skills/ccc-protocol
chmod 644 ~/.claude/skills/ccc-protocol/SKILL.md
```

### 复测

```bash
# 在 IDE 内新开对话说：
# "按 ccc 流程跑 hello test"
# → 期望：agent 回应 "读 SKILL.md，进入 Planner 角色" 之类
```

---

## §2 心跳不响应（cluster-bus）

### 症状
- `bash tools/cluster-doctor.sh` 显示 "FAIL: bus unreachable"
- `GET /api/node/list` 返回连接错误
- dispatcher ABORT exit=2 ("cluster-bus unreachable")

### 根因
1. bus 进程未启动 / 崩溃 / 被 kill
2. bus 绑定 `0.0.0.0:9100` 但本机防火墙挡
3. port 9100 被其他进程占
4. 检查点 (`/tmp/ccc-cluster-bus.json`) 损坏，bus 启动失败

### 修复

```bash
# 1. 验证进程
ps aux | grep cluster-bus | grep -v grep
# → 没进程 → bus 未启动或崩了

# 2. 验证端口
lsof -i :9100
# → 没输出 → 端口空闲
# → 有别进程 → 检查端口冲突

# 3. 看日志
tail -50 /tmp/cluster-bus.log
# → uvicorn error → 检查 uvicorn 是否装

# 4. 重启 bus
pkill -f cluster-bus.py
rm /tmp/ccc-cluster-bus.json  # 清损坏 checkpoint
python3 ~/program/CCC/scripts/cluster-bus.py > /tmp/cluster-bus.log 2>&1 &
sleep 2
curl http://127.0.0.1:9100/api/health
# → 期望: {"status":"ok",...}
```

### 复测

```bash
bash tools/cluster-doctor.sh
# → [1/5] bus liveness OK
```

---

## §3 跨设备 git sync 失败

### 症状
- `bash scripts/git-bundle-stream.sh push mac2017` 卡住 / connection refused
- Mac2017 端 fetch error: "not a git repository"
- "fatal: refusing to fetch into branch 'refs/heads/main' checked out at..."

### 根因
1. ssh key 未配置（首次连接需 exchange）
2. Mac2017 工作树有未 commit 改动 — fetch 拒绝更新 main
3. ssh username 错（Mac2017 是 `fan` 不是 `apple`）
4. Mac2017 cluster-bus 未启动 (跨设备 dispatch 用)

### 修复

```bash
# 1. ssh key check (用~/.ssh/config alias mac2017)
ssh mac2017 'ls /Users/fan/app/abc/.ccc/' 2>&1
# → "Permission denied" → 缺 ssh key

# 2. 加 ssh key
ssh-keyscan mac2017 >> ~/.ssh/known_hosts
ssh-copy-id fan@mac2017

# 3. Mac2017 端 cleanup dirty working tree
ssh mac2017 'cd ~/app/abc && git status --short | head'
# → 有 M / ?? → 决定: stash / commit / checkout --

# 4. Mac2017 端起 cluster-bus (派单用)
ssh mac2017 'python3 ~/app/ccc/scripts/cluster-bus.py > /tmp/cbus.log 2>&1 &'

# 5. 重试 sync
git bundle create /tmp/abc.bundle --all
base64 -i /tmp/abc.bundle | ssh mac2017 'base64 -d > /tmp/abc.bundle && cd ~/app/abc && git fetch --force /tmp/abc.bundle "refs/heads/main:main-bundle" && git checkout main-bundle && git reset --hard main-bundle'
```

### 复测

```bash
# 验证两边 commit 一致
git log --oneline | head -3
ssh mac2017 'cd ~/app/abc && git log --oneline | head -3'
# → 应该一致
```

---

## §4 Verdict 拒绝写入

### 症状
- Verifier session 完成但 `.ccc/verdicts/<task>.verdict.md` 不存在
- report.md 含 "VERDICT: PASS" 但文件 0 行
- pre-commit hook 报警：verdict file only X lines (need ≥ 50)

### 根因
1. Verifier prompt 缺 "将结论写到 .ccc/verdicts/<task>.verdict.md" 强制指令
2. Verifier 提前退出，写入中断
3. Verdict 文件写到错路径（如 `<workspace>/dispatches/<task>.verdict.md` 而非 `<workspace>/.ccc/verdicts/`）

### 修复

```bash
# 1. 验证 VERDICT 三选一 + 文件存在 + 行数
ls .ccc/verdicts/*.verdict.md
wc -l .ccc/verdicts/*.verdict.md
# → 必须 ≥ 50 行

# 2. 验证文件路径（红线 11）
cat .ccc/verdicts/<task>.verdict.md | head -30
# → 必须 VERDICT: PASS / FAIL / CONDITIONAL_PASS
# → 必须 ≥3 个 probe

# 3. 立即补救写一个最小 verdict（10 分钟 fix）
cat > .ccc/verdicts/<task>.verdict.md << 'EOF'
# Task Verdict — <task>

> Verifier: <session_id>
> Plan: .ccc/plans/<task>.plan.md
> Date: $(date -I)

## Probe 1: ...
## Probe 2: ...
## Probe 3: ...

VERDICT: PASS
EOF

# 4. 改 Verifier prompt 模板永久 fix
# templates/executor-prompt.template.md 加:
# "退出前必须 `wc -l < .ccc/verdicts/<task>.verdict.md` 验证 ≥50"
```

### 复测

```bash
bash scripts/v1.0-validation.sh   # cluster-bus / dispatch 全 PASS
# 期望: F4 verdict file ≥ 50 (作为 verifier file rule)
```

---

## §5 Dispatcher 无候选

### 症状
- `python3 scripts/ccc-dispatch.py` 输出 `candidates: NONE` + VERDICT: ABORT exit=2
- "recommendation: NO_NODE_HAS_REQUIRED_CAPABILITY"
- 计划提到 `claude-p` 但 cluster-bus 只注册了 `feiniu` (只有 `ollama-bge-m3`)

### 根因
1. 节点没注册到 cluster-bus
2. 注册了但缺 needed capability（mismatch）
3. cap 提取关键字 sniff 失败（plan 中相关词不在 keyword 表）

### 修复

```bash
# 1. 验证节点已注册 + capability 覆盖
curl http://127.0.0.1:9100/api/node/list
# → "capabilities": ["shell","claude-p","git"]

# 2. 加 missing capability
curl -X POST http://127.0.0.1:9100/api/node/register \
  -d '{"node_id":"new_node","host":"192.168.3.X","port":9101,"capabilities":["shell","claude-p","git","ollama-bge-m3"]}'

# 3. 验证 heartbeat (still alive)
curl -X POST http://127.0.0.1:9100/api/node/heartbeat \
  -d '{"node_id":"new_node","load":1.0}'

# 4. 看 dispatcher 的 capability 提取是否对应你 plan 中的 capability
python3 scripts/ccc-dispatch.py \
  --plan your-task.plan.md \
  --workspace your-workspace \
  --bus-url http://127.0.0.1:9100 <<< "yes"
# → "[dispatcher] needed_capability=..." 看是哪些 keyword
```

### 复测

```bash
echo "yes" | python3 scripts/ccc-dispatch.py \
  --plan your-task.plan.md \
  --workspace your-workspace
# → "[dispatcher] recommendation: new_node (score=0.X)"
```

---

## §6 重要诊断速查表

| 症状 | 一句话检查 | 修复 |
|------|-----------|------|
| Verifier 写 0 行 verdict | `ls .ccc/verdicts/ && wc -l` | 改 Verifier prompt，强制 ≥3 probes + ≥50 行（红线 11）|
| Dispatcher ABORT exit=2 | `curl /api/health` | 重启 bus，验证 `cluster-bus.py` 进程 |
| Trae 加载 SKILL 但无回应 | `cat ~/.claude/skills/ccc-protocol/SKILL.md \| head` | 检查 frontmatter + 修正权限 644 |
| Bash 脚本 sha-bang fail | `bash -n scripts/X.sh` | 替换 `bash -c '\$VAR'` 为 v3 模板 |
| Cross-device sync fail | `ssh mac2017 'cd ~/app/abc && git status --short'` | cleanup dirty + 重试 |
| pytest 跑挂 | `pytest tests/ -v`  | 检查 fixtures (tmp_path, monkeypatch.chdir 不影响 subprocess) |
| Cluster bus 启动后 1 分钟挂 | `cat /tmp/cluster-bus.log` | 检查 checkpoint loop error |
| Flywheel 写出意外路径 | `cat .ccc/abnormal-reports/*.md` | 验证 RED LINE 14 (只写 abnormal-reports) |

---

## §7 红线违反应急

如果发现 1 条 red line 被违反：

```bash
# 1. STOP 一切改动
git status --short  # 看 dirty
git diff --stat     # 看修改范围

# 2. 检查哪些 red line
grep -E "红线" docs/lessons.md | head -10  # 找对应 line

# 3. 写 abnormal report
cat > .ccc/abnormal-reports/<date>-red-line-violation.abnormal-report.md << 'EOF'
# Red Line Violation Report

- 日期: 2026-07-06
- Red line N: <which>
- commit: <hash>
- 上下文: <what happened>
- Root cause: <analysis>
- Fix: <remediation>

## Rollback steps
1. git revert <commit>
2. 修正 prompt + commit
EOF

# 4. 立即升级到老板 (如果 critical)
echo "RED LINE VIOLATION at commit <hash>" >> <老板 escalation file>
```

---

## 相关文件

- [USAGE.md §4](USAGE.md) — 常见问题速查
- [references/red-lines.md](../references/red-lines.md) — 13 红线
- [CONTRIBUTING.md](CONTRIBUTING.md) — review rules
- [docs/lessons.md](../docs/lessons.md) — 已沉淀教训
- [DESIGN-VALIDATION.md](../DESIGN-VALIDATION.md) — 决策永久证据链
