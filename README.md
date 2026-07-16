# CCC — Connect–Claude Code

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.42.1-blue.svg)](VERSION)

> **Loop Engineer：人定意图，系统自动编排与自主执行。**  
> 自研 **CCC Hub** 做入口；任务路由工具；Skill + Prompt 即角色——用户不选角色、不背 Skill。

**产品叙事 SSOT**：[`docs/VISION.md`](docs/VISION.md)  
**启动必读（Agent）**：[`STARTUP-BRIEF.md`](STARTUP-BRIEF.md) · 权威版本：根目录 `VERSION`

---

## CCC 是什么

**C**onnect — **C**laude **C**ode

CCC 不是「又一个 IDE」，也不是「角色超市」。它是一台 **Loop Engineer**：

| 层 | 做什么 |
|----|--------|
| **Hub（对话面）** | 对齐基线 → 定稿方案 → 转任务；快捷动作完成人机交接 |
| **Engine + Board（编排面）** | 看板闭环：拆解、开发、验收、重试、重开、进化 |
| **工具路由（执行面）** | Claude / OpenCode 等按任务选用；Token 与成本可治理 |

第三方 Agent IDE 壳（zcode、Qoder 等）曾是过渡方案；**现在 Hub 已完全替代入口**，且在「定意图 → 自动闭环」上超过「只聊天 / 只写码」的工具。

### 无穷角色（不是 7 个固定工种）

```text
任务意图 → 路由工具 → Skill + Prompt = 本次角色
```

仓库中的 `skills/ccc-*` 是**流水线阶段默认能力包**（拆解 / 写码 / 审查 / 测试 / 归档…），由 Engine 按任务调度——**不是**让用户先挑角色。  
任意行业、任意复杂工作：差异落在 Skill / Prompt / 路由上；**用户始终只面对意图**。

---

## 30 秒看懂闭环

```text
对齐 → 定稿 → 转任务 → Engine 自动编排
  → 开发 → 验收 →（失败则重试/重开）→ 归档 → 可进化
```

看板列（不可跳列）：

```text
backlog → planned → in_progress → testing → verified → released
```

---

## Quick Start

```bash
git clone https://github.com/hanrry2323/CCC.git
cd CCC

# 1) Hub + Board（UI 入口，默认不拉起常驻 Engine）
bash scripts/install-board-plist.sh --start
bash scripts/install-hub-plist.sh --start

# 2) 浏览器
open http://127.0.0.1:7777
# 默认账密：ccc / ccc   （详见 docs/ccc-hub-ports.md）
```

在 Hub 里建议路径：

1. **对齐基线** → **下一步** → **定稿方案** → **转任务** → **下达并开工**  
2. 需要自动跑队列时：`bash scripts/ccc-autostart-guard.sh enable --start`  
3. 允许系统自造任务时（显式）：`… invent --start`

完整步骤与排障：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)

---

## 和谁不一样

| | Chat | OpenCode 等执行器 | ECC 类角色工坊 | **CCC** |
|--|------|-------------------|----------------|---------|
| 入口 | 对话 | CLI / 编辑器 | 选角色 | **Hub** |
| 编排 | 无 | 弱 | 人工为主 | **Engine Loop** |
| 角色 | 无 | 无 | 固定一堆 | **任务生成（无穷）** |
| 验收 | 口头 | 自测 | 看产品 | **verdict 文件门禁** |

---

## 仓库地图

| 路径 | 说明 |
|------|------|
| `docs/VISION.md` | 产品叙事 SSOT |
| `scripts/chat_server/` | CCC Hub（对话 / 看板 / 控制台） |
| `scripts/ccc-engine.py` | Loop Engineer 主循环 |
| `scripts/ccc-board.py` | 看板与阶段能力调度 |
| `skills/ccc-*/` | 阶段默认 Skill（能力包） |
| `references/red-lines.md` | 工程红线 |
| `docs/CONTROL.md` | 运行控制面（disabled/ui/enabled/invent） |

---

## 工程纪律（摘要）

- **红线 11**：验收必须写 verdict 文件（口头 PASS 无效）  
- **红线 12**：禁止 agent 擅自启用 CCC（须用户显式触发）  
- **控制面默认 `disabled`**：不偷偷常驻、不自造任务  

全文：`references/red-lines.md`

---

## 文档

| 文档 | 读者 |
|------|------|
| [VISION](docs/VISION.md) | 所有人（定位） |
| [Getting Started](docs/GETTING-STARTED.md) | 首次安装 |
| [USAGE](docs/USAGE.md) | 日常使用 |
| [STARTUP-BRIEF](STARTUP-BRIEF.md) | Agent / 维护者（省 token） |
| [CONTRIBUTING](CONTRIBUTING.md) | 贡献者 |
| [CHANGELOG](CHANGELOG.md) | 版本历史 |
| [Roadmap](docs/roadmap.md) | 历史演进与方向索引 |

---

## License

[MIT](LICENSE) © hanrry2323
