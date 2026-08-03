# CCC Startup Brief

> **读完 = 知道 CCC 怎么用。** 其他文件按需 grep。目标：启动 token 可控。  
> **版本**：`VERSION`（**v0.70.0**）  
> **权威链**：[`docs/INDEX.md`](docs/INDEX.md) §0（重构决策定稿 + 契约 v1 最高优先级）  
> **索引**：[`docs/INDEX.md`](docs/INDEX.md) · **架构**：[`docs/architecture.md`](docs/architecture.md)

---

## 1. 一句话

**人定意图 → 写任务卡到 `docs/dispatch/` → 2017 Engine 派发执行体 → 收单回写看板 → 验收闭环；全程只认一个权威仓 + 一份任务卡文档。**

CCC = **Connect–Claude Code** = **Loop Engineer**  
**任意设备壳**（Desktop / 网页 / 手机）经 HTTP 直连 **2017 单端 :7788**；对话口接**大脑 Agent**（Claude Code CLI via 6100，带心智/工具/知识库）；编排面（**薄驱动 Engine + 文档流转 + 看板/HTTP**）远端开发。

**席位（硬）**：**Claude/OpenCode**=CCC 合入开发 · **Claude Code**=本机养机 + 日常维护 · **OpenCode**=Engine 写码槽 · **Codex**=知识/闲聊 · **Desktop**=任意设备壳。SSOT：[`docs/product/dev-channel.md`](docs/product/dev-channel.md)。  
**人格独立**：**Cursor ≠ Desktop Agent**；Desktop Plan「不写码」只约束桌面对话，不限制 Cursor。

**共识**：Demo ≠ 上线 ≠ 符合意图（行业共性）；共识必须写入权威链文档（`docs/INDEX.md` §0）再应用。  
**Vibe 真优势三句**：少而硬的意图 · 唯一权威路径 · 偏差默认用飞轮收——**不是**画布更细。

**勿再说**：「接很多 IDE」「先选 7 角色」「免费打头 / MiniMax 主力」「Claude Code 当开发主力」「旧 scripts/ 命令」「Hub :7777 / sidecar :7788」「能力包 / 角色分层」。

**4 个数字**：

| | |
|--|--|
| **2017 单端 `:7788`** | HTTP 直连：对话 / 看板 / 运维 / 线路图（**默认免登录**，`CCC_WEB_AUTH_REQUIRED=1` 可恢复账号密码） |
| **大脑 Agent `:6100`** | /conversation 调 2017 Claude Code CLI（Anthropic 出口，带心智/工具/知识库） |
| **Relay flash `:6102`** | 模型出口上游路由（中转站，OpenCode 写码槽走此） |
| **3 个 launchd 服务** | `com.ccc.web-server` + `com.ccc.engine` + `com.ccc.board-scheduler`（2017 常驻） |

---

## 2. 人机路径（优先）

```text
任意设备壳（Desktop / 网页 / 手机）
  → HTTP 直连 2017:7788（默认免登录，直连即聊）
  → /conversation 聊意图（大脑 Agent 带心智/工具/知识库）
  → 写任务卡到 docs/dispatch/T<n>-*.md
  → Engine 派发执行体（可后台 CLI 自动拉起 / 手动 GUI 挂起等人）
  → 收单 → 状态机流转（待分派 → 执行中 → 已回写 → 已关闭）
  → 看板/线路图视图实时反映进度
```

端口与账密：[`docs/ccc-hub-ports.md`](docs/ccc-hub-ports.md)（`ccc` / `ccc`）  
上手：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)  
架构概览：[`docs/architecture.md`](docs/architecture.md)  
部署拓扑：[`docs/deploy/topology.md`](docs/deploy/topology.md) · 2017 布局：[`docs/deploy/server-layout.md`](docs/deploy/server-layout.md)

---

## 3. 编排面：薄驱动 Engine（契约 §7 执行体注册表）

> 下表是 **Engine 调度的执行体角色**，按 `server/config/executors.json` 注册表配置派发。

