# CCC 下阶段总体方案 — 多端对话壳 + 标准编排 Hub

> **状态**：已拍板（2026-07-20）· 对齐版本 `VERSION`（撰写时 v0.51.0）  
> **性质**：总体方案 / 北星文档；**先文档后代码**。冲突时：边界基线仍以 [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) 为准，本文管「下一步建什么」。  
> **验证仓**：先 `ccc-demo`，流程稳定后再覆盖真实业务仓。

---

## 1. 一句话

**Desktop（及以后网页 / 手机）做多端对话壳；Hub 做版本化编排 API；人只在「意图既定」处拍板，进队后流水线自动自进化。**

---

## 2. 已锁定决策

| 项 | 决定 |
|----|------|
| 半年主叙事 | 多端对话壳 + 标准编排 Hub |
| 第一刀验证 | `ccc-demo`（测试仓）→ 再铺真实项目 |
| 模型出口 | 对话 / product：MiniMax（可换 Claude 兼容）；dev：OpenCode 直连上游 |
| 中转站 | 已退役；不回退为默认路径 |
| 架构骨架 | **演进现有 Hub–Engine–board**，不开局重写 Temporal / LangGraph |

---

## 3. 人审 vs 自动（三句口径 · 硬边界）

1. **人确定意图与方案 → transfer；此后编排自动，不为「安心」加人批。**  
2. **人审只保留在：定稿 / 采纳提案、以及 abnormal / 资源失控时的止损。**  
3. **进程泄漏与槽爆炸按可靠性 P0 治；治好之前允许临时人工兜底，但不把兜底写成产品常态。**

### 3.1 分层（原则现在锁；细则后面长）

| 层 | 含义 | 人审？ |
|----|------|--------|
| **意图门**（进 Hub 前） | 定稿、旁路提案采纳、选仓与验收 | **必须**（唯一默认人审面） |
| **编排流水线**（backlog 后） | product → dev → reviewer/tester → kb → released | **默认全自动** |
| **机器门禁** | verdict / SPEC / DoD | **不是人审**；是自动质量闸 |
| **止损** | hang、泄漏、进程爆炸、abnormal | 通知 + 可人工介入；目标是技术修好后减少 |

**禁止**：把「逐步等人点批准」做成进队后的产品常态 —— 违背 Hub「意图既定后自进化」目标。

**延后约定（跑通后再写细）**：哪些提案可一键默认采纳、何种 abnormal 升级通知、稳定性 SLA 达标后减少人工兜底。

---

## 4. 工程化硬约束

1. **文档优先**：契约与方案先落 `docs/`，再改代码；版本看 `VERSION` + `CHANGELOG`。  
2. **commit / 远端**：语义化提交；合入前自检；Hub/Desktop 部署与仓版本对齐（见 [`../deploy/desktop.md`](../deploy/desktop.md)）。  
3. **文件夹卫生**：新建目录**只在项目根下、不超过一级**（例：`CCC/inbox/`、`docs/…`）。禁止 `~/散落目录`、禁止跨机绝对路径当契约。  
4. **契约版本化**：Hub API 以 **v1** 冻结字段与错误码；破坏性变更走 v2，客户端可并行探测。  
5. **状态在仓内 / 看板**：进度 SSOT = board 文件 + flow-events；不靠模型记忆。  
6. **旁路默认不进 backlog**：外部顾问产出 = 提案；采纳后才 transfer。

---

## 5. 目标架构（演进，非换骨）

```text
Clients:  Desktop →（后）Web →（后）Mobile
              │  Hub API v1（鉴权 · 幂等 · 错误码）
              ▼
         CCC Hub（控制面）
         transfer / flow / board / proposals(可选)
              │
         Engine + Board（编排面 · 自动流水线）
              ├ product / reviewer…（Claude 兼容 · skill/promote）
              └ dev（OpenCode）
              ▲
         inbox/（项目根下一级 · 可选）
         外部顾问提案 → Desktop 采纳 → transfer
```

社区对齐（2026）：Hub–Spoke 控制面、推理与编排分离、状态外置、HITL 只在故障线/意图门 —— **与现网一致**；不必为「更潮」推倒重来。

### 5.1 刻意不做（半年内）

- 主聊天搬回 Hub  
- Desktop 做成第二 IDE（文件树 / 内嵌终端 / MCP 大盘作主轴）  
- 旁路自动进 Engine 队列  
- 开局引入 Temporal / LangGraph 重写 Engine  
- 恢复 ai-loop-router 为默认出口  

---

## 6. 工作流切面（优先级）

