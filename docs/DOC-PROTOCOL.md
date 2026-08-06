# CCC 文档写入规范（DOC-PROTOCOL）

> **权威入口**：[`INDEX.md`](INDEX.md) §0 → 本页。  
> **目的**：用更少的文档管事；谁都能写，但必须落在规定路径，禁止 agent 到处翻、到处新建。

---

## 0. 四条硬原则

1. **同一事实只存一处**；第二份只能是派生，或文首标明「史」。
2. **先问落点再写**：下表没有的路径 = **禁止新建**；应归档或并入现有页。
3. **项目档案一页封顶**：每个可出卡前缀在 CCC 仓只维护 `docs/projects/<prefix>/README.md`；业务深文写在业务仓，不在 CCC 复制。
4. **卡 ≠ 文档**：开发工作只出 [`dispatch/`](dispatch/) 任务卡；项目存档 / 线路意向不进卡正文堆历史。

---

## 1. 落点表（写哪里）

| 你要写的 | 写这里 | 怎么写 |
|----------|--------|--------|
| 平台共识 / 权威裁决 | 先改 [`INDEX.md`](INDEX.md) §0，再改被引用文 | 短、可裁决冲突；禁止只留在聊天 |
| 下一程意向（未出卡） | [`roadmap.md`](roadmap.md)「下一程挂账」 | **一行**意图 + 备注；未出卡不写长文 |
| 注册 / 改项目 | [`projects/registry.yaml`](projects/registry.yaml) + 对应 [`projects/<prefix>/README.md`](projects/) | 改完跑阶段 B 校验（见任务卡）；禁止只改 `PREFIXES` 或只改 KB seed |
| 开发任务 | `docs/dispatch/<prefix>/<prefix>NNN-slug.md`（`scripts/new-card.sh`） | 卡头五态；不做第二份设计长文 |
| 平台现行 SOP | [`product/`](product/) **白名单**（须进 INDEX §0/§1） | 新 SOP 必须同时改 INDEX；否则不算权威 |
| 部署 / 拓扑 | [`deploy/`](deploy/) | 短、可执行；与 `.ccc/infrastructure.md` 冲突时以 deploy + INDEX 为准 |
| 临时笔记 | [`notes/`](notes/) | **7 天内**并入权威、删或迁 `archive/`；禁止当 SSOT |
| 史实 / 烟测 / 旧协议 | [`archive/`](archive/) | 文首标「史」；日常勿引用为现行 |

### 现行产品 SOP 白名单（入口级）

仅下列视为现行（其余 `product/` 默认当史，除非 INDEX 明确升格）：

- [`product/dev-channel.md`](product/dev-channel.md)
- [`product/accept-board-sop.md`](product/accept-board-sop.md)
- [`product/machine-audit-flow.md`](product/machine-audit-flow.md)
- [`product/ccc-desktop-architecture.md`](product/ccc-desktop-architecture.md)（Desktop 恢复时）

---

## 2. 项目注册（唯一事实源）

| 层 | 路径 | 角色 |
|----|------|------|
| **SSOT** | [`projects/registry.yaml`](projects/registry.yaml) | 前缀 / UI id / 路径 / taskable / forbidden / status |
| **档案** | `projects/<prefix>/README.md` | 每项目一页（五节模板，禁止再长） |
| **派生（阶段 B 后）** | `PREFIXES`、`GET /projects`、`is_taskable`、`knowledge/seed` | **禁止手维第二份真值**；由 registry 生成或校验对齐 |
| **说明** | [`dispatch/T-mapping.md`](dispatch/T-mapping.md) | 历史卡命名对照；**前缀表以 registry 为准** |

废弃手维：`docs/kb-seed/`（只认 `knowledge/seed/`，且须与 registry 一致）。

### 档案五节模板（强制）

1. **是什么**（一句话）  
2. **路径**（M1 / 2017）  
3. **在 CCC 怎么动**（出卡前缀、是否 taskable）  
4. **线路 / 近况**（链 roadmap 挂账，或 ≤3 条；不贴长史）  
5. **禁区**

---

## 3. 线路图怎么归位

| 面 | 职责 |
|----|------|
| [`roadmap.md`](roadmap.md)「当前方向 + 下一程挂账」 | 产品北星与未出卡意向 |
| HTTP `#/roadmap` | 按卡状态聚合；可链本规范与 `projects/`，**不**承载第二套项目百科 |
| 历史正文 | 只在 [`archive/`](archive/)；勿覆盖「当前方向」 |

---

## 4. 禁止

- 在 `CLAUDE.md` / 聊天 / 业务仓与 CCC **双写**同一权威事实  
- 新建落点表外的「说明.md」「设计.md」「项目文档」目录树（如 `docs/qb/` 深文档）  
- 把 `docs/kb-seed/`、Hub 时期 `product/hub-*`、旧 `CONTRIBUTING` phases 协议当现行  
- 口头注册项目（必须改 registry + README，阶段 B 后还须校验通过）

---

## 5. Agent 最短路径

```
INDEX §0 → DOC-PROTOCOL（本页）→ projects/<prefix>/README 或 scripts/new-card.sh
```

日常短读：§0 → 本页 → `architecture.md` → `STARTUP-BRIEF.md`。
