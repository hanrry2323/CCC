# DEV-PACKET: 014-reviewer-bg-empty-verdict

> 复制本文件**全文**发给**个人 Claude Code CLI**（接 Relay `flash`；非 Desktop Agent）。  
> 合入权威 = Cursor。做完提交到指定分支，**不要 push main**。  
> **主题**：reviewer / `--bg` 空输出与超时必落 verdict（R2 · 接 013）。Ops UI **禁止**。

---

## 0. 长任务纪律（Claude Code 主力 · 多 Phase 一次做完）

你是本包的**主力开发**。按 Phase 顺序做完再回报；允许同一分支多 commit。  
每完成一个 Phase：跑该 Phase 验收命令；失败先自修，勿跳 Phase。  
**禁止**只写文档交差；**禁止**改权威/红线/密钥。  
工作节奏建议（自循环，不必等人）：

```text
loop:
  读本包当前 Phase → 改白名单 → py_compile + 相关 pytest →
  git add 白名单 → commit → 进入下一 Phase →
  全部 Phase 绿 → 按 §8 回报
```

若某 Phase 卡住 >2 次失败：在 `RESIDUAL` 写清根因与最小复现，**停**，不要扩大白名单。

---

## 1. 目标（用户可见）

013 已合入：quarantine 前 gates 会补 FAIL verdict。但仍有缺口：

1. `check_reviewer_async` 在 **空输出** / **进程提前退出** 时直接 `failed`，**不写** `.ccc/verdicts/<tid>.verdict.md`。  
2. `ccc-reviewer-bg.sh` 超时会写 `<tid>.reviewer.timeout`，但 Python 侧**几乎不读**该标记 → 可能一直 `running` 或误报「process exited before writing verdict」。  
3. 超时应落 **TIMEOUT** verdict（可重试）；空输出 / 无有效 JSON 应落 **FAIL**（fixable）——与短路径 `_fail_deterministic` / `_write_timeout_verdict` 精神对齐。

做完后：

- async 路径：空输出、超时、进程早退 **必有** verdict 文件再返回 failed/TIMEOUT。  
- bg wrapper 与 `check_reviewer_async` 对 `.timeout` / `.done` 口径一致。  
- 单测覆盖上述分支；**不改变** PASS 判定、不放宽 quarantine 阈值。

对应：PRODUCTION-DELIVERY-ROUNDS R2 · P-C/P-D 收尸诚实。

---

## 2. 分支与提交

- 基线：最新 `origin/main`（应含 013 · `6fba8d0` 或更新）
- 分支：`draft/014-reviewer-bg-empty-verdict`
- 提交风格：`fix(reviewer): …` / `fix(bg): …` / `test: …`（英文 why）
- **禁止** `git push origin main`；可 `git push -u origin draft/014-reviewer-bg-empty-verdict`
- **禁止** `git add -A` / `git add .`；只 add §3 白名单
- 同仓多 agent：**不要** `git add -A`；提交前 `git status` 确认无他人文件

```bash
git fetch origin main
git checkout -B draft/014-reviewer-bg-empty-verdict origin/main
```

---

## 3. 白名单（只许改这些）

### 代码 / 测

- `scripts/board/roles/reviewer.py`（`check_reviewer_async` 空/超时/早退写 verdict；清理 `.timeout`）
- `scripts/ccc-reviewer-bg.sh`（仅当需对齐标记约定；保持薄改）
- `scripts/engine/gates.py`（仅当 async 返回值与 TIMEOUT 门需要对齐的最小改动）
- `tests/scripts/test_reviewer_async_empty.py`（新建）
- `tests/scripts/test_reviewer_done_marker.py`（若需扩）
- `tests/scripts/test_reviewer_bg.sh`（若改 shell 标记）
- `tests/scripts/test_long_lived_session.py`（仅回归，勿大改）
- `scripts/tests/test_*.py`（仅当仓内双轨测目录需要镜像时）

### 文档（薄）

- `docs/dev-packets/README.md`（本包状态行）
- `docs/dev-packets/PRODUCTION-DELIVERY-ROUNDS.md`（R2 完成后标进行中→草稿工 done；**勿改 R3/R4 顺序**）
- `docs/briefs/2026-07-27-ccc-production-readiness.md`（程 B / 平台交付下加一行「014 …」——**仅一句**）

### 可选

- `tests/scripts/fixtures/**`（小 fixture，禁止业务仓）

---

## 4. 黑名单（碰了就停）

- `docs/product/loop-engineer-authority.md`
- `.cursor/rules/loop-engineer-consensus.mdc`
- `references/red-lines.md`
- `references/stress-kpi-scorecard.json`
- `VERSION` / `CHANGELOG.md` / `docs/releases/**`
- `relay/**`、`~/.ccc/**`、launchd/plist、密钥
- Desktop / Swift / Ops UI / SPA
- 业务仓 `/Users/fan/program/apps/**`
- 任意未列路径
- **禁止**抬 `MAX_CONCURRENT` / 改 invent / 改 reopen 阈值（那是 015）

---

## 5. 现状锚点

