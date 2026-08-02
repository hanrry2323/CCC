# DEV-PACKET: 015-failure-reopen-quarantine-harden

> 复制本文件**全文**发给**个人 Claude Code CLI**（接 Relay `flash`；非 Desktop Agent）。  
> 合入权威 = Cursor。做完提交到指定分支，**不要 push main**。  
> **主题**：失败可收加固 — reopen / quarantine 机读码（R3 · 接 014）。Ops UI **禁止**。

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

014 已合入：async 空输出/超时必落 verdict。R3 聚焦**失败可收**：

1. **enabled** 下瞬态 abnormal **work** 有限 reopen（≤2/卡；经 `_task_reopen`；禁 orch/invent）路径要有**可重复单测**锁口径。  
2. quarantine / abnormal `reason`（及 `reason.txt` / note）对 hang / 无 verdict 等关键路径**必含可机读码**（如 `hang_detected`、`reviewer_produced_no_verdict`），禁止只写散文 `acceptance_cmd_failed`。  
3. **不抬** quarantine / fail_loop 阈值；不改 scorecard；不做 Ollama。

做完后：

- `reopen_task` + auto-refeed 边界（epic 跳过、permanent 跳过、≥2 停、orch 拒）测绿。  
- hang / 关键 quarantine 文案含机读码有测锁定。  
- `_task_reopen` 清 pid 与 014 对称（含 `.reviewer.timeout` / `.exitcode`）。

对应：failure-learning Refeed · P-D · PRODUCTION-DELIVERY-ROUNDS R3。

---

## 2. 分支与提交

- 基线：最新 `origin/main`（应含 014 · `b3936c9` 或更新）
- 分支：`draft/015-failure-reopen-quarantine-harden`
- 提交风格：`fix(reopen): …` / `fix(quarantine): …` / `test: …`（英文 why）
- **禁止** `git push origin main`；可 `git push -u origin draft/015-failure-reopen-quarantine-harden`
- **禁止** `git add -A` / `git add .`；只 add §3 白名单

```bash
git fetch origin main
git checkout -B draft/015-failure-reopen-quarantine-harden origin/main
```

---

## 3. 白名单（只许改这些）

### 代码 / 测

- `scripts/_task_reopen.py`（pid 清理对称；reopen 边界若需）
- `scripts/engine/failure_router.py`（classify / budget；机读码辅助若需）
- `scripts/_failure_ledger.py`（`related_stats_event` / infer；薄）
- `scripts/_failure_learning.py`（薄，仅 reopen/pack 对齐）
- `scripts/ccc-engine.py`（**仅** `_retry_abnormal_failures` / `_classify_failure` 相关最小改；禁止大重构）
- `scripts/engine/hang.py`（仅当 reason 缺 `hang_detected` 时补）
- `scripts/engine/gates.py`（仅当 quarantine reason 缺机读码时薄补）
- `tests/scripts/test_task_reopen.py`（新建或从 `scripts/tests/` 迁扩；优先 `tests/scripts/`）
- `tests/scripts/test_retry_abnormal_refeed.py`（新建：auto-refeed 边界）
- `tests/scripts/test_quarantine_reason_codes.py`（新建：机读码）
- `scripts/tests/test_task_reopen.py`（若双轨需镜像，保持同语义）
- `tests/scripts/test_hang_classification.py` / `test_failure_ledger.py`（仅扩断言，勿删绿测）

### 文档（薄）

- `docs/dev-packets/README.md`
- `docs/dev-packets/PRODUCTION-DELIVERY-ROUNDS.md`（R3 状态）
- `docs/briefs/2026-07-27-ccc-production-readiness.md`（加一行 015）
- `docs/briefs/2026-07-23-failure-learning.md`（可选一句「015 测锁」）

---

## 4. 黑名单（碰了就停）

- `docs/product/loop-engineer-authority.md`（只读对齐）
- `.cursor/rules/loop-engineer-consensus.mdc`
- `references/red-lines.md` / `references/stress-kpi-scorecard.json`
- `VERSION` / `CHANGELOG` / `docs/releases/**`
- `relay/**`、密钥、launchd、Desktop/SPA/Ops UI
- 业务仓 `/Users/fan/program/apps/**`
- **禁止**把 `MAX_AUTO_RETRY` / `review_fail_loops≥3` / `MAX_TASK_RETRY_BUDGET` **抬高**当「修绿」
- **禁止** invent / 对 orch 自动 reopen
- 任意未列路径

---

## 5. 现状锚点

