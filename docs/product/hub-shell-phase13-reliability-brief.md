# Hub-Shell Phase13 — 编排可靠性门禁（开发 Brief）

> **性质**：需求 / 验收 brief（非实现说明书）  
> **日期**：2026-07-21 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) §6 P0 可靠性 · §11  
> **版本基线**：根目录 `VERSION` = **v0.52.1** · 三端应对齐同一 `main` commit  
> **执行者**：Claude Code（ops 通道）在 **main 上直接开发**  
> **终验者**：规划方（Cursor/Hub Agent）复跑验收命令后收口状态板

---

## 0. 你是谁、怎么干（强制）

1. 在 CCC 仓 **`main` 上直接开发**，**不要开分支**。  
2. **技术方案由你自定**；本文只规定背景、目标、硬边界、验收。  
3. 开发过程：**自己跑验收 → 语义化 commit → 可推远端**；每步可回滚。  
4. 自称「完成」无效；以文末 **验收命令全绿** 为准。终验人会再跑一遍。  
5. 开始前先读：`STARTUP-BRIEF.md`、本文、`docs/product/hub-shell-roadmap.md` §3–§6、`scripts/engine/hang.py`、`scripts/engine/slots.py`、`scripts/smoke-ccc-demo-soak.sh`、`scripts/smoke-hub-shell-gate.sh`。  
6. 冲突时：边界基线 [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) > 本文 > 个人偏好。

---

## 1. 背景

### 1.1 产品位置

CCC = 对话面（M1 Desktop + sidecar）定意图产 epic；编排面（Mac2017 Hub + Engine + Board）自动跑完。  
人审只在意图门；进队后默认全自动。见路线图 §3。

### 1.2 已完成（不要重做）

| 阶段 | 含义 |
|------|------|
| Wave1–4 Phase1–12 | Hub API / soak / inbox / 真实仓 qb·hp·xianyu / 止损最小可见 / 业务向意图 |
| v0.52.1 | gitignore 假绿门禁、transfer 空响应重试、`smoke-hub-shell-gate` |

状态板：[`hub-shell-phase-status.md`](hub-shell-phase-status.md)。

### 1.3 为何现在做 Phase13

路线图 §6 **P0 可靠性**仍是北星硬项：hang / 槽 / 泄漏 / OpenCode·Claude 进程爆炸。  
Phase2 已有 `smoke-ccc-demo-soak.sh`（N=3 + orphan_delta），但：

- 尚未收成「可周检、可回归、缺口有文档」的 **可靠性门禁包**；  
- hang / 死 pid / 槽计数漂移 / 主循环卡住 等，缺统一口径与可重复探针；  
- 临时人工兜底可以，但**不能**继续当产品常态（路线图 §3）。

本阶段目标：**把可靠性变成可测、可宣称、可周跑的门禁**，而不是再堆一轮「感觉稳了」。

---

## 2. 目标（用户 / 运维可感知）

完成 Phase13 后，应同时满足：

1. **无人值守可声称有据**：有一份 Phase13 文档写清「测了什么、没测什么、失败时人怎么介入」。  
2. **周检一条命令**（或明确分层）：本地/对 Mac2017 能跑绿，结果可解读（orphan / slot / hang 相关断言）。  
3. **已知泄漏类故障有自动或半自动收敛路径**：死 pid 文件、槽位幽灵占用、hang 超限后的任务命运——行为可测、可文档化。  
4. **不扩大人审面**：不引入逐步批准；止损仍是通知 + 可人工介入（Phase9 已做最小可见，本阶段可补工程侧，不重做通知中心）。

---

## 3. 范围

### 3.1 必须做（What）

任选实现路径，但交付必须覆盖：

| # | 需求 | 成功标准（验收语言） |
|---|------|----------------------|
| A | **可靠性门禁脚本** | 新增或扩展现有 smoke（可挂到 `smoke-hub-shell-gate` 的一层，或独立 `smoke-*-reliability*.sh`），对 Mac2017（或文档标明的环境）断言：浸泡前后 orphan 不恶化；槽/死 pid 有明确检查 |
| B | **hang / 槽 / 死 pid 行为可测** | 至少 1 组 **单元或集成测** 覆盖现有 `engine/hang.py`、`engine/slots.py`（或你抽取的辅助模块）中与「回收 / 重试上限 / 计数一致性」相关的逻辑；禁止只改文档不测 |
| C | **运维可读口径** | `docs/product/hub-shell-phase13-reliability.md`（验收记录，绿后写）说明：命令、环境变量、PASS/FAIL 含义、失败时推荐动作（kickstart / 清 pid / 看 abnormal） |
| D | **状态板收口** | `hub-shell-phase-status.md` 增加 Phase13 一行 = green + commit；`hub-shell-roadmap.md` §11 一句指向本阶段已完成 |
| E | **CHANGELOG** | `[Unreleased]` 或你 bump 的版本节记录本阶段（若 bump `VERSION`，须跑通 `scripts/check-version-sync.py` 并同步文档中的版本字符串） |

### 3.2 明确不做（Don't）