| 优先级 | 切面 | 内容 | 成功标准 |
|--------|------|------|----------|
| **P0** | Hub API v1 | 冻结 transfer / flow snapshot+SSE / board 摘要；鉴权与错误码；文档 + 契约测 | 第二客户端可按文档对接 |
| **P0** | 投递可见性 | Desktop：`本机草稿` / `已投递` / `编排已受理`；失败可重试（本机落盘） | Hub 断线仍可聊；下达状态不谎报 |
| **P0** | 可靠性 | hang / 槽 / 泄漏 / OpenCode·Claude 进程爆炸治理 | 自动流水线可长时间无人值守 |
| **P1** | 榨模型 | promote、skill、身份与心智；低端模型撑高级任务 | **Phase3 已勾选**：`ccc-product` 反过拆 + fanout prompt complexity |
| **P2** | 提案旁路 | `inbox/`（项目根一级）+ Desktop 采纳；hmap / 外部免费顾问只作输入 | **Phase4 已勾选**：`smoke-inbox-adopt.sh`；未采纳不进板 |
| **P3** | 多端薄客户 | 网页 / 手机只消费 Hub API v1 | 不复制 Engine |

实现顺序：**契约与可靠性先于旁路 UI；旁路先于多端。**

---

## 7. Hub API v1（草案范围 · 细节实现期补齐）

最低集合（与现网对齐并文档化）：

| 能力 | 路径意向 | 备注 |
|------|----------|------|
| 定稿下达 | `POST /api/desktop/transfer` | 幂等键；意图门通过后进 backlog |
| 进度 | `GET …/flow/snapshot` + SSE `…/flow/events` | 右栏 / 多端只读 |
| 看板 | board 摘要 / 任务详情（经 Hub） | 不含主聊天 |
| 健康 | Hub / Board 探活 | 供客户端三态 |
| 提案（P2） | 列表 / 采纳→transfer | 采纳 = 意图门，不是流水线人批 |

聊天热路径：**留在各端本机 Agent（sidecar）**；Hub 不做主对话。

完整字段表：[`transfer-gate.md`](transfer-gate.md) · API 契约：[`hub-api-v1.md`](hub-api-v1.md)。

---

## 8. `ccc-demo` 验收（第一刀）

在真实业务仓之前，下列在 `ccc-demo` 必须绿：

1. Desktop 定稿 → transfer → epic 进 backlog  
2. Engine 自动扇出 → work → released（**无中途人批**）— **Phase5a 已勾选**：`scripts/smoke-ccc-demo-released.sh`  
3. Hub 短暂不可达：对话仍可用；恢复后 snapshot 对齐；失败 transfer 可重试  
4.（P2）写入一条 inbox 提案 → Desktop 采纳 → 再走 1–2  
5. 稳定性：连续跑 **N=3** 轮无槽泄漏 / 无失控残留进程（`scripts/smoke-ccc-demo-soak.sh`）

Phase 状态板：见 [`hub-shell-phase-status.md`](hub-shell-phase-status.md)。

通过后再覆盖 `xianyu` / `qb` 等注册业务仓。

---

## 9. 文档与仓库卫生清单

- [ ] 本文为下阶段北星；重大转向先改本文再改代码  
- [ ] `CHANGELOG` / `VERSION` 与发布说明同步  
- [x] 新目录仅项目根下一级；inbox = `CCC/inbox/`（禁止 `.ccc/inbox` 双轨）  
- [ ] Mac2017 / M1 部署 commit 对齐后再宣称「已上线」  
- [ ] 契约变更：先改 docs，再改 Hub，再改 Desktop  

---

## 10. 关联 SSOT

| 文档 | 用途 |
|------|------|
| [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) | 对话/编排边界 |
| [`ccc-desktop-architecture.md`](ccc-desktop-architecture.md) | Desktop 架构 |
| [`transfer-gate.md`](transfer-gate.md) | 定稿门禁 |
| [`flow-events.md`](flow-events.md) | 右栏事件 |
| [`../deploy/topology.md`](../deploy/topology.md) | 双机拓扑 |
| [`../VISION.md`](../VISION.md) | 产品叙事 |

---

## 11. 下一步（开干时）

Phase1–4 + 对话身份已收口。现行刀：**Phase5a released → Phase5b outbox → Phase6 真实仓**（见 phase-status）。

1. 代码变更引用本文章节号（如 `hub-shell-roadmap §8`）  
2. **不做**：P3 薄客户、Temporal 重写、主聊天回 Hub、旁路自动进队  

---

*撰写：2026-07-20 · 社区架构评估结论：现网 Hub–Spoke + 意图门 HITL 正确；拒绝开局换骨。*
