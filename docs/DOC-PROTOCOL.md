# CCC 文档写入规范（DOC-PROTOCOL）

> **权威入口**：[`INDEX.md`](INDEX.md) §0 → 本页。  
> **目的**：用更少的文档管事；谁都能写，但必须落在规定路径；**任务卡怎么命名已定死**。

---

## 0. 四条硬原则

1. **同一事实只存一处**；第二份只能是派生，或文首标明「史」。
2. **先问落点再写**：下表没有的路径 = **禁止新建**；应归档或并入现有页。
3. **项目档案一页封顶**：每个可出卡前缀在 CCC 仓只维护 `docs/projects/<prefix>/README.md`；业务深文写在业务仓，不在 CCC 复制。
4. **卡 ≠ 文档**：开发工作只出 [`dispatch/`](dispatch/) 任务卡；项目存档 / 线路意向不进卡正文堆历史。
5. **冻结 Agent 心智补丁（2026-08-07）**：北星 = 一个主 IDE 谈意图 → `ccc-plan` 确认后自动拆卡入队 → Engine+硬门禁静默跑 → 只在 RED 或待合入时找人 → 人审 diff 后「合入批准」。禁止为「教 Agent 少迷路」新建/扩写 SOP、验收同义句、席位表、AGENTS 长禁令。缺口只记 [`roadmap.md`](roadmap.md) 挂账；改流程须先改 [`INDEX.md`](INDEX.md) §0。竖切见 [`product/north-star-slice.md`](product/north-star-slice.md)。

---

## 1. 落点表（写哪里）

| 你要写的 | 写这里 | 怎么写 |
|----------|--------|--------|
| 平台共识 / 权威裁决 | 先改 [`INDEX.md`](INDEX.md) §0，再改被引用文 | 短、可裁决冲突；禁止只留在聊天 |
| 下一程意向（未出卡） | [`roadmap.md`](roadmap.md)「下一程挂账」 | **一行**意图 + 备注；未出卡不写长文 |
| 注册 / 改项目 | [`projects/registry.yaml`](projects/registry.yaml) + 对应 [`projects/<prefix>/README.md`](projects/) | 改完跑校验；禁止只改 `PREFIXES` 或只改 KB seed |
| 开发任务 | **优先** `scripts/plan-to-cards.sh`（`ccc-plan`）；单卡仍可用 `new-card.sh` | 命名见 §2；方案确认后禁止一张张聊着出卡 |
| 平台现行 SOP | [`product/`](product/) **白名单**（须进 INDEX §0/§1） | 新 SOP 必须同时改 INDEX；**禁止**心智补丁类新建（原则 #5） |
| 部署 / 拓扑 | [`deploy/`](deploy/) | 短、可执行 |
| 临时笔记 | [`notes/`](notes/) | **7 天内**并入权威、删或迁 `archive/` |
| 史实 / 烟测 / 旧协议 | [`archive/`](archive/) | 文首标「史」 |

### 现行产品 SOP 白名单（入口级）

- [`product/dev-channel.md`](product/dev-channel.md)
- [`product/north-star-slice.md`](product/north-star-slice.md)（北星竖切 · plan-to-cards / 合入批准）
- [`product/hub-context-sop.md`](product/hub-context-sop.md)（中枢出卡前了解项目 · 允许/禁止表）
- [`product/accept-board-sop.md`](product/accept-board-sop.md)（别名指向合入批准，见 north-star-slice）
- [`product/machine-audit-flow.md`](product/machine-audit-flow.md)
- [`product/ccc-desktop-architecture.md`](product/ccc-desktop-architecture.md)（Desktop 恢复时）

---

## 2. 任务卡 / 任务命名（硬 · 定死）

> **门禁**：`scripts/new-card.sh` + `server/board/validate.py`。不合规 = 出不了卡 / CI 红。  
> **前缀表**：[`projects/registry.yaml`](projects/registry.yaml)（唯一）；[`dispatch/T-mapping.md`](dispatch/T-mapping.md) 仅历史对照。

### 2.1 一句话公式

```text
路径   = docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md
卡 ID  = <prefix><NNN>          （例：ccc005）
文件名 = <prefix><NNN>-<slug>   （例：ccc005-registry-single-source.md）
分支   = codex/<文件名去 .md>   （例：codex/ccc005-registry-single-source）
worktree 目录名片段 = <prefix><NNN> 小写（例：ccc-dev-ws-ccc005）
```

**三者必须一致**：`prefix` = `docs/dispatch` 子目录名 = 卡头字段「项目」= registry 前缀。

### 2.2 各段规则（不许改口径）

| 段 | 规则 | 例 | 非法例 |
|----|------|----|--------|
| **prefix** | 2–4 位**小写英文字母**；必须在 registry 且 `forbidden: false` | `ccc` `qb` `mx` `xy` `hp` `tst` | `CCC` `qh` `medio` `T` |
| **NNN** | **恰好三位数字**，同前缀内自增、唯一；禁止跳号手造冲突 | `001` `005` | `5` `0005` `ccc5` |
| **slug** | 小写字母/数字，词间**单**连字符；由标题英文词派生；纯中文标题 → `task` | `registry-single-source` | `Registry` `a__b` `中文` |
| **扩展名** | 固定 `.md` | — | `.MD` `.txt` |

### 2.3 卡头与正文标题

```markdown
# 任务卡 <prefix><NNN> · <人读标题>（<执行体> 执行）

> 关联：… · 执行体：… · 验收：… · 状态：待分派 · 派发：engine|manual · 项目：<prefix> · 日期：YYYY-MM-DD
```

