# DEV-PACKET: dod-hygiene-scope-guard

> **大包长任务**：一次会话做完下方全部 Phase，只回报一次。  
> 合入权威 = **Cursor**。做完只提交到指定分支，**不要 push main**。  
> 先：`git checkout main && git pull --ff-only`，再开分支。  
> 发给**个人 Claude Code CLI**（Relay `flash` 即可；非 Desktop Agent；非 Cursor Cloud 主路径）。  
> 主题：DoD / hygiene auto-commit **禁止**把非 plan scope（尤其 `.ccc/**`）扫进业务仓。**不碰** relay 密钥、Ops UI、authority。

## 1. 总目标（用户可见）

金路径 / 任意 work 卡的 DoD auto-commit 只应包含 **plan/phases scope 白名单文件**（及明确允许的测试产物）。  
禁止再出现 `… auto-commit by CCC DoD gate hygiene` 把 `.ccc/board`、`quarantines`、`stats`、`state.md` 等板面脏文件打进业务 `git log`。

对应实锤：`ccc-demo` commit `7cab29f` / `15a09bf`（见 [`docs/briefs/2026-07-27-golden-path-evidence.md`](../briefs/2026-07-27-golden-path-evidence.md) v4）。OpenCode 自 commit `c250b6f` 已干净——问题在 **Engine DoD hygiene 路径**。

## 2. 分支与提交

- 分支：`draft/dod-hygiene-scope-guard`
- **可以多个 commit**（按 Phase）
- 建议 messages：
  - `fix(dod): never auto-commit outside plan scope`
  - `fix(dod): refuse .ccc board dirt in hygiene commits`
  - `test: dod hygiene scope guard`
- 禁止 `git push origin main`；可不 push，或 `git push -u origin draft/dod-hygiene-scope-guard`
- **禁止** `git add -A` / `git add .`；每次只 add 本 Phase 白名单

## 3. 白名单（整包允许）

- `scripts/_task_commit.py`（或实际承载 DoD auto-commit / hygiene 的模块——先 `rg` 定位 `DoD gate hygiene` / `auto-committed`）
- `scripts/board/roles/dev.py`（若 salvage 调 DoD 的入口需收口）
- `scripts/_ccc_hygiene.py`（仅当 hygiene 列表与 DoD add 路径纠缠时）
- `tests/scripts/test_task_commit.py`（**可新建**或扩现有）
- `tests/scripts/test_dod_hygiene_scope.py`（**可新建**）

## 4. 黑名单（碰了就停）

- `docs/product/loop-engineer-authority.md`
- `references/red-lines.md`
- `~/.ccc/**`、真密钥、plist、`relay/upstreams.json`
- `relay/**`（thinking 禁用已在主机配置落地，本包不改）
- `desktop/**`、Ops SPA
- 其它未列路径

## 5. 现状锚点（必读再改）

### 5.1 实锤坏 commit

在业务仓 `ccc-demo`：

```text
7cab29f  layer1-v4-… auto-commit by CCC DoD gate hygiene
  含：.ccc/board/* .ccc/quarantines/* .ccc/stats/* .ccc/state.md …
c250b6f  phase1: update golden path v4 …   ← OpenCode，仅 docs/reports/…
```

### 5.2 根因（已定位）

[`scripts/_task_commit.py`](../../scripts/_task_commit.py)：

- `_hygiene_allow_ccc_meta(...)` 为真时，把 **全部** `.ccc/**` 脏路径当作 `product` 并 `git add`（约 283–293、373–386 行），message 带 `DoD gate hygiene`。  
- `_ccc_hygiene` / 标题含「文档戳记」/ tag `doc_only` 会把 **docs 戳记卡**误判成 hygiene → 金路径卡走错分支，板面脏进业务仓。  
- 非 hygiene 分支已有 scope 求交；**bug = hygiene 判定过宽 + hygiene 分支无条件收 `.ccc`**。

### 5.3 期望行为

1. **真** board_ops / pipeline=`ops|hygiene|board_ops` 才允许 DoD 提交 `.ccc` meta（仍应尽量收窄到本任务相关路径）。  
2. `doc_only` / `executor=opencode` / 普通业务卡：**禁止** hygiene 分支；只 commit plan scope。  
3. 标题「文档戳记」**不得**单独把卡送进 `_hygiene_allow_ccc_meta`（可与 skip-pytest 判定拆开）。  
4. 保留「acceptance 绿但 scope 脏 → recommit **仅 scope**」。

### 5.4 定位命令

```bash
rg -n "DoD gate hygiene|_hygiene_allow_ccc_meta|auto-commit by CCC DoD" scripts/ tests/
```

## 6. 实现步骤（Phase）

### Phase A — 收口 hygiene 判定与 add 列表

1. 收窄 `_hygiene_allow_ccc_meta`（或调用方）：`doc_only` / 无 ops pipeline → **False**。  
2. hygiene 为真时：仍禁止无差别 `all .ccc dirty`；至少排除无关 `board/backlog|quarantines` 大扫荡，或改为只 add 本 `task_id` 相关 meta。  
3. 金路径 docs 戳记必须走 **scope 分支**（与 OpenCode `c250b6f` 同形）。

### Phase B — 单测

用临时 git 仓（现有 fixture 模式）：

1. scope=`docs/reports/stamp.md` 已改 + `.ccc/board/x.jsonl` 脏 → auto-commit **只含** stamp。  
2. 仅 `.ccc` 脏、scope 净 → **不**产生 hygiene commit（或 ok=false / skipped）。  
3. 回归：scope 多文件仍可一并提交。

### Phase C — 自检

```bash
python -m py_compile scripts/_task_commit.py   # 按实际改动文件
ruff check <白名单文件>
pytest tests/scripts/test_task_commit.py tests/scripts/test_dod_hygiene_scope.py -q --tb=short
# 若文件名不同，以你新建的为准，写进回报
```

## 7. 验收（必须跑）

上表命令全绿；回报里贴 **失败用例名若有** 与最终 pass 计数。

## 8. 做完回报（固定格式）

```
BRANCH: draft/dod-hygiene-scope-guard
FILES:
- …
TESTS:
- … → pass/fail
RESIDUAL:
- …
```

## 9. Cursor 合入后（本包外）

1. 2017 `git pull` + `launchctl kickstart -k gui/$(id -u)/com.ccc.engine`  
2. 可选：再投一笔 docs 戳记，确认 `git show` 无 `.ccc/` 路径。
