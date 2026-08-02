# 任务书 B · 后端与引擎修复（窗口 B）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 B 即可。

## 0. 先读

1. `CLAUDE.md`
2. `docs/architecture-core.md`、`docs/architecture.md`、docs 下稳定性/状态机相关文档
3. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 任务目标

1. 红旗扫：重构遗留的裸异常、模块级状态、过期测试（如 hp=404 类）
2. 修复明确问题：异常吞掉、错误边界、状态机/验收门缺口（verified→released 人工确认门）按 docs 与现有契约对齐
3. 千行级大模块（engine / board_store）**只做可安全拆分的点**，不做大爆炸重构——列出候选与理由，能不动就不动
4. 补/修后端测试

## 2. 允许范围

- `scripts/` 下引擎与后端逻辑、`app/services/`、后端测试
- 契约/状态机相关文档同步（文档改动要列入报告）

## 3. 红线（禁止）

- 网页前端、`desktop/`、`src-tauri/`
- 4000/4100 与 relay 相关（窗口 D 的活）
- 不启动产线、不改运行态、不动 Hub/Board 服务
- 密钥/凭据/生产配置
- 提交 main

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「红旗清单 + 每个修复的问题→动作→影响面」，**只读不改**。  
确认后实现：小步提交，每步有测试。

## 5. 验收标准

- 红旗清单每条有结论（修了 / 不是问题 / 暂缓）
- 新增/修复逻辑有测试覆盖，后端测试全绿
- 状态机与验收门行为与 docs 契约一致（有证据）
- 报告标注哪些是「安全拆分」、哪些「暂缓」

## 6. 完成报告格式

发现 → 动作 → 证据 → 风险

## 7. 已知基线失败（必做，主仓 d94796b 复跑确认，非窗口 D 引入）

全量 `pytest tests/scripts/` 现有 13 例失败，失败集已用干净 main 复跑确认一致，集中在这几个区域：

- `test_acceptance_gate`
- `test_authority_patrol` ×2
- `test_gate_rule_fitness`
- `test_hang` ×2
- `test_hygiene_transfer_acceptance`
- `test_intent_probe_lpsn` ×6
- `test_script_seed`

要求：

1. 全量复跑 `tests/scripts/`，逐例判定「修复 / 不是问题 / 暂缓」
2. 修复项必须带测试证据；判定「不是问题」必须给理由
3. 目标是这 13 例清零或逐条标注可接受理由，写进完成报告
