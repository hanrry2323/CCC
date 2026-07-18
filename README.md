# CCC — Connect–Claude Code

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.50.0-blue.svg)](VERSION)
[![Release](https://img.shields.io/github/v/release/hanrry2323/CCC)](https://github.com/hanrry2323/CCC/releases/latest)

> **Loop Engineer：人定意图，系统自动编排与自主执行。**  
> 主入口 **CCC Desktop**（SwiftUI 三栏）；自由编排 + 多执行面；Skill + Prompt 即角色——用户不选角色、不背 Skill。

**完整介绍**：[`docs/INTRO.md`](docs/INTRO.md) · **叙事 SSOT**：[`docs/VISION.md`](docs/VISION.md) · **Desktop 架构**：[`docs/product/ccc-desktop-architecture.md`](docs/product/ccc-desktop-architecture.md)  
**启动（Agent）**：[`STARTUP-BRIEF.md`](STARTUP-BRIEF.md) · 版本：`VERSION`  
**Release**：[v0.50.0](docs/releases/v0.50.0.md)（对内多仓里程碑）

---

## 截图导览（操作流程）

> 将截图放入 [`docs/assets/intro/`](docs/assets/intro/) 后即可点亮下列预览。分镜与旁白：[`docs/INTRO-WALKTHROUGH.md`](docs/INTRO-WALKTHROUGH.md)。

| 步骤 | 文件 | 一句话 |
|------|------|--------|
| 1 | `01-hub-home.png` | 入口是 Desktop（网页 Hub 仅运维） |
| 2 | `02-quick-actions.png` | 对齐 / 下一步 / 定稿 / 转任务 |
| 3 | `03-dispatch-block.png` | 定稿输出可执行契约 |
| 4 | `04-dispatch-card.png` | 下达并开工 + Skill 软偏好 |
| 5 | `05-board.png` | Loop 在看板上可见 |
| 6 | `06-console.png` | 失败可重开、控制面可见 |

（截图就位后可在此用 `![...](docs/assets/intro/01-hub-home.png)` 嵌入。）

---

## CCC 是什么

**C**onnect — **C**laude **C**ode

CCC 不是「又一个 IDE」，也不是「角色超市」。它是一台 **Loop Engineer**：

| 层 | 做什么 |
|----|--------|
| **Desktop（对话面）** | 左项目 / 中方案对话 / 右编排流程；定稿 → 转任务（仅 epic） |
| **Engine + Board（编排面）** | 自由扇出 work、赋身份与执行面；看板闭环 |
| **Executors（执行面）** | 默认 OpenCode；python / ollama / cli 可插拔 |

仓库中的 `skills/ccc-*` 是 **Engine 阶段默认能力包**（不是给用户点选的角色列表）：

```text
任务意图 → 路由工具 → Skill + Prompt = 本次角色（无穷）
```

---

## 垂直行业：同一底座，换上行业资产

```text
CCC + 爬虫/DB/worker + Domain Skill + 自定义快捷键
  = 垂直 AI 工具
```

首个样板蓝图（医药采价调度 **QX**）：[`docs/vertical-qx.md`](docs/vertical-qx.md)。  
完整故事见 [`docs/INTRO.md`](docs/INTRO.md) §5–6。

---

## 30 秒看懂闭环

```text
对齐 → 定稿 → 转任务 → Engine 自动编排
  → 开发 → 验收 →（失败则重试/重开）→ 归档 → 可进化
```

```text
backlog(epic 大卡常驻)
  → Claude 扇出 → planned(work) → in_progress → testing → verified → released
  → 子卡全 released → 大卡 done 沉底
```

---

## Quick Start

```bash
git clone https://github.com/hanrry2323/CCC.git
cd CCC

bash scripts/install-board-plist.sh --start
bash scripts/install-hub-plist.sh --start

open http://127.0.0.1:7777
# 默认账密：ccc / ccc   （详见 docs/ccc-hub-ports.md）
```

1. **对齐基线** → **定稿方案** → **转任务** → **下达并开工**  
2. 自动跑队列：`bash scripts/ccc-autostart-guard.sh enable --start`  

详解：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)

---

## 和谁不一样

| | Chat | OpenCode 等执行器 | ECC 类角色工坊 | **CCC** |
|--|------|-------------------|----------------|---------|
| 入口 | 对话 | CLI / 编辑器 | 选角色 | **Desktop** |
| 编排 | 无 | 弱 | 人工为主 | **Engine Loop** |
| 角色 | 无 | 无 | 固定一堆 | **任务生成（无穷）** |
| 验收 | 口头 | 自测 | 看产品 | **verdict 文件门禁** |
| 垂直扩展 | 难 | 脚本堆砌 | 再造角色 | **挂资产 + 快捷键** |

---

## 仓库地图

| 路径 | 说明 |
|------|------|
| `docs/INTRO.md` | 对外完整介绍 |
| `docs/VISION.md` | 产品叙事 SSOT |
| `desktop/` | CCC Desktop（SwiftUI 主客户端） |
| `scripts/chat_server/` | Center Server API + 网页运维 Hub |
| `scripts/ccc-engine.py` | Loop 主循环 |
| `scripts/ccc-board.py` | 看板与阶段能力调度 |
| `skills/ccc-*/` | 阶段默认能力包 |
| `docs/CONTROL.md` | 控制面 |

---

## 工程纪律（摘要）

- **红线 11**：验收必须写 verdict 文件  
- **红线 12**：禁止 agent 擅自启用 CCC  
- **控制面默认 `disabled`**  

---

## 文档

| 文档 | 读者 |
|------|------|
| [完整介绍 INTRO](docs/INTRO.md) | 所有人 |
| [VISION](docs/VISION.md) | 定位 SSOT |
| [Walkthrough](docs/INTRO-WALKTHROUGH.md) | 截图分镜 |
| [QX 竖切](docs/vertical-qx.md) | 商用样板 |
| [Getting Started](docs/GETTING-STARTED.md) | 首次安装 |
| [USAGE](docs/USAGE.md) | 日常使用 |
| [STARTUP-BRIEF](STARTUP-BRIEF.md) | Agent |
| [CONTRIBUTING](CONTRIBUTING.md) | 贡献者 |
| [CHANGELOG](CHANGELOG.md) | 版本历史 |

---

## License

[MIT](LICENSE) © hanrry2323