- 卡头「项目」**必须** = 文件名前缀 = 子目录名。  
- 状态五态定死：`待分派` / `执行中` / `已回写` / `已关闭` / `打回`（可带括号原因，归桶看基础态）。  
- 看板「机审」是派生列，**不是**卡头第六态。
- 「验收」= 执行体自身（**自验收**，2026-08-07 改）：谁开发谁验收。两条硬规则：① 机审是独立步骤——开发阶段禁止写 `## 机审区`，验收席（即使与开发同工具）按 Code Review 技能独立审查、写机审区、过 ready 门禁；② 老板「合入批准」= 人审最终 diff，任何人/工具不可绕过。
- `## 人工批注`（可选固定节）：老板对打回卡/审核的批注意见写这里。若存在，执行体**必须先读批注**并按批注修订目标/步骤后再执行，批注优先于正文。重新分派 = `打回 → 待分派`（写纯「待分派」，引擎重试计数归零；`打回次数` 保留为历史）。

### 2.4 出卡方式（定死）

1. **唯一入口**：`scripts/new-card.sh --project <prefix> --title "…" [--slug …]`  
2. 禁止手搓文件名绕过；禁止在 `docs/dispatch/` **根目录**新建卡。  
3. 禁止新出 `T<数字>-*.md`（旧 T 卡只读保留，**永不批量改名**）。  
4. 禁止前缀 `qh`（QuantHive 独立轨道）。

### 2.5 人话怎么叫「这个任务」

| 场合 | 怎么说 / 写 |
|------|-------------|
| 口头 / 看板 | `ccc005` 或全名 `ccc005-registry-single-source` |
| 聊天贴任务块 | `<<<CCC_TASK>>>` 里 `id: ccc005` |
| git 分支 | 必须 `codex/<完整文件名去.md>`，勿直推 `main` |
| 日志 / worktree | `ccc005`（与卡 ID 同） |

### 2.6 正反例

**合法**

- `docs/dispatch/ccc/ccc006-board-live-metrics.md`
- `docs/dispatch/qb/qb001-fix-login.md`
- `docs/dispatch/mx/mx012-export-csv.md`

**非法（validate / new-card 必须拦）**

- `docs/dispatch/ccc006-foo.md`（不在前缀子目录）
- `docs/dispatch/ccc/CCC006-foo.md`（前缀大写）
- `docs/dispatch/ccc/ccc6-foo.md`（序号非三位）
- `docs/dispatch/T99-new-thing.md`（新 T 卡）
- `docs/dispatch/qh/qh001-x.md`（禁前缀）
- 卡头「项目：medio-0」但文件在 `mx/`（项目字段必须写前缀 `mx`）

---

## 3. 项目注册（唯一事实源）

| 层 | 路径 | 角色 |
|----|------|------|
| **SSOT** | [`projects/registry.yaml`](projects/registry.yaml) | 前缀 / UI id / 路径 / taskable / forbidden / status |
| **档案** | `projects/<prefix>/README.md` | 每项目一页（五节模板，禁止再长） |
| **派生** | `PREFIXES`、`GET /projects`、`is_taskable`、`knowledge/seed` | 禁止手维第二份真值 |
| **历史对照** | [`dispatch/T-mapping.md`](dispatch/T-mapping.md) | 旧 T 卡 ↔ 新名；**前缀表以 registry 为准** |

废弃手维：`docs/kb-seed/`。

### 3.1 仓库位置规范（硬 · 2026-08-07）

业务仓路径必须落在归属树内（`registry.yaml` 每项目 `location` 字段，`server.board.registry.check_path_locations` 校验）：

| location | 允许树 | 说明 |
|----------|--------|------|
| `m1-program` | `~/program/<name>`（M1） | M1 业务/基建仓 |
| `mac2017-apps` | `~/program/apps/<name>`（2017） | 2017 业务仓 |
| `mac2017-platform` | `~/program/CCC`（2017 例外） | 平台本体 |
| `legacy` | 不限 | 散落仓（QuantHive `~/ZCodeProject`、qx-map `~/qx-map` 等）只标注不迁移 |

- 新注册项目必须标 `location`；路径越界 → 校验红。
- 文件夹归位搬迁为独立运维项（停机窗口一仓一验），搬迁后 registry 路径随迁移更新。

### 档案五节模板（强制）

1. **是什么**（一句话）  
2. **路径**（M1 / 2017）  
3. **在 CCC 怎么动**（出卡前缀、是否 taskable）  
4. **线路 / 近况**（≤3 条）  
5. **禁区**

---

## 4. 线路图怎么归位

| 面 | 职责 |
|----|------|
| [`roadmap.md`](roadmap.md)「当前方向 + 下一程挂账」 | 产品北星与未出卡意向 |
| HTTP `#/roadmap` | 按卡状态聚合；不承载第二套项目百科 |
| 历史正文 | 只在 [`archive/`](archive/) |

---

## 5. 禁止

- 在 `CLAUDE.md` / 聊天 / 业务仓与 CCC **双写**同一权威事实  
- 新建落点表外的说明/设计树（如 `docs/qb/` 深文档）  
- 把 `docs/kb-seed/`、Hub `product/hub-*`、旧 phases 协议当现行  
- 口头注册项目；**口头发明卡号 / 前缀 / 分支名**  
- 手改卡文件名绕过 `new-card.sh`

---

## 6. Agent 最短路径

```
INDEX §0 → DOC-PROTOCOL（本页 §2 命名）→ registry / 档案 → scripts/new-card.sh
```

日常短读：§0 → 本页 → `architecture.md` → `STARTUP-BRIEF.md`。
