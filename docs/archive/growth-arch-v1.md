# CCC Auto-Growth v1 — 自动成长架构

> 版本：v1.0.draft
> 日期：2026-07-13
> 状态：架构定案（待审核）
> 目标：CCC 从 30% 自动率 → 90% 自动率

---

## 一、核心诊断

CCC 当前骨架完整（Engine + 7 角色 + Board），但以下回路断了：

```
当前（断路）：
  Engine → dev → reviewer → kb       每个 task 独立，无记忆，无反馈
                      ↓
                quarantine（等冷却）

目标（回路）：
  Engine → dev → reviewer → kb → lessons → product（下次 task 参考）
                      ↓
                quarantine → 分析 → 自动修
                      ↓
              stats → engine → 调参
```

### 断路明细

| # | 回路 | 当前状态 | 影响 |
|---|------|---------|------|
| 1 | **product → dev** | product 不稳定，我常手写 plan | 卡在入口 |
| 2 | **dev → lessons** | dev 失败只 quarantine，不记教训 | 同样 bug 反复出现 |
| 3 | **Engine → 调参** | engine 参数写死（timeout/retry/model） | 不能自适应 |
| 4 | **model 分级 → 执行** | model-tier-strategy.md 是文档，不是代码 | L2 用哪级全靠感觉 |
| 5 | **kb → version** | released 后不做 version bump | 版本更新永远手动 |
| 6 | **verdict → product** | reviewer 的审查结果不反馈回拆任务环节 | 上次做错了下次还错 |

---

## 二、架构原则

| 原则 | 说明 |
|------|------|
| **非侵入式** | 不改 Engine 主循环结构，只在现有 hook 点注入新逻辑 |
| **读 stats 做决策** | 所有自适应参数调整以 stats summary.json 为输入 |
| **失败 = 数据** | 每次 quarantine 必须产出一行结构化教训，投回 lessons |
| **分层改动** | 我写架构（文档）；CCC 跑 dev（代码）；我 review |

### 不改的部分（红线）

- Engine 主循环 `engine_loop()` 的迭代逻辑
- Board JSONL 格式 `board-task-schema.md`
- 中转站（ai-loop-router）和 upstreams.json
- `.ccc/` 契约文件结构
- 7 角色 SKILL.md

---

## 三、架构设计

### 改动 1：product role 稳定化

**目标**：product_role 拆任务可靠性 ≥ 90%（当前约 40%）

**诊断**：
- `_call_claude_for_plan()` 调 claude CLI 通过中转站 4000 端口
- 不稳定原因：prompt 太长时截断、claude CLI timeout、phase 格式解析失败
- 当前已有 `_get_code_context()` + `_call_claude_for_plan()` + 模板文件

**方案**（不改 product_role 调用方式，只加固）：
1. **大 prompt 分段写入**: 如果 prompt > 60000 chars，不通过 `claude -p` 传参，改用 `--file` 附件（同 opencode-exec.py 的解决方式）
2. **phases 解析失败重试**: 如果 claude 输出解析不出 phases JSON，重试 1 次（换简化 prompt）
3. **已有 plan 跳过保护**: `phases.json` 存在时跳过 product（已有，有效）
4. **失败回退**: 超过重试次数 → 产物写到 `.ccc/product_fallback/` 目录，留一个 `need_manual_review` 标记

**验收**: product_role 连续 10 次调用无失败

### 改动 2：Lessons Pipeline

**目标**：dev 失败 → 自动写教训 → lessons.md → 下次拆任务时参考

**数据流**：
```
dev/fail → _record_failure() → .ccc/lessons/{task_id}.json
    ↓
lessons 聚合器（新脚本）→ 读所有 .json → 合并到 docs/lessons.md（Append）
    ↓
product_role 启动时读 lessons.md 最后 30 条 → 注入 prompt
```

**新文件**：`scripts/_lessons.py`

功能：
- `record_failure(task_id, phase, error, analysis)` — 写一条 `.ccc/lessons/{task_id}.json`
- `get_recent_lessons(count=30)` — 读取最近 N 条，返回结构化 list
- `append_to_lessons_md()` — 将待办 lessons 追加到 `docs/lessons.md`

**修改文件**：

| 文件 | 改动 |
|------|------|
| `scripts/ccc-engine.py` | dev 失败时调用 `record_failure()` |
| `scripts/ccc-board.py` 中 `product_role()` | 注入 lessons context |

### 改动 3：Engine 自适应调参

**目标**：Engine 根据 stats 自动调整 `timeout`、`retry`、`model`

**数据流**：
```
aggregate_stats() → summary.json
    ↓
engine 读 summary → 调参
    ↓
下次 dev_role 用新参数
```