- P3 多端薄客户 / 网页主聊天 / 手机客户端  
- Temporal / LangGraph 重写 Engine  
- 主聊天搬回 Hub；恢复 ai-loop-router  
- 旁路提案自动进 backlog  
- 逐步人批流水线  
- 通知中心 / 推送渠道（Phase9 最小可见已够；本阶段不扩产品通知）  
- Desktop 做成第二 IDE（文件树 / 终端 / MCP 大盘作主轴）  
- 对 **CCC orch 看板** 投业务 epic（R-15）；验证只用 **ccc-demo**（或已注册 app，且走 transfer，不手改 CCC `.ccc/board` 业务卡）  
- 改系统文件、密钥、`~/.env`；擅自把 control 打到 `invent`  
- 大范围无关重构、顺手「优化桌面 UI」——桌面若必须动，仅限可靠性可见性的最小补强，并在 Phase13 文档写明

### 3.3 环境假设

| 端 | 角色 |
|----|------|
| M1 | 对话 / 改 CCC 仓 / 跑部分单测；Desktop + sidecar |
| Mac2017 | Hub + Engine + Board；编排 SSOT；soak / live smoke 主战场 |
| 验证仓 | 优先 `ccc-demo` |

改 Hub/Engine 后须在文档写清：**Mac2017 `git pull` + kickstart**（chat-server / engine / board 按需）。  
改 Desktop 后须 **package-baseline 装机** 才可宣称 Desktop 侧完成（若本阶段未改 Desktop，写明「N/A」）。

---

## 4. 工程约束（红线摘要）

- 语义化 commit；**不要** `--no-verify` / force push / 改 git config。  
- 契约变更：先 `docs/`，再代码。  
- 新目录只在项目根下一级（已有 `scripts/` `docs/` `tests/` 优先）。  
- Hub API 破坏性变更走 v2；本阶段优先不破 v1 字段。  
- 控制面：保持 `enabled` + `invent_hard_disabled` + `queue_consumer_only` 心智；空板闲置正常。

---

## 5. 验收清单（你自己跑绿；终验人复跑）

### 5.1 必跑

```bash
# 在 CCC 仓根
python -m py_compile scripts/ccc-engine.py scripts/engine/hang.py scripts/engine/slots.py
ruff check scripts/engine/ scripts/ccc-engine.py tests/scripts/ --quiet || true   # 若你改了这些路径则必须无新错
pytest tests/scripts/ -q --tb=short -k "hang or slot or reliability or soak or orphan" 
# 若上述 -k 无收集到用例：你必须新增测并保证能被合理 -k 命中，或在 Phase13 文档写明确切 pytest 路径

# 语法自检（按你改动的 sh）
bash -n scripts/smoke-ccc-demo-soak.sh
# 以及你新增/修改的 smoke-*.sh

# 现有门禁（本机或对 2017；按脚本要求设 CCC_SERVER）
CCC_SERVER=http://192.168.3.116:7777 CCC_HUB_SHELL_TIER=fast bash scripts/smoke-hub-shell-gate.sh

# 可靠性浸泡（允许耗时；N 默认 3）
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-ccc-demo-soak.sh
```

若你扩展了 gate 的 reliability tier，在 Phase13 文档写明应用的 `CCC_HUB_SHELL_TIER=` 值，并保证终验人按同一命令可复现。

### 5.2 完成定义（DoD）

- [ ] §3.1 A–E 均有对应交付  
- [ ] §5.1 命令在文档记录的环境上全绿（贴关键输出摘要到 Phase13 验收文档）  
- [ ] `git status` 干净或仅含你声明的未跟踪噪音说明  
- [ ] 终验人未介入前，你已自我对照本文 §3.2 不做清单  

### 5.3 版本

- 默认：**不强制** bump `VERSION`；若改动面大、你认为应发 **v0.52.2** 或 **v0.53.0**，可以 bump，但必须同步 `CHANGELOG` + `check-version-sync.py` + 相关文档中的版本字符串。  
- 不 bump 则只写 CHANGELOG `[Unreleased]`。

---

## 6. 建议工作顺序（可调整，供你判断）

1. 摸底：跑一遍现有 soak + 读 hang/slots；列出「已有能力 vs 缺口」写在 Phase13 验收文档草稿。  
2. 补测 / 补脚本 / 补收敛逻辑（按缺口，最小改动）。  
3. 接到 gate 或独立 smoke；本地 + 2017 验证。  
4. 更新状态板、roadmap §11、CHANGELOG；语义化 commit。  
5. 若动了 2017 热路径：文档写清 pull/kickstart；可在 commit message 提醒。

---

## 7. 完成时请回复规划方的格式

```text
Phase13 DONE
- HEAD: <short sha>
- VERSION: <v… 或 unchanged>
- Commits: <短列表>
- 验收命令与结果摘要: …
- 双机对齐: 已 pull+kickstart / 未改 Hub / 待规划方同步
- 风险与未测: …
```

---

## 8. 关联

| 文档 | 用途 |
|------|------|
| [`hub-shell-roadmap.md`](hub-shell-roadmap.md) | 北星 |
| [`hub-shell-phase-status.md`](hub-shell-phase-status.md) | 状态板 |
| [`hub-shell-phase9-stoploss.md`](hub-shell-phase9-stoploss.md) | 止损可见（勿重复造通知） |
| [`../deploy/desktop.md`](../deploy/desktop.md) | 三端对齐清单 |
| `scripts/engine/hang.py` · `slots.py` · `active_tasks.py` | 热路径 |
| `scripts/smoke-ccc-demo-soak.sh` · `smoke-hub-shell-gate.sh` | 现有门禁 |

---

*Brief 作者：规划方 · 实现与方案：执行方 Claude · 终验：规划方*
