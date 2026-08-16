# CodeRun 测评 · 埋点计划（统计基础）

- **状态**：计划（待实施）
- **目的**：为「CodeRun 模式 + CCC 流程」后期统计提供结构化数据。当前数据散在卡文件/engine 日志/执行日志，缺统一可查询的统计层。
- **日期**：2026-08-17

## 一、要统计什么（三类）

### A. 开发流程（CCC 卡生命周期）
| 数据点 | 说明 | 现状 |
|---|---|---|
| 卡状态迁移时间戳 | 待分派→执行中→已回写→机审→待合入→已关闭，各节点时间 | ⚠️ 部分（dispatched_at/written_at 有，其他缺） |
| 打回轮次 | 每卡打回次数 | ⚠️ reject_count 有，但打回原因没结构化 |
| 打回原因分类 | 维护区声明不实 / 代码质量 / 红线 / 机械门禁 | ❌ 无（在日志文本里） |
| 机审 severity | 轻/中/重 + 通过/不通过 | ❌ 无（在 audit 文本里） |
| 各阶段耗时 | 开发耗时 / 机审耗时 / 总耗时 | ❌ 无 |

### B. CodeRun 编排（模式有效性）
| 数据点 | 说明 | 现状 |
|---|---|---|
| 是否用编排 | 任务卡是否真的走了程序化编排（vs 逐轮） | ❌ 无（hp030 无法确认 opencode 是否遵守） |
| 子调用并发度 | 编排程序内并行子调度数 | ❌ 无 |
| 工具调用数 / 模型轮次 | 每任务调用量 | ❌ 无（DSH session 有，CCC 无） |
| description 缺失次数 | CodeRun 特有失败 | ⚠️ DSH session 可提取，CCC 无 |
| 失败/重试次数 | 卡死、命令失败、重试 | ⚠️ engine 日志有，未结构化 |

### C. 模型（档位 × 质量）
| 数据点 | 说明 | 现状 |
|---|---|---|
| 每任务模型档位 | flash/code/pro/直连/中转 | ⚠️ 可推，未记录 |
| 模型调用量 | token / 次数 / 耗时 | ❌ 无 |
| 模型质量 | 打回率 / 修复轮次 / 机审通过率 | ❌ 无 |

## 二、埋点位置与载体

| 位置 | 载体 | 埋什么 |
|---|---|---|
| **CCC Engine** | `server/engine/main.py` 关键节点（派发/打回/机审/收单） | 写结构化 JSON 行（时间/卡/事件/原因/severity）到统计表 |
| **CCC 看板** | `server/board/` | 卡状态迁移记时间戳 + 打回原因分类字段 |
| **DSH** | `dsh-session-telemetry`（otel 已有） | CodeRun 会话：run_code 调用/description 缺失/子调度/耗时 |
| **执行日志** | `exec/*.log` | 结构化事件提取（start/dispatch/audit/collect/result） |

## 三、数据结构（建议）

每事件一行 JSON（append-only 统计表）：
```json
{
  "ts": "ISO时间", "card": "hp030", "project": "hp",
  "event": "audit_reject",            // 或 dispatch/dev_done/writeback/audit_pass/close
  "stage": "audit",                   // dev/audit/merge
  "executor": "opencode|claude|dsh",
  "model_tier": "code|flash|pro",
  "use_code_run": true/false,         // 是否走了 CodeRun 编排
  "reason": "维护区声明不实",          // 打回原因
  "severity": "中",                    // 机审 severity
  "round": 8,                          // 打回轮次
  "duration_s": 123,
  "tool_calls": 45, "model_calls": 12, "desc_missing": 3
}
```

## 四、落地步骤

1. **Engine 埋点**（改 `main.py` 派发/打回/机审/收单 4 处）：写结构化事件行 → `~/.ccc/logs/events.jsonl`
2. **看板状态字段**（`board/models.py` + 卡文件）：补 `reject_reason` / `severity` / 阶段时间戳
3. **DSH 对接**：CodeRun 会话统计从 session telemetry 提取（description 缺失/子调度/耗时）
4. **统计查询**：一个 `stats.py` 脚本读 events.jsonl → 出报表（打回率/机审通过率/耗时/CodeRun 遵守率/模型质量）

## 五、优先级

- **P0**：Engine 埋点（事件结构化）——这是统计的地基
- **P1**：看板补原因字段 + 阶段时间戳
- **P2**：DSH CodeRun 会话统计对接
- **P3**：stats.py 报表

> 关联：全流程梳理（命令PATH/worktree_base/机审模型配置 已记录 31-formal-flow-issues.md），埋点是它的统计侧补充。
