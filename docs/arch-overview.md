# CCC 架构总览（2026-07-07）

## 一句话

CCC = 自动化开发框架。Claude 做规划，opencode 写代码，6+1 角色管流水线。

---

## 1. 部署逻辑

```
Claude（我）←→ 用户
    │ 商讨方案
    │ 写 plan.md + phases.json
    │ --promote 进 planned
    ▼
opencode（dev 角色）
    │ 每 10min 取 1 个 planned
    │ 执行 opencode run --model flash <plan>
    │ 报告结果
    ▼
reviewer / tester → verified → kb → released → regress(回测)
```

**CCC 项目本身** (`~/program/CCC/`) = 这套工具的开发自用。
**其他项目**（qxo 等）= 各自一套 plist + `.ccc/board/`，用相同角色流水线。

---

## 2. 7 角色  看板列 = 流水线

```
角色        扫哪列        做什么                    放哪列
──────      ──────        ──────                    ──────
product     backlog       读需求、写 plan（我手动）      planned
dev         planned       调 opencode 写代码            in_progress → testing
reviewer    testing       静态检查（py_compile）        verified
tester      testing       测试（pytest）               verified
ops         所有列        健康检查                     不动 board
kb          verified      git tag + push + changelog    released
regress     released      每日回测，发现回归→建 bug     backlog（建新 bug）
```

**关系图**：
```
backlog ─→ planned ─→ in_progress ─→ testing ─→ verified ─→ released
  ↑          ↑              ↑            ↑           ↑            ↑
product    product        dev         dev/rev      reviewer     kb
（收件箱）  （写plan）     （执行中）    （等验收）    /tester      （发布）
                                                                  ↓
                                                               regress
                                                              （回测→bug）
```

**每个角色都有独立 SKILL.md**（职责/方法论/红线）。当前齐全。

---

## 3. 测试/验证的问题和优化

### 现状（太粗糙）

```python
reviewer: for py in ALL scripts/*.py:  py_compile(py)
tester:   pytest tests/scripts/（全部测试）
```

完全不看任务改了什么文件，不看 plan.md 里的验收项。

### 应该做的

| 优化 | 说明 |
|------|------|
| **按任务范围审查** | 读 plan.md 的"文件白名单"，只检查涉及的文件 |
| **读取验收项** | plan.md 里有验收命令，应该逐个执行 |
| **失败定位** | reviewer 告诉你是哪个文件、什么原因 |
| **跳过非 Python 任务** | 文档/配置任务不跑 py_compile |

---

## 4. 学习飞轮接入

```
regress 发现回归 → 建 bug 到 backlog
       ↓
product 写新 plan → 读 AGENTS.md 避免重复踩坑
       ↓
dev 执行 → report 末尾写 AGENTS.md 建议段
       ↓
kb 归档 → 收集建议到 pending-agents-suggestions.md
       ↓
人类审批 → 写入 .ccc/AGENTS.md
       ↓
product 下次写 plan 时自动读 AGENTS.md
```

**关键节点**：
- **dev**: 失败的执行 → report 末尾写 `> **AGENTS.md 建议:**`
- **kb**: 归档时收集建议
- **regress**: 重复失败的 bug → 自动建议加到 AGENTS.md
- **product**: `--promote` 时读 AGENTS.md 作为参考
