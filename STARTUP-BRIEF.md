# CCC Startup Brief

> **读完 = 知道 CCC 怎么用。** 其他文件按需 grep。目标：启动 token 可控。  
> **版本**：`VERSION`（**v0.71.0**）  
> **渠道真值以本文为准 · 2026-09-03 更新**：2017 所有模型通道统一经 M1 中转 `3456 → LiteLLM → Code`；`6100/6102` 与 opencode.ai 直连均为退役历史路径。看板已启用鉴权，匿名读接口返回 401。  
> **权威链**：[`docs/INDEX.md`](docs/INDEX.md) §0（重构决策定稿 + 契约 v1 最高优先级）  
> **文档怎么写 / 项目注册**：[`docs/DOC-PROTOCOL.md`](docs/DOC-PROTOCOL.md) · [`docs/projects/registry.yaml`](docs/projects/registry.yaml)  
> **Cursor 已弃用**（2026-08-14，入口 `CURSOR.md` 已移除）  
> **索引**：[`docs/INDEX.md`](docs/INDEX.md) · **架构**：[`docs/architecture.md`](docs/architecture.md)

---

## 1. 一句话

**人定意图 → 写任务卡到 `docs/dispatch/` → 2017 Engine 派发执行体 → 收单回写看板 → 验收闭环；全程只认一个权威仓 + 一份任务卡文档。**

CCC = **Connect–Claude Code** = **Loop Engineer**  
**任意设备壳**（Desktop / 网页 / 手机）经 HTTP 直连 **2017 单端 :7788**；对话口接**大脑 Agent**（统一经 M1 中转 3456 的 Code）；编排面（**薄驱动 Engine + 文档流转 + 看板/HTTP**）远端开发。

**席位（硬，2026-08-07 · 北星）**：
- **开发/维护** = 前段 DSH；**审核/验收/合入/部署** = 后段 CC CLI（phase2）
- **管理席** = 可替换调度插件（现役外脑）
- **合入** = 默认 phase2 自动执行；老板保留否决/打回权
- **绑定**只认 `server/config/executors.json`，随时可换
- **HTTP 看板** = 实时面；Desktop 暂缓

SSOT：[`docs/product/north-star-slice.md`](docs/product/north-star-slice.md) · [`docs/product/dev-channel.md`](docs/product/dev-channel.md) · [`docs/product/hub-context-sop.md`](docs/product/hub-context-sop.md) · [`CLAUDE.md`](CLAUDE.md)。  
**cwd 铁律**：CCC 权威仓 = 2017 `/Users/fan/program/CCC`；M1 副本已退役（2026-08-22）。  
**北星命令**：`scripts/plan-to-cards.sh` · `GET /board/ready_for_merge` · `scripts/approve-merge.sh` / `scripts/card-evidence.sh`。  
**合入硬路由**：合入默认由 phase2 自动执行；老板保留否决/打回；ready = 分支信封 `git show origin/<分支>:<卡>` 含机审通过；**禁止**代写机审区。

**共识**：Demo ≠ 上线 ≠ 符合意图；共识必须写入权威链文档（`docs/INDEX.md` §0）再应用。

**勿再说**：「接很多 IDE」「先选 7 角色」「Hub :7777 / Board :7775 / sidecar」「旧 scripts/ccc-engine」「能力包 / 角色分层」「M1 跑 7788/Engine」「Desktop 必经」。现役绑定只认 `executors.json`；DSH/CC CLI 为现役插件，OpenCode/Codex/桌面端为退役/休眠。

**4 个数字**：

| | |
|--|--|
| **2017 单端 `:7788`** | HTTP 直连：对话 / 看板 / 运维 / 线路图（已启用鉴权；匿名读请求返回 401） |
| **M1 中转 `:3456`** | LiteLLM → Code：2017 对话、DSH 执行体与机审统一主通道 |
| **6100 / 6102** | 旧中转路径，进程已停用，仅保留历史记录 |
| **2 个 launchd 服务** | `com.ccc.web-server` + `com.ccc.engine`（`board-scheduler` 已收敛进 engine） |

