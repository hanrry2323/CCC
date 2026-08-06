# CCC Startup Brief

> **读完 = 知道 CCC 怎么用。** 其他文件按需 grep。目标：启动 token 可控。  
> **版本**：`VERSION`（**v0.70.0**）  
> **权威链**：[`docs/INDEX.md`](docs/INDEX.md) §0（重构决策定稿 + 契约 v1 最高优先级）  
> **Cursor 入口**：[`CURSOR.md`](CURSOR.md) · **仓内规则**：`.cursor/rules/`（2026-08-05 新栈）  
> **索引**：[`docs/INDEX.md`](docs/INDEX.md) · **架构**：[`docs/architecture.md`](docs/architecture.md)

---

## 1. 一句话

**人定意图 → 写任务卡到 `docs/dispatch/` → 2017 Engine 派发执行体 → 收单回写看板 → 验收闭环；全程只认一个权威仓 + 一份任务卡文档。**

CCC = **Connect–Claude Code** = **Loop Engineer**  
**任意设备壳**（Desktop / 网页 / 手机）经 HTTP 直连 **2017 单端 :7788**；对话口接**大脑 Agent**（Claude Code CLI via 6100）；编排面（**薄驱动 Engine + 文档流转 + 看板/HTTP**）远端开发。

**席位（硬，2026-08-06）**：
- **Claude Code** / **OpenCode**（2017）= 可后台 CLI 执行体（flash/6100 vs code/6102；卡头绑定）
- **Codex** = 自研驱动者 + 系统总维护 + 验收席（出卡 / 把控 / 独立验收）
- **M1 IDE** = 开发智能中枢（打开 CCC 仓 + 已注册能力）
- **Cursor / Trae** = 了解 / 讨论 / 排查 / 文档对齐
- **HTTP 看板/运维** = 人机实时面（主路径）
- **Desktop** = 壳（**暂缓**，非主路径）

SSOT：[`docs/product/dev-channel.md`](docs/product/dev-channel.md) · [`CURSOR.md`](CURSOR.md) · qx-map `ide/tool-roles.md`。  
**人格独立**：**Cursor ≠ Desktop Agent**；Desktop Plan「不写码」只约束桌面对话。

**共识**：Demo ≠ 上线 ≠ 符合意图；共识必须写入权威链文档（`docs/INDEX.md` §0）再应用。

**勿再说**：「接很多 IDE」「先选 7 角色」「Hub :7777 / Board :7775 / sidecar」「旧 scripts/ccc-engine」「能力包 / 角色分层」「OpenCode 已禁用」「M1 跑 7788/Engine」「Desktop 必经」。

**4 个数字**：

| | |
|--|--|
| **2017 单端 `:7788`** | HTTP 直连：对话 / 看板 / 运维 / 线路图（默认免登录，`CCC_WEB_AUTH_REQUIRED=0`） |
| **大脑 / Claude Code `:6100`** | Anthropic 出口 flash：对话 + Claude Code 执行体 |
| **Relay / OpenCode `:6102`** | code 档上游路由（OpenCode 等） |
| **3 个 launchd 服务** | `com.ccc.web-server` + `com.ccc.engine` + `com.ccc.board-scheduler`（仅 2017） |

---

## 2. 人机路径（优先）

```text
任意设备壳（Desktop / 网页 / 手机）
  → HTTP 直连 2017:7788（默认免登录）
  → /conversation 聊意图（大脑 Agent）
  → 写任务卡到 docs/dispatch/T<n>-*.md
  → Engine 派发 Claude Code（可后台 CLI）/ 手动 GUI 挂起等人
  → 收单 → 五态流转（待分派 → 执行中 → 已回写 → 已关闭）
  → 看板/线路图视图实时反映进度
```

自研期标准链路：Codex 出卡 → push main → 2017 pull → Engine 派发 → worktree `ccc-dev-ws-tNN` → Codex 验收 → 合入部署。

上手：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)  
架构：[`docs/architecture.md`](docs/architecture.md)  
部署：[`docs/deploy/topology.md`](docs/deploy/topology.md)

---

## 3. 编排面：薄驱动 Engine（契约 §7）

> 按 `server/config/executors.json` 派发。**现行生产绑定以 2017 实机为准**；仓内 example 含 Claude Code + OpenCode 双 CLI。

| 角色语义 | 分类 | 现行绑定 | 干 |
|----------|------|----------|-----|
| 开发 / 写码 | 可后台 CLI | **Claude Code** / **OpenCode** | 按任务卡改仓 → commit/push |
| 维护 | 可后台 CLI | Claude Code（或 OpenCode） | 运维/修复类 |
| 管理席 | — | Codex | 出卡 / 裁决（不执行） |
| 验收席 | — | Codex | 独立验收（不执行） |
| ops | 手动 GUI | — | 健康检查（挂起等人） |

**派发规则**：`可后台 CLI` → Engine 自动拉起；`手动 GUI` → 挂起等人。  
**状态机**：`待分派 → 执行中 → 已回写 → 已关闭`；失败 `→ 打回 → 待分派`。非法转移抛 `IllegalTransitionError`。

---

## 4. 控制面（2017 三服务常驻）

| 服务 | 入口 | 职责 |
|------|------|------|
| `com.ccc.web-server` | `server/web/server.py :7788` | HTTP API + 静态页 |
| `com.ccc.engine` | `server/engine/main.py` | 派发 + 收单 |
| `com.ccc.board-scheduler` | `server/board/scheduler.py` | 只读巡检 + 导出 |

```bash
curl -s http://192.168.3.116:7788/health
python3 -m server.engine.main --config server/config/config.env --once
python3 -m server.board.export
python -m server.board.validate docs/dispatch
```

---

## 5. 看板（一行）

```text
待分派 → 执行中 → 已回写 → 已关闭
              ↓        ↑
            打回 → 待分派（人工重派）
```

任务卡 = 唯一事实源：`docs/dispatch/T<n>-*.md`。看板由 `server/board/loader.py` 派生。

---

## 6. 红线（极简）

全文：`references/red-lines.md`

- **1** 不动系统文件 / 密钥  
- **11** Verdict 必须落文件  
- **12** 禁止 agent 自主启用 CCC  
- **R-15** 禁止 CCC 本体经看板自消费（平台合入走 Claude Code 执行体 + Codex 验收）  

---

## 7. 模型（执行面）

```bash
# 大脑 / 执行体（2017，via 6100）
ANTHROPIC_BASE_URL=http://127.0.0.1:6100 ANTHROPIC_MODEL=flash \
  claude -p "<msg>" --output-format text
```

OpenCode 与 Claude Code 均为可后台 CLI；按卡头绑定与注册表拉起（勿写「已禁用」）。

---

## 8. 懒加载

```bash
cat CURSOR.md                    # Cursor 角色与现况
cat docs/architecture.md
cat docs/INDEX.md                # §0 权威链
grep -A 15 "## 红线 11" references/red-lines.md
python -m server.board.validate docs/dispatch
```

**黄金规则**：Brief 够了 → 不够再 grep。Hub 时期文档（VISION 待核段、旧 product/*）一律降为史。

---

## 9. 调用链（1 行）

任意设备壳 → HTTP 直连 2017:7788 → /conversation → 写任务卡 `docs/dispatch/` → Engine 派发 **Claude Code** → 收单回写 → 已关闭。

---

**维护**：范式变更时同步 `CURSOR.md` + `.cursor/rules/` + INDEX §0 + 本 Brief。  
**约束**：禁止在 Engine 外并发依赖模块全局 `ROOT`（F-CON-03）。
