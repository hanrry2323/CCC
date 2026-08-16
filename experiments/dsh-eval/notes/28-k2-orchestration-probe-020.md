# 探针 · CodeRun 编排在真实卡上的应用（020 Worker 池设计卡）

- **状态**：✅ 完成（首个真实卡应用探针）
- **批次**：Phase 3 · 卡2 任务编排探针（卡内探针 1）
- **环境**：M1（编排程序 + 并行取证）
- **日期**：2026-08-16

## 结论

**CodeRun 编排模式在真实多步骤卡上跑通并提效**：020 Worker 池设计卡的「并行取证」阶段，1 个编排程序、4 路并发取证、**1 秒**完成，产出结构化证据。同时**暴露 020 设计草案的 RC7 事实已过时**（见下）。相比现状逐轮工具调用（4+ 次串行读 + 模型中间推理），编排方式少 4 倍往返、取证完整、一次性看到全貌。

## 方法

编排程序（`/tmp/orch_probe.sh`）模拟 CodeRun 语义：
- 一段程序内 4 路并行取证（`&` 并发 = Promise.all）：
  - 路1 RC4 执行/决策寻址：dispatch.py 的 cli_entry_for_binding / rows_for_worker_id
  - 路2 RC7 注册表双源：example vs 2017 生产 executors 的 worker_id
  - 路3 Worker 现状：ExecutorEntry 字段 / worker routing 测试
  - 路4 决策态定义：AUTO/REMOTE/MANUAL
- `wait` 汇合 → 一次性输出全部证据。

## 结果（1 秒，4 路证据）

```
=== 4 路并行取证完成，耗时 1s（串行预计 4 倍）===
路1: cli_entry_for_binding(dispatch.py:151) 认 W 号(re.fullmatch W\d+ :156)；rows_for_worker_id(:126) 存在
路2: example worker_id: W4/W4/W3/W1/W4/DSH —— 2017 生产 executors 同：W4/W4/W3/W1/W4/DSH（两源一致！）
路3: test_worker_routing.py 断言 worker_id 对齐(W1-W4 各命中)；test_engine_dispatch.py:62 标签寻址
路4: dispatch.py:64-65 AUTO/REMOTE="remote" 已定义；REMOTE 注释「ccc-plan-020 执行计划 v2」
```

## 关键发现：020 设计草案的 RC7 已过时

- 020 草案（2026-08-11）声称：**RC7 注册表双源漂移**——「2017 生产 executors.json：W1-W4 无 worker_id（仅 W9 有）」。
- **探针实测（2026-08-16）**：2017 生产 executors.json **W1-W4 全部有 worker_id**（W4/W4/W3/W1/W4/DSH），与 example **一致**。
- 结论：RC7 已被修复（或 08-11 后文件更新），**020 草案的该根因需要复核更新**，且 `REMOTE` 决策态已实现（dispatch.py:65）——020 的执行计划 v2 有部分已落地。

## 提效对比（CodeRun 编排 vs 现状逐轮）

| 维度 | 现状（逐轮调用） | CodeRun 编排 |
|---|---|---|
| 工具调用 | 4+ 次串行 read/grep/ssh，每次等返回 | 1 程序内 4 路并发 |
| 耗时 | ~4×（含模型中间推理往返） | 1s（纯并行 IO） |
| 证据完整性 | 逐次读，易漏关联 | 一次全貌，可直接交叉 |
| 事实变化暴露 | 依赖人工注意 | 并行比对自动暴露（RC7 过时） |

## 风险 / 对 CCC 借鉴的意义

- **证明 CodeRun 模式在 OpenCode/CC 里可行**（不依赖 DSH）：一段编排程序 = 多步骤并行取证，正是「多步骤小卡」的解法雏形。
- 020 草案需按最新事实复核（RC4/RC7 已演进），可作为后续真实开发卡。
- 下一步：把同一卡跑「结构化产出 + 验收重跑」段，形成完整 dev→review 闭环探针。