| 角色 | 分类 | 当前绑定 | 干 |
|------|------|----------|-----|
| product | 可后台 CLI | Claude Code | 拆任务卡 → 子卡 |
| dev | 可后台 CLI | OpenCode | 写代码 → 提交 |
| reviewer | 可后台 CLI | Claude Code | 语义审查 → verdict |
| tester | 可后台 CLI | OpenCode | pytest + 验收清单 |
| ops | 手动 GUI | — | 健康检查（不动 board） |

**派发规则**：`可后台 CLI` → Engine 自动拉起；`手动 GUI` → 挂起等人；未知角色 → 不派发。  
**状态机 = 契约 §2 五态**：`待分派 → 执行中 → 已回写 → 已关闭`；失败路径 `执行中/已回写 → 打回（附问题清单）`，人工处理后 `打回 → 待分派` 重新派发；终态 `已关闭`。**非法状态转移一律抛 `IllegalTransitionError`。**

---

## 4. 控制面（2017 三服务常驻）

2017 已部署三个 launchd 常驻服务（T22 落地）：

| 服务 | 入口 | 职责 |
|------|------|------|
| `com.ccc.web-server` | `server/web/server.py :7788` | HTTP API + 静态页（对话/看板/运维/线路图） |
| `com.ccc.engine` | `server/engine/main.py` | 薄驱动主循环（派发 + 收单） |
| `com.ccc.board-scheduler` | `server/board/scheduler.py` | 只读巡检 + 导出 board.js |

```bash
# 健康检查
curl -s http://192.168.3.116:7788/health

# 引擎单次扫描 + 收单
python3 -m server.engine.main --config server/config/config.env --once

# 看板导出
python3 -m server.board.export
```

---

## 5. 看板（一行）

```text
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回（附问题清单）→ 待分派（人工重派）
```

任务卡文档 = 唯一事实源：`docs/dispatch/T<n>-*.md`，元数据行含 `状态：X` / `执行体：Y` / `日期：Z`。  
看板数据由 `server/board/loader.py` 从任务卡解析派生，不另建数据源。

---

## 6. 红线（极简）

全文：`references/red-lines.md`

致命：

- **1** 不动系统文件 / 密钥  
- **11** Verdict 必须落文件（口头 PASS 无效）  
- **12** 禁止 agent 自主启用 CCC  
- **R-15** 禁止 CCC 本体经看板自消费（平台改动用开发工具（Claude/OpenCode））  

---

## 7. 教训（5 条）

| # | 避坑 |
|---|------|
| 27 | `claude -p` 的 prompt 走 stdin |
| 28 | 口头 PASS ≠ 真 PASS |
| 32 | opencode 模型名带 provider 前缀 |
| 33 | 长 prompt 走 `--file` |
| 35 | 默认「执行器写码 + 审查门禁」 |

---

## 8. 模型（执行面）

```bash
# 大脑 Agent（对话口，2017 本机）
claude -p "<msg>" --output-format text
# env: ANTHROPIC_BASE_URL=http://127.0.0.1:6100 ANTHROPIC_MODEL=flash

# 写码槽（Engine dev）
opencode run --model loop/flash "<msg>"
```

Token 治理与分层见 `docs/model-tier-strategy.md`。

---

## 9. 懒加载

```bash
cat docs/VISION.md
cat docs/architecture.md         # 架构概览
cat docs/INDEX.md                # 文档索引（§0 重构决策 + 契约 v1）
grep -A 15 "## 红线 11" references/red-lines.md
python3 -m server.board.export   # 看板导出
```

**黄金规则**：Brief 够了 → 不够再 grep。

---

## 10. 调用链（1 行）

任意设备壳 → HTTP 直连 2017:7788 → /conversation 大脑 Agent 聊意图 → 写任务卡 `docs/dispatch/` → Engine 派发执行体（product=Claude / dev=OpenCode）→ 收单回写 → 已关闭。

---

**维护**：范式变更时同步 VISION + README + SKILL + INDEX §0（均链回本文或 VISION）。  
**约束**：禁止在 Engine 外并发依赖模块全局 `ROOT`（F-CON-03）。
