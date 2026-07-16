# 竖切蓝图：CCC × QX（及通用垂直行业）

> **本阶段只写蓝图，不拆 QX 大仓。**  
> 产品叙事见 [`INTRO.md`](INTRO.md) · [`VISION.md`](VISION.md)  
> QX 路径（本机）：`~/program/projects/qx` · QXO 指挥台：`~/program/qx-observer`（互补，非替代 CCC）

---

## 1. 判断

| 已有（QX） | 缺失 | CCC 补上 |
|------------|------|----------|
| 爬虫注册表、`crawlers/` | Loop 级编排 | Engine + Board |
| PostgreSQL `qx_platform` | 人机快捷交接 | Hub + 快捷键 / 自定义动作 |
| `workers/`、历史 PM2 cron | 失败重试 / 验收门禁 | phase + verdict + 重开 |
| Dashboard 业务可视化 | 「意图 → 可执行任务」 | 定稿转任务 / 模板下达 |

结论：QX **不必再造调度 IDE**；以 CCC 为底座，行业资产挂上去即竖切产品。

QXO（qx-observer）偏战略指挥 / 中台，与 CCC **互补**：CCC 跑编排闭环，行业资产与 Domain Skill 挂在 CCC 下。

---

## 2. 通用配方

```text
CCC Hub ──快捷键──► 模板任务
    │
    ▼
Engine + Board ──阶段能力包──► 执行器（OpenCode / Claude / 行业 CLI）
    │                              ▲
    └──── Domain Skill ────────────┤
                                   │
                          爬虫 / worker / DB
```

复制到下一垂直行业时：**只换 Domain Skills + 资产 + 快捷键文案，不换 Hub。**

---

## 3. QX 落地阶段（建议顺序）

### Phase A — 挂载（低风险）

1. 将 QX workspace 登记 `~/.ccc/workspaces.json`（Hub 可选项目 `qx`）  
2. 控制面 `enable` 仅在需要自动消费队列时打开  
3. 用 Hub「转任务」对 QX 发一笔小 scope 改造任务做冒烟  

### Phase B — 快捷键竖切

在 Hub 自定义动作（或后续配置化）沉淀：

| 动作示例 | 下达效果 |
|----------|----------|
| 跑四川价 | 模板 task → scope=`crawlers/...` + runner 命令 |
| 补采失败单 | 读失败账本 → 生成 requeue task |
| 对账日报 | ETL/report phase 链 |

用户仍**不选角色**；点的是**业务动词**。

### Phase C — 执行器对接

- phase `scope` 指向 `projects/qx/crawlers|workers|lib/...`  
- 失败回灌沿用 CCC pytest / verdict / reopen  
- 逐步把「PM2 唯一调度源」叙事改为 **Board+Engine 触发**；cron 可保留为「向 backlog 投递」的薄封装  

### Phase D — 产品边界

| 保留在 QX Dashboard | 迁到 / 以 CCC Hub 为准 |
|---------------------|------------------------|
| 业务图表、采价结果、运营看板 | 任务状态、重试、验收、控制面 |
| 领域配置 UI（若有） | 定稿、转任务、快捷编排 |

### Phase E — 复制下一行业

模板：`docs/vertical-<industry>.md` 复制本文结构，替换资产表与快捷键表即可。

---

## 4. 资产对照表（初稿）

| 层 | CCC | QX |
|----|-----|-----|
| 入口 | Hub `:7777` | （编排不再以 Dashboard 为入口） |
| 编排 | `ccc-engine` / board JSONL | 任务类型 crawl / ETL / report |
| 执行 | OpenCode / Claude | `python -m lib.crawler_core.runner`、workers |
| 数据 | 不替代 | `QX_PG_DSN` / `qx_platform` |
| 能力包 | `skills/ccc-*` | 待建 `skills/qx-*`（采价规则、质检） |

---

## 5. 非目标（本蓝图明确不做）

- 立刻把整个 QX 仓库搬进 CCC monorepo  
- 用 CCC 重写 PostgreSQL schema  
- 让 QXO 与 CCC Hub 抢同一端口做同一入口（端口规划见 `ccc-hub-ports.md`）  

---

## 6. 成功标准（日后验收用）

1. 在 Hub 选项目 `qx`，一个自定义快捷键可下达并跑通单爬虫任务  
2. 失败可在 Hub/控制台重开，无需 SSH 改 PM2  
3. 文档与演示可复述：「CCC 底座 + QX 资产 = 医药采价垂直工具」  
