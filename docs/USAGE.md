# CCC USAGE — 三类用户指南

> 叙事：[`VISION.md`](VISION.md) · 安装：[`GETTING-STARTED.md`](GETTING-STARTED.md)  
> CCC = **Connect–Claude Code** · **Loop Engineer**（Hub 入口 + Engine 编排 + 工具路由）

---

## 1. Hub 用户 — 定意图、看闭环

### 适用

- 用浏览器完成对齐 / 定稿 / 转任务  
- 盯看板与控制台，而不是在第三方 Agent IDE 里编排  

### 推荐路径

1. 打开 `http://127.0.0.1:7777`（`ccc` / `ccc`）  
2. **对齐基线** →（可选）**下一步** → **定稿方案**  
3. **转任务** → 核标题 → 可选 Skill 软偏好 → **下达并开工**  
4. **看板**看流转；失败看控制台 / `ccc-failure-report.py`  
5. 需要自动跑队列：`bash scripts/ccc-autostart-guard.sh enable --start`  

### 你不需要

- 选择「产品经理 / 开发 / 测试」等角色  
- 背诵 Skill 名称（系统按任务注入；软偏好可选）  
- 打开 zcode / Qoder 等第三方壳做编排（Hub 已替代）  

### 控制面

| 模式 | 何时用 |
|------|--------|
| `disabled` / `ui` | 只聊天、只建卡 |
| `enabled` | 日常：只消费队列 |
| `invent` | 明确要自造/进化任务时 |

见 [`CONTROL.md`](CONTROL.md)。

---

## 2. Skill / 能力包消费者 — 在任务上挂偏好

- Hub 转任务卡：勾选 ≤3 个 Skill，或手写 id + 补充说明  
- 写入 `hints.skills`，注入 OpenCode/dev prompt（**软提示**；与 plan/scope 冲突时以后者为准）  
- 自建 Skill：放在 `~/.claude/skills/` 或项目 `.claude/skills/`（`GET /api/skills` 可扫描）  

阶段默认包索引：[`../skills/README.md`](../skills/README.md)

---

## 3. Maintainer — 改 CCC 本仓

1. 读 `STARTUP-BRIEF.md` + `VISION.md`  
2. 改代码前开 plan/phases（或走 Hub 定稿）  
3. `pytest tests/scripts/ -q` · `bash scripts/ccc-self-check.sh`  
4. 遵守 `references/red-lines.md` · 贡献见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)  

常用命令：

```bash
bash scripts/ccc-hub-dev.sh
python3 scripts/ccc-board.py index
bash scripts/ccc-autostart-guard.sh status
pytest tests/scripts/ -q --tb=short
```

---

## 4. 已废弃用法（文档中若仍出现，以本文为准）

| 旧说法 | 现状 |
|--------|------|
| 三角色 Plan/Exec/Verify 为主路径 | 已并入 Engine 阶段能力包 |
| 7 个 launchd 角色定时 | 已废止；Engine 串行 |
| 「接到任意 IDE」当主卖点 | Hub 为入口；IDE/CLI 仅为执行器 |
| 用户先选角色再干活 | 禁止作为产品叙事 |

---

## 5. 红线（用户侧必知）

- **11**：验收看 verdict 文件  
- **12**：不要让 agent 偷偷 `enable`/`invent` CCC  

全文：`references/red-lines.md`