| 锚点 | 说明 |
|------|------|
| 空输出早退 | `reviewer.py` `check_reviewer_async` ≈771–776：`empty reviewer output` / `process exited…` **无写 verdict** |
| 超时 helper 已有 | `_write_timeout_verdict` ≈173；短路径 `_fail_deterministic` ≈204 |
| bg 超时标记 | `ccc-reviewer-bg.sh` ≈145–148：写 `.reviewer.timeout`，**不**写 done |
| 013 已做 | `gates.py` `_write_fail_verdict_before_quarantine`（quarantine 前补洞）；本包补 **async 入口** |
| 清理表 | `_cleanup_reviewer_markers` ≈872：当前**未**含 `.reviewer.timeout` |
| 版本 | `VERSION` = v0.63.0（本包不 bump） |

---

## 6. 实现步骤（Phase）

### Phase A — 红测锁定缺口

1. 新建 `tests/scripts/test_reviewer_async_empty.py`。  
2. 用 `tmp_path` + monkeypatch `get_workspace`：  
   - **A1** 有 `.done` + 空 `.out` → 调用后必须存在 FAIL verdict（含 `empty` / `empty_reviewer_output` 类 Reason），返回 `failed`。  
   - **A2** 无 `.done`、无存活 pid（或 pid 文件指向死进程）→ 必须写 FAIL verdict，返回 `failed`（禁止静默无文件）。  
   - **A3** 存在 `.reviewer.timeout`（可无 done）→ 必须写 **TIMEOUT** verdict，返回 `TIMEOUT`（或文档化与 engine 一致的 status 字符串）。  
3. 先让测红（证明缺口），再进入 Phase B。

### Phase B — 修 `check_reviewer_async`

1. 抽小 helper（可复用 `_write_timeout_verdict` / 对齐 `_fail_deterministic` 格式）：

```markdown
# <tid> Verdict

**Verdict:** FAIL   # 或 TIMEOUT

**Category:** fixable   # TIMEOUT 可省略 Category

**Reason:** empty_reviewer_output | process_exited_before_verdict | reviewer_bg_timeout
```

2. 空输出 / 早退 → FAIL；读到 `.timeout` → TIMEOUT（优先于「仍 running」若 max-wait 已过且 wrapper 已写 timeout）。  
3. `_cleanup_reviewer_markers` 增加 `.reviewer.timeout`（及若有 `.exitcode` 一并清，保持对称）。  
4. **不要**把 FALLBACK/TIMEOUT 写成 PASS；**不要**改短路径已绿逻辑。  
5. 单测 A1–A3 绿。

### Phase C — bg.sh 与 Python 对齐（薄）

1. 确认超时路径：写 `.timeout` 后，Python 下一 tick 必能看见并收尸。  
2. 若需：超时同时写一行可解析的 `.out` 提示（可选，优先少改 shell）；或以「只认 `.timeout` 文件」为契约并在测里锁定。  
3. `test_reviewer_bg.sh` / 相关测仍绿。  
4. 若 `gates.py` 对 TIMEOUT 已有 `_verdict_is_timeout`，确认 async 写出的正文能被识别（`**Verdict:** TIMEOUT`）。

### Phase D — 文档与回报

1. README：014 状态 → `草稿工 done <sha>`。  
2. PRODUCTION-DELIVERY-ROUNDS：R2 标完成要点（一行表）。  
3. production-readiness：加 `- [x] 014 …` 或 draft 时 `[ ]`（Cursor 合入再勾）。  
4. §8 回报。

---

## 7. 验收（必须跑）

```bash
python3 -m py_compile \
  scripts/board/roles/reviewer.py \
  scripts/engine/gates.py

bash -n scripts/ccc-reviewer-bg.sh

PYTHONPATH=scripts pytest \
  tests/scripts/test_reviewer_async_empty.py \
  tests/scripts/test_reviewer_done_marker.py \
  tests/scripts/test_reviewer_verdict_failsafe.py \
  tests/scripts/test_long_lived_session.py \
  -q --tb=short

# 若改了 shell
bash tests/scripts/test_reviewer_bg.sh

PYTHONPATH=scripts pytest tests/scripts/ -q --tb=line -k "reviewer or verdict or async"

# 禁止
# - 改 scorecard / 权威 / VERSION
# - 把空输出静默当 PASS
```

期望：相关测全绿；`git diff origin/main..HEAD --stat` 仅白名单。

---

## 8. 做完回报（固定格式）

```
BRANCH: draft/014-reviewer-bg-empty-verdict
FILES:
- …
TESTS:
- … → pass/fail
COMMITS:
- <sha> <subject>
RESIDUAL:
- …
HOW_TO_REVIEW:
- git fetch && git checkout draft/014-reviewer-bg-empty-verdict
- PYTHONPATH=scripts pytest tests/scripts/test_reviewer_async_empty.py -q --tb=short
- bash -n scripts/ccc-reviewer-bg.sh
- git diff origin/main..HEAD --stat
```

---

## 9. 给转发者的一句话

把本文件从标题到 §8 整份贴进 Claude Code；用 Claude **`/loop`**（自控节奏或 `/loop 10m …`）跑完；把 `BRANCH` + `git log --oneline origin/main..HEAD` + diff 统计发回 Cursor 审合入。
