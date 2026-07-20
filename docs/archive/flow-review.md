# CCC 全流程弱点清单

> 2026-07-09 基于 4 轮实战（并发测试/qx 收口/qb 对抗审查/Trae 集成）总结。
> 目的：明确当前流程的已知薄弱点，记录在文档而非靠记忆。

---

## 已加固的弱环

| 弱点 | 修复版本 | 修复内容 |
|------|---------|---------|
| engine 取 task 后不更新 index | v0.23.2 | 加 `update_index()` |
| 时间戳全部用 UTC | v0.23.3 | 改为北京时间 +08:00 |
| **Trae 报告格式无校验** | **v0.23.4** | **加 `_review_validator.py`** |

---

## 仍未修的弱环（按严重度）

### 🔴 P0: reviewer_role LLM 审查空转（v0.23.5 已修）

**现象**：24 个完成 task 中 87.5% 的 verdict 是 FALLBACK，reviewer 实际没用。

**影响**：task 未经真审查就从 testing 推到 verified → released。

**原因**：`_review_with_llm` 调 `claude -p` 未指定 `--model flash`（CLAUD.md 要求），且提示词 JSON 指令不够明确导致 LLM 偶尔输出非 JSON。

**修复方案**（v0.23.5）：
- `_review_with_llm` 加 `--model flash`（符合子进程规范）
- 提示词 `` 严格 JSON `` 改为 `不要包装 markdown，不要附加解释`
- JSON 提取优先抓 markdown 代码块，其次裸 JSON
- `_get_git_diff` 首次 commit（无 HEAD~1）降级到 `--root`，避免空 diff

---

### 🔴 P1: OpenCode 池上限未强制执行（红线 X1 形同虚设）

**现象**：并发测试中 5 个 engine 同时启动 5 个 opencode run 进程，M1 8GB 内存压力显著。

**原因**：`ccc-engine.py` 直接 `Popen(opencode-runner.sh)`，不走 `opencode-pool.py`。

**修复方案**：engine 的 `dev_role_launch` 加 opencode 并发计数检查。

---

### 🟡 P2: task 超时后 engine 无降级策略

**现象**：300s 超时的 task 仍标记为 in_progress，engine 不重试、不跳过、不告警。

**影响**：超时 task 永久占用 in_progress 列，阻塞后续 task。

**修复方案**：v0.24 加超时 → quarantine 或重试逻辑。

---

### 🟡 P3: 跨 project engine 无通信

**现象**：5 个 engine 各自独立运行，不知道其他项目在做什么。

**影响**：OpenCode 池超限（P1）的根本原因——每个 engine 不知道自己以外还有 4 个 engine 在跑。

**修复方案**：共享的 opencode 并发计数器（文件或 Redis）。

---

### 🟢 P4: reports/ → backlog 无自动转 task

**现象**：Trae 写报告到 `.ccc/reviews/` 后，需要我手动创建 backlog task。

**影响**：不是 bug，是设计（我在中间做评估过滤）。但如果做自动转 task 可以加速。

**注意**：auto_fixable=true 的 finding 可以自动转 task 跳过人。但需要 reviewer 门禁先加固（P0）。

---

## 四层流程稳固摘要

```
Trae 写报告 → .ccc/reviews/         → engine 自动校验格式 ✅（v0.23.4 新加）
engine 校验 → 告警/通过              → 我读报告创建 backlog task
backlog     → product 拆 plan        → engine 执行
engine 执行 → dev → reviewer → kb    → released

弱环集中在这层：↓
reviewer    → 87.5% 空转 ❌          → 需 v0.24
opencode    → 并发 5+ 超限 ❌        → 需 v0.24
超时 task   → 不降级 ❌              → 需 v0.24
```