---

## 2. 人机路径（优先）

```text
任意设备壳（Desktop / 网页 / 手机）
  → HTTP 直连 2017:7788（需登录 token）
  → /conversation 聊意图（大脑 Agent，经 3456 Code）
  → 写任务卡到 docs/dispatch/<prefix>/<prefix><NNN>-*.md
  → 前段 DSH 开发+前置机审 → 已回写
  → 后段 CC CLI（phase2）审核/验收/合入/部署 → 已关闭
  → 看板/线路图视图实时反映进度
```

现行标准链路：老板/外脑拟指令 → 前段 DSH 开发+前置机审 → 已回写 → 后段 CC CLI（phase2）审核/验收/合入/部署 → 已关闭。

上手：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)  
架构：[`docs/architecture.md`](docs/architecture.md)  
部署：[`docs/deploy/topology.md`](docs/deploy/topology.md)

---

## 3. 编排面：薄驱动 Engine（契约 §7）

> 按 `server/config/executors.json` 派发；工具是可替换插件，现役前段 DSH / 后段 CC CLI。

| 角色语义 | 分类 | 现行绑定 | 干 |
|----------|------|----------|-----|
| 开发 / 维护 | 可后台 CLI | **DSH**（前段） | 改仓 + 前置机审 → 已回写 |
| 审核 / 验收 / 合入 / 部署 | 可后台 CLI | **CC CLI（phase2）**（后段） | 已回写 → 已关闭 |
| 管理席 | — | 可替换调度插件（现役外脑） | 拟指令 / 调度 / 监督 |

**派发规则**：`可后台 CLI` → Engine 自动拉起；`手动 GUI` → 挂起等人。  
**状态机**：`待分派 → 执行中 → 已回写 → 已关闭`；失败 `→ 打回 → 待分派`。非法转移抛 `IllegalTransitionError`。

---

## 4. 控制面（2017 两服务常驻）

| 服务 | 入口 | 职责 |
|------|------|------|
| `com.ccc.web-server` | `server/web/server.py :7788` | HTTP API + 静态页 |
| `com.ccc.engine` | `server/engine/main.py` | 派发 + 收单 + 看板调度 |

```bash
curl -s http://192.168.3.116:7788/health
python3 -m server.engine.main --config server/config/config.env --once
# board-scheduler 已收敛进 engine
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
- **R-15** 禁止 CCC 本体经看板自消费（平台合入走 OpenCode 开发 → 机审 → 「合入批准」）  

---

## 7. 模型（执行面）

```bash
# 大脑 / 执行体（2017，via M1 中转 3456）
出口变量以 `config.env` / wrapper 为准；`claude -p` 裸调不作机审通道。
```

按注册表拉起现役插件；DSH/CC CLI 可替换，OpenCode/Codex/桌面端为退役/休眠。

---

## 8. 懒加载

```bash
# Cursor 已弃用（2026-08-14），难度突击由 Claude Code/OpenCode 顶替
cat docs/architecture.md
cat docs/INDEX.md                # §0 权威链
cat docs/DOC-PROTOCOL.md         # 写哪里 / 项目注册
grep -A 15 "## 红线 11" references/red-lines.md
python -m server.board.validate docs/dispatch
```

**黄金规则**：Brief 够了 → 不够再 grep。Hub 时期文档（VISION 待核段、旧 product/*）一律降为史。

---

## 9. 调用链（1 行）

老板/外脑指令 → DSH 前段开发+前置机审 → 已回写 → phase2 CC 后段审核/验收/合入/部署。

---

**维护**：范式变更时同步 `.cursor/rules/` + INDEX §0 + 本 Brief（CURSOR.md 已随 Cursor 弃用移除）。  
**约束**：禁止在 Engine 外并发依赖模块全局 `ROOT`（F-CON-03）。