**改 `scripts/ccc-engine.py`**（已有 `aggregate_stats()` 调用）：

| 参数 | 数据源 | 调整规则 |
|------|--------|---------|
| `timeout` | 最近 5 次 phase 平均耗时 × 2 | 最低 300s，最高 7200s |
| `retry` | 最近 10 次 task 失败率 | 失败率 > 40% → retry+1；< 10% → retry-1 |
| `model` | 默认用 Config.model | 未来可对接 summary.json 的 recommendation |

**不创建新文件**，只改 `ccc-engine.py`（~40 行）

### 改动 4：Model tier 代码化

**目标**：`model-tier-strategy.md` 的规则变成代码可读的配置

**现状**：model tier 只在文档里，`_config.py` 只有一个 `model` 字段

**改 `_config.py`**：

```python
@dataclass
class ModelTier:
    name: str          # "flash" | "code" | "pro"
    description: str   # 用途说明
    default_provider: str  # 中转站模型名（如 "deepseek-v4-flash"）
    fallback_providers: list[str]  # 降级链
    timeout_scale: float  # 相对基准 1.0
```

**不改**：
- 中转站 upstreams.json（不动）
- Engine 当前的 model 选择逻辑（只在 Config 层加新字段）

### 改动 5：VERSION/CHANGELOG 自动化

**目标**：task 进入 released 后自动 bump version + 追加 CHANGELOG

**改 `kb_role()` 已有流程**：

kb_role 从 verified → released 时，追加：
```python
_bump_version_if_needed(ws, task_id)
```

新函数逻辑：
1. 读 `VERSION` 文件
2. 按 semver 规则 bump patch（或从 task 描述推断）
3. 追加 CHANGELOG 条目 `## [新版本] - 日期`
4. git add + git commit（只在 VERSION/CHANGELOG 有变化时）
5. 失败不阻塞 kb_role（try/except）

### 改动 6：quarantine 分析 + 自修

**目标**：task 被 quarantine 时，不是干等冷却，而是分析原因、尝试自动修复

**改 `_quarantine_with_notify()` 和 `_retry_abnormal_dev_failures()`**：

1. quarantine 时：
   - 读最新 phase report → 提取失败原因
   - 写 `.ccc/failure_analyses/{task_id}.json`（结构化）
   - 如果原因是"timeout 不足" → 标记 `auto_fix: increase_timeout`

2. `_retry_abnormal_dev_failures()` 冷却到期时：
   - 检查 `.ccc/failure_analyses/{task_id}.json`
   - 如果有 auto_fix → 应用后再重试（如 timeout × 1.5）
   - 记录修复是否成功 → 反馈回 stats

---

## 四、改动汇总表

| # | 改动 | 新文件 | 改文件 | 工作量 |
|---|------|--------|--------|--------|
| 1 | product role 加固 | 0 | `ccc-board.py`（~30 行） | 中 |
| 2 | Lessons Pipeline | `_lessons.py`（~150 行） | `ccc-engine.py`（+5 行）, `ccc-board.py`（+3 行） | 中 |
| 3 | Engine 自适应调参 | 0 | `ccc-engine.py`（~40 行） | 中 |
| 4 | Model tier 代码化 | 0 | `_config.py`（~30 行） | 小 |
| 5 | VERSION/CHANGELOG 自动化 | 0 | `ccc-board.py`（~50 行追加到 kb_role） | 小 |
| 6 | quarantine 分析 + 自修 | 0 | `ccc-engine.py`（~40 行） | 中 |

**总计**：1 新文件（~150 行），4 改文件（~200 行净增）

---

## 五、开发顺序

```
Phase 1: 改动 5（VERSION/CHANGELOG）— 最轻，不影响其他
Phase 2: 改动 4（model tier 代码化）— 纯 Config 层
Phase 3: 改动 1（product role 加固）— 入口稳定
Phase 4: 改动 3（Engine 自适应调参）— 依赖 stats 已接入
Phase 5: 改动 2（Lessons Pipeline）— 依赖 knowledge 流转
Phase 6: 改动 6（quarantine 分析）— 依赖 lessons 已就绪
```

---

## 六、验收标准

| 维度 | 验收 |
|------|------|
| Engine 运行 | 连续 7 天无 crash |
| product role | 连续 10 次拆任务成功 |
| lessons | 每次 dev 失败 → 1 条教训文件 |
| version bump | released 后 VERSION + CHANGELOG 自动更新 |
| 自适应 | stats → timeout/retry 在 6 轮内生效 |
| Cursor 调用 | 1 个 prompt 完成全部 phase 编码 |
