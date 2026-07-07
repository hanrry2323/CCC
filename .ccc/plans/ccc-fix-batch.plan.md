# Plan: ccc-fix-batch — 文档/脚本一致性批量修复 (2026-07-07)

> 撰写：Planner (ccc-fix-batch) | 执行：Planner 本人 (修复任务，跨文件，无 Executor)

---

## 范围

- **目标**：8 项一致性/清理修复（用户直接指定，无需启用 CCC 完整流程）
- **改动文件**：
  1. `CLAUDE.md` — 恢复 v0.7 原始（drop v0.8 WIP）
  2. `references/red-lines.md` — 标题/编号索引表/补 红线 12/合并 红线 13/去重 红线 18
  3. `scripts/ccc-task-done.sh` — L93 修复 `$WORKSPACE` 传参
  4. `scripts/__pycache__/*.pyc` — 清理
  5. `.ccc/plans/`, `.ccc/reports/`, `.ccc/verdicts/`, `.ccc/phases/` — 选择性归档 v0.7 完工产物 + 清理孤儿
  6. `docs/roadmap.md` — 加过期 banner（v0.6/v0.7 完成,当前 v0.7.0）
  7. `SKILL.md` — L47 红线数描述对齐
  8. `docs/lessons.md` — 顶部加 qxo→CCC 转型 banner
  9. `.ccc/state.md` — 更新最近任务表为真实完整 v0.7 子任务链

---

## 验收

- [x] E1: CLAUDE.md 无 `test_precheck_all_pass`（grep 返回 0）
- [x] E2: red-lines.md 标题不再写 "10 条红线"（grep 0 命中）
- [x] E3: red-lines.md 含 "红线 12" 条目（grep 命中）
- [x] E4: ccc-task-done.sh L93 传 `$WORKSPACE`（grep 命中）
- [x] E5: scripts/__pycache__/*.pyc 已清空（ls 无输出）
- [x] E6: SKILL.md L47 不再写 "11 条硬约束"（grep 0 命中）
- [x] E7: lessons.md 含 qxo→CCC 转型 banner（grep 命中）
- [x] `python3 -m pytest tests/scripts/ -q`（排除 3 个 v0.8 WIP 测试）— 42 passed
- [x] `bash scripts/ccc-precheck.sh . ccc-fix-batch` — 5/5 PASS
- [x] 每条改动独立 staging + commit，commit message 含 `ccc-task-id=ccc-fix-batch`

---

## 不在范围

- 禁止改动测试文件 (`tests/scripts/*.py`)
- 禁止改动 `VERSION` / `CHANGELOG.md` 顶部版本号
- 禁止改动 `.gitignore` / `.env` / 密钥文件
- 禁止 sudo
- 禁止引入新外部依赖
- SKILL.md 的红线清单内容本身（只改 L47 数字描述）
- 不动 v0.8 WIP 测试（被 `--ignore` 排除）

---

## 风险

- **低**：纯文档/清理类，无代码逻辑改动
- **中**：red-lines.md 编号改动可能影响外部引用，但 CLAUDE.md 仅做"恢复"，已对齐

---

## 执行顺序

每条改动独立 commit，顺序：
1. CLAUDE.md 恢复
2. red-lines.md 编号修复
3. ccc-task-done.sh L93 修复
4. pyc 清理（gitignore，无需 commit）
5. .ccc/ 归档 + state.md 更新
6. roadmap.md 过期 banner
7. SKILL.md L47 描述对齐
8. lessons.md qxo→CCC banner
9. pytest + precheck 全跑

---

## 只改文件白名单

9 个明确目标文件 + .ccc/ 工作产物：

1. `/Users/apple/program/CCC/CLAUDE.md` — 恢复 v0.7 原始
2. `/Users/apple/program/CCC/references/red-lines.md` — 编号修复
3. `/Users/apple/program/CCC/scripts/ccc-task-done.sh` — L93 bug
4. `/Users/apple/program/CCC/scripts/__pycache__/*.pyc` — 清理（gitignore）
5. `/Users/apple/program/CCC/.ccc/plans/` + `reports/` + `verdicts/` + `phases/` — 选择性归档 v0.7 完工产物
6. `/Users/apple/program/CCC/docs/roadmap.md` — 加过期 banner
7. `/Users/apple/program/CCC/SKILL.md` — L47 描述对齐
8. `/Users/apple/program/CCC/docs/lessons.md` — 顶部 banner
9. `/Users/apple/program/CCC/.ccc/state.md` — 最近任务表更新

**白名单外不动**：
- `tests/scripts/*.py`（红线 3）
- `VERSION` / `CHANGELOG.md`（用户约束）
- `.gitignore` / `.env` / 密钥（用户约束）

---

## Commit 计划表

| Phase | 改动 | Commit 消息 |
|-------|------|-------------|
| 1 | CLAUDE.md | `fix(docs): restore CLAUDE.md to v0.7 original` |
| 2 | red-lines.md | `fix(docs): red-lines.md numbering fix — title, index, add 红线12, dedup 红线13/18` |
| 3 | ccc-task-done.sh | `fix(scripts): ccc-task-done.sh L93 pass WORKSPACE` |
| 4 | pyc 清理 | (gitignored, 无 commit) |
| 5 | .ccc/ 归档 | `chore(ccc): archive v0.7 closure artifacts + state.md full table` |
| 6 | roadmap.md | `fix(docs): roadmap.md add 过期 banner — v0.6/v0.7 完成,当前 v0.7.0` |
| 7 | SKILL.md | `fix(docs): SKILL.md L47 红线数描述对齐` |
| 8 | lessons.md | `fix(docs): lessons.md add qxo→CCC 转型 banner` |
| 9 | pytest + precheck | (验证步骤,无 commit) |

每条 commit message 末尾追加 `ccc-task-id=ccc-fix-batch`。