| 锚点 | 说明 |
|------|------|
| Refeed | `ccc-engine.py` `_retry_abnormal_failures` ≈2863：`MAX_AUTO_RETRY=2`；跳过 epic / permanent / exhausted |
| reopen API | `scripts/_task_reopen.py` `reopen_task`；现测在 `scripts/tests/test_task_reopen.py` |
| classify | `engine/failure_router.py` `classify_failure`；默认 transient |
| hang 码 | authority：reason **必须**含 `hang_detected`；ledger `related_stats_event=hang_detected` |
| 014 残留 | `_task_reopen._PID_SUFFIXES` 可能仍缺 `.reviewer.timeout` / `.reviewer.exitcode`（有 glob 兜底，宜显式） |
| brief | `docs/briefs/2026-07-23-failure-learning.md` Refeed 行 |
| 版本 | v0.63.x（本包不 bump） |

---

## 6. 实现步骤（Phase）

### Phase A — 红测：reopen + refeed 边界

1. 在 `tests/scripts/` 写（或迁）`test_task_reopen.py`：abnormal→planned；拒 verified；清 `.reviewer.timeout`。  
2. 新建 `test_retry_abnormal_refeed.py`，对 `_retry_abnormal_failures` **尽量纯函数/可注入**测（tmp_path board）：  
   - **A1** work + transient reason + 冷却已过 → reopen 到 planned，计数 +1。  
   - **A2** epic → 不 reopen。  
   - **A3** reason 含 `reviewer_fail_loop_exhausted` / permanent 关键词 → 不 reopen。  
   - **A4** 已 auto-retry ≥2 → 不 reopen。  
   - **A5** orch 路径（模拟 `is_orch_path` True）→ 直接 return。  
3. 若函数难测：允许抽 `_should_auto_refeed(task, …) -> bool` 小纯函数到 `failure_router` 或 engine 旁路，**禁止**复制整段 tick。

### Phase B — 机读 quarantine / hang reason

1. 新建 `test_quarantine_reason_codes.py`：  
   - hang 耗尽 / acceptance 124 路径产出的 reason **含** `hang_detected`。  
   - 「无 verdict」类 quarantine reason **含** `reviewer_produced_no_verdict` 或与 013 helper 一致的稳定码。  
2. 缺则改 `hang.py` / `gates.py` 写 reason 处补码（薄）。  
3. **不要**改人类可读中文前缀；码用 snake_case 嵌入即可。

### Phase C — reopen 清理对称 + 回归

1. `_PID_SUFFIXES` 显式加入 `.reviewer.timeout`、`.reviewer.exitcode`（及若有 `.tester.timeout` 对称）。  
2. 跑 hang / failure_ledger / task_reopen / refeed 相关测全绿。  
3. 确认未抬任何阈值常量。

### Phase D — 文档与回报

1. README：015 → `草稿工 done <sha>`。  
2. ROUNDS：R3 标完成要点。  
3. production-readiness：`- [x] 015 …`（或 draft `[ ]`，Cursor 合入勾）。  
4. §8 回报。

---

## 7. 验收（必须跑）

```bash
python3 -m py_compile \
  scripts/_task_reopen.py \
  scripts/engine/failure_router.py \
  scripts/_failure_ledger.py \
  scripts/ccc-engine.py \
  scripts/engine/hang.py \
  scripts/engine/gates.py

PYTHONPATH=scripts pytest \
  tests/scripts/test_task_reopen.py \
  tests/scripts/test_retry_abnormal_refeed.py \
  tests/scripts/test_quarantine_reason_codes.py \
  tests/scripts/test_hang_classification.py \
  tests/scripts/test_failure_ledger.py \
  scripts/tests/test_task_reopen.py \
  -q --tb=short

PYTHONPATH=scripts pytest tests/scripts/ -q --tb=line -k "reopen or refeed or hang_detected or quarantine_reason"

# 禁止
# - 抬 MAX_AUTO_RETRY / fail_loop / scorecard
# - 对 orch 自动 reopen
```

期望：相关测全绿；`git diff origin/main..HEAD --stat` 仅白名单。

---

## 8. 做完回报（固定格式）

```
BRANCH: draft/015-failure-reopen-quarantine-harden
FILES:
- …
TESTS:
- … → pass/fail
COMMITS:
- <sha> <subject>
RESIDUAL:
- …
HOW_TO_REVIEW:
- git fetch && git checkout draft/015-failure-reopen-quarantine-harden
- PYTHONPATH=scripts pytest tests/scripts/test_retry_abnormal_refeed.py tests/scripts/test_quarantine_reason_codes.py -q --tb=short
- git diff origin/main..HEAD --stat
```

---

## 9. 给转发者的一句话

把本文件从标题到 §8 整份贴进 Claude Code；用 Claude **`/loop`** 跑完；把 `BRANCH` + `git log --oneline origin/main..HEAD` + diff 统计发回 Cursor 审合入。
