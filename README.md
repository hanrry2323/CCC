# CCC — Connect–Claude Code

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.71.0-blue.svg)](VERSION)
[![Release](https://img.shields.io/github/v/release/hanrry2323/CCC)](https://github.com/hanrry2323/CCC/releases/latest)

> **Loop Engineer：人定意图，系统自动编排与自主执行。**  
> 任意设备壳经 HTTP 直连 2017 单端服务；对话口接大脑 Agent；编排面（薄驱动 Engine + 文档流转 + 看板/HTTP）远端开发。

**完整介绍**：[`docs/INTRO.md`](docs/INTRO.md) · **叙事 SSOT**：[`docs/VISION.md`](docs/VISION.md) · **架构**：[`docs/architecture.md`](docs/architecture.md)  
**启动（Agent）**：[`STARTUP-BRIEF.md`](STARTUP-BRIEF.md) · **版本**：`VERSION`（v0.71.0）· **权威链**：[`docs/INDEX.md`](docs/INDEX.md) §0

> 2026-08-02 架构重构定稿：薄驱动 Engine + 文档流转 + 看板/HTTP + 2017 单端 + 任意设备壳。旧 `scripts/` 已退役归档；旧端口（7777 Hub / 7775 Board / 7788 sidecar / 7778 Cockpit）已退役。详见 [CHANGELOG#v0700](CHANGELOG.md)。

---

## CCC 是什么

**C**onnect — **C**laude **C**ode

CCC 不是「又一个 IDE」，也不是「角色超市」。它是一台 **Loop Engineer**：

| 层 | 做什么 |
|----|--------|
| **任意设备壳**（Desktop / 网页 / 手机） | 经 HTTP 直连 2017 :7788；对话/看板/运维/线路图四视图 |
| **2017 单端 :7788**（server/web/server.py） | HTTP API + 静态页；`/conversation` 接大脑 Agent |
| **薄驱动 Engine**（server/engine/） | 读取执行体注册表 → 派发 → 收单 → 状态机流转 |
| **看板服务端**（server/board/） | 从 `docs/dispatch/*.md` 解析任务卡 → 三视图 + 线路图 |

任务卡文档 = **唯一事实源**：`docs/dispatch/T<n>-*.md`，元数据行含 `状态：X` / `执行体：Y` / `日期：Z`。

---

## 30 秒看懂闭环

```text
任意设备壳 → HTTP 直连 2017:7788 → /conversation 聊意图
  → 写任务卡 docs/dispatch/T<n>-*.md
  → Engine 派发执行体（可后台 CLI 自动拉起 / 手动 GUI 挂起等人）
  → 收单 → 状态机流转：待分派 → 执行中 → 已回写 → 已关闭
  → 看板/线路图实时反映进度
```

任务卡状态机（契约 §2 五态）：

```text
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回（附问题清单）→ 待分派（人工重派）
```

---

## Quick Start

```bash
git clone https://github.com/hanrry2323/CCC.git
cd CCC

# 2017 生产端已部署两 launchd 常驻服务（T22 落地；board-scheduler 已收敛进 engine）：
# - com.ccc.web-server       → server/web/server.py :7788
# - com.ccc.engine           → server/engine/main.py

# 任意设备壳直连（默认免登录即用；服务端可配置恢复账号密码登录）
curl -s http://192.168.3.116:7788/health
```

本地开发：

```bash
# Python 语法检查
python -m py_compile server/engine/main.py

# 单测（新栈测试）
pytest server/tests/ -q --tb=short

# Ruff lint（CI 级，覆盖 server/）
ruff check server/ tests/

# 引擎单次扫描 + 收单
python3 -m server.engine.main --config server/config/config.env --once

# 看板导出（从 docs/dispatch/ 解析任务卡 → web/data/board.js）
python3 -m server.board.export

# HTTP API 服务启动（生产走 launchd plist）
python3 -m server.web.server --port 7788
```

详解：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)

---

## 仓库地图

| 路径 | 说明 |
|------|------|
| `server/` | ★ 新栈（2026-08-02 重构定稿）：engine / board / web / kb / config / deploy（relay/ 中转站已于 2026-08-24 退役拆除） |
| `server/engine/` | 薄驱动核心：dispatch / main / scheduler / store / task / cluster |
| `server/board/` | 看板服务端：loader / queries / export / models / scheduler |
| `server/web/` | HTTP API + 静态页：server.py / brain.py（大脑 Agent 代理） |
| `desktop/` | Desktop 壳（SwiftUI，任意设备壳之一） |
| `docs/dispatch/` | ★ 任务卡文档（唯一事实源） |
| `docs/INDEX.md` | 文档索引 SSOT（§0 重构决策 + 契约 v1 最高优先级） |
| `docs/architecture.md` | 架构概览 |
| `references/red-lines.md` | 红线 + X/R 系列 |
| `references/board-task-schema.md` | 任务卡文档契约 |
| `docs/archive/legacy-retired-2026-08-02/` | 旧栈归档（scripts/ 等，已退役，勿引用） |

---

## 工程纪律（摘要）

- **红线 11**：验收必须写 verdict 文件  
- **红线 12**：禁止 agent 擅自启用 CCC  
- **任务卡 = 唯一事实源**：`docs/dispatch/*.md`，状态机五态
- **零硬编码**：端口 / 路径 / 模型名 / 工具名走 `config.env` 与执行体注册表

---

## 文档

| 文档 | 读者 |
|------|------|
| [INDEX](docs/INDEX.md) | 先读 §0 权威链 |
| [architecture](docs/architecture.md) | 架构概览 |
| [VISION](docs/VISION.md) | 叙事 SSOT |
| [roadmap](docs/roadmap.md) | 当前方向 + 历史归档 |
| [GETTING-STARTED](docs/GETTING-STARTED.md) | 首次安装 |
| [STARTUP-BRIEF](STARTUP-BRIEF.md) | Agent 启动 |
| [CHANGELOG](CHANGELOG.md) | 版本历史 |

---

## License

[MIT](LICENSE) © hanrry2323
