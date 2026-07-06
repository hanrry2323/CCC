你是 CCC Executor(独立 `claude -p` session)。

# 任务: readme-zcode-update

修改 `/Users/apple/program/CCC/README.md`,新增 ZCode Adapter 段。

## 启动顺序(必读)

1. 读 `/Users/apple/program/CCC/.ccc/plans/readme-zcode-update.plan.md`
2. 读 `/Users/apple/program/CCC/README.md` 现有内容(避免破坏)
3. 读 `/Users/apple/program/CCC/references/adapters/runtime-zcode.md` 提取 ZCode adapter 关键能力

## 工作内容

### Step 1: 编辑 README.md

在 README.md **末尾**(最后一个 ## 段之后)新增以下段(精确内容,可微调措辞):

```markdown
## ZCode Adapter (v1.2.1, 2026-07-06)

ZCode 桌面应用底层是 Claude Code CLI 的 GLM-branded 包装。本仓库提供
CCC 在 ZCode 环境下的完整 adapter:

- `scripts/ccc-zcode-bridge.sh` — spawn 独立 Executor/Verifier session
  (claude -p + BigModel/GLM provider + UUID session-id)
- `scripts/ccc-znode-register.py` — 把当前机器注册到 cluster-bus,
  capability = `[zcode, glm-5, claude-p, shell, git, python]`
- `scripts/ccc-zcode-orchestrate.sh` — 6 步端到端编排器
  (precheck → register → executor → commit → watchdog → verifier → finish)

### 一键跑

```bash
ccc run <workspace> <task-id>
```

### 手动分步

```bash
bash scripts/ccc-zcode-bridge.sh <ws> <task> executor
ccc commit <ws> <task>
bash scripts/ccc-zcode-bridge.sh <ws> <task> verifier
bash scripts/ccc-finish.sh <ws> <task>
```

详见 `references/adapters/runtime-zcode.md` v1.2.1。

---

**测试覆盖**: 21/21 smoke tests PASS,含本地 HTTP mock cluster-bus 验证。
```

### Step 2: 写 Executor 报告 `.ccc/reports/readme-zcode-update.report.md`

包含:
- 改动清单: `README.md` 新增 1 段(行号区间)
- 自验证: `grep -n "ZCode Adapter" README.md` 输出
- 红线遵守: 不 commit / 不写 verdict
- 末尾: `> VERDICT: .ccc/verdicts/readme-zcode-update.verdict.md`

### Step 3: 不 commit(留给 ccc-exec-commit.sh)

## 完成定义

1. README.md 真含新增段(可用 grep 验证)
2. report.md 真文件存在 + 含 `> VERDICT:` 引用
3. 不写 verdict.md(Verifier 独立 session 写)
4. 不 commit

退出前 echo:
```
EXECUTOR_RESULT: success
README_LINES_ADDED: <count>
REPORT_FILE: /Users/apple/program/CCC/.ccc/reports/readme-zcode-update.report.md
```