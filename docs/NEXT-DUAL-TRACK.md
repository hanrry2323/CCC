# 下一步计划：用 CCC 带动 xianyu + clawmed-ccc（双轨）

> 状态：**已拍板**（2026-07-17）  
> 叙事：`docs/VISION.md` / `docs/INTRO.md` · 视频：`docs/releases/intro-video-script.md`

---

## 已拍板

| 决策 | 选择 | 说明 |
|------|------|------|
| **D1 xianyu** | **D1-A** | 先质量门，过线后再产 CCC 介绍片 |
| **D2 QX 竖切** | **D2-B** | 全新项目，不在旧 qx 上打转 |
| **新项目** | **clawmed-ccc** | 目录：`~/program/clawmed-ccc` · **任务简称：`cla`** |
| **第 1 周** | **并行** | A1（xianyu 质量门）+ B0（建仓 clawmed-ccc） |
| **旧文档** | **全量归档** | qx / clawmed 旧任务文档移出主路径，仅需时参考 |

---

## 0. 用白话说要干什么

| 轨 | 目标 | CCC 干什么 |
|----|------|------------|
| **A · xianyu** | 优化后的出片质量过线 → 再产 CCC 介绍视频 | 任务卡：质量冒烟 → 修 P0 → 出介绍片 |
| **B · clawmed-ccc** | CCC 底座 + 从旧 qx/clawmed **迁入**有价值资产 | 任务卡：建仓 → 迁最小爬虫 → 快捷键闭环 |

旧 `projects/qx`、`projects/clawmed-ai`：**零件库 + 归档**，不再当主开发面。

---

## 1. 总原则

1. 一个意图 = 一张看板任务（Hub 定稿转任务）。  
2. 控制面日常 `enable`；不默认 `invent`。  
3. 工作区：`xianyu`、`clawmed-ccc` 登记 `~/.ccc/workspaces.json`。  
4. Engine 跑阶段能力包；人拍板与看失败重开。  
5. 小步卡：有 scope、有验收句。  
6. **旧任务文档不进新仓上下文**：Agent/人默认不读归档目录（见 §7）。

---

## 2. 轨 A — xianyu（D1-A）

| 顺序 | 任务 | 验收 |
|------|------|------|
| **A1** | 跑通近期视频质量优化 + 验收清单 | 同输入 2 次不崩；差距表；≥30s 可看样片 |
| A2 | 按差距表修 P0 | P0 清零或书面豁免 |
| A3 | 产出 CCC 介绍片 60–90s | 成片可挂 Release（脚本见 intro-video-script） |
| A4 | （可选）链回 CCC README | 可点开 |

---

## 3. 轨 B — clawmed-ccc（D2-B）

路径：`/Users/apple/program/clawmed-ccc`  
Hub / 看板任务标题前缀建议：`cla:`（简称，避免每次打全名）

| 顺序 | 任务 | 验收 |
|------|------|------|
| **B0** | 命名 + 建仓 + README（CCC 底座）+ 空 `.ccc/board` + 登记 workspace | **已完成**（2026-07-17） |
| B1 | 从旧 qx **迁入**最小爬虫集，跑通 1 条 | runner/任务可验收 |
| B2 | PG 连接与最小迁移策略 | 约定库可读写 |
| B3 | Hub 自定义快捷键 → 模板 crawl 任务 | 一点即派 |
| B4 | 编排以 CCC 看板为准；业务大屏边界写明 | 文档 + 冒烟 |

**迁入白名单**：爬虫适配器、经证明可跑的 worker、PG schema/规则文档。  
**不迁**：旧 PM2 唯一调度叙事、死代码、会污染上下文的旧 plans/phases/reports。

---

## 4. 第 1 周并行（已同意）

| 轨 | 本周最小交付 |
|----|--------------|
| A | **A1** xianyu 质量门 |
| B | **B0** `clawmed-ccc` 建仓并挂 CCC |

---

## 5. 介绍素材

```text
A 过线后 ──► xianyu 出 CCC 介绍视频
B 改造中 ──► Hub/看板截图 → docs/assets/intro/
```

---

## 6. 旧项目角色

| 路径 | 角色 |
|------|------|
| `~/program/clawmed-ccc` | **主开发面**（新垂直产品） |
| `~/program/projects/qx` | 归档 + 零件库（只读参考） |
| `~/program/projects/clawmed-ai` | 归档 + 零件库（OpenClaw 早期残留） |
| `~/program/xianyu` | 轨 A 主开发面 |

---

## 7. 归档策略（qx / clawmed）

### 原则

- **全部旧任务文档**移出日常路径，避免 CCC/Agent 扫到陈年 plan 当现行需求。  
- 有价值内容保留在 `_archive/`，**仅在需要时人工打开**。  
- 新仓 `clawmed-ccc` **禁止**复制旧 `.ccc/plans|phases|reports|board` 垃圾；只迁代码与数据契约。

### 归档落点（已执行/约定）

| 来源 | 归档目录 |
|------|----------|
| `projects/qx` 的 `.ccc/{plans,phases,reports,reviews,verdicts,audit-reports,evolve}` 与历史 board 任务 | `projects/qx/_archive/ccc-artifacts-2026-07-17/` |
| `projects/qx/tasks` 等任务清单 | 同上或 `projects/qx/_archive/tasks-2026-07-17/` |
| `projects/clawmed-ai` 的 `plans/`、`tasks/` 及同类任务文档 | `projects/clawmed-ai/_archive/task-docs-2026-07-17/` |

各归档根目录放 `README.md`：说明「只读参考，非现行 backlog」。

### Agent 约定

- 默认 **不读** `**/_archive/**`、旧 qx/clawmed 的历史 plan。  
- 需要零件时：人明确说「从 qx 归档参考某某爬虫」再打开。

---

## 8. 下一步动作清单

- [x] 本文写入已拍板（D1-A / D2-B / clawmed-ccc / 并行）  
- [x] 执行 qx / clawmed-ai 归档移动  
- [x] 创建 `~/program/clawmed-ccc` 骨架并登记 workspace  
- [ ] Hub 下达 **A1**（xianyu 质量门）、**B1**（迁入最小爬虫；B0 已完成）  
- [ ] **流程诊断**：批1=OBS1+OBS2（已下达 in_progress）→ 你通知验收 → 批2再下 3 卡；凑 ≥6 样本再修（见 §9）  

---

## 9. CCC 流程观察（样本=7，可开工修）

> 主目的：跑通 CCC 闭环可信度。  
> 样本：B1 · B1.1 · OBS1 · OBS2（seed）+ OBS3/4/5（全流程 product）+ Engine 卡死一次。

### 9.1 看板终态（2026-07-17）

| 任务 | 路径 | 终态 | 硬交付 |
|------|------|------|--------|
| B1 | seed | released | `src/` 空；commit=bootstrap |
| B1.1 | seed | released | 有骨架但 `src/` 曾未提交；FALLBACK |
| OBS1 | seed | released | **真 commit** `bfcfd06`；`tests/test_obs1` 已跟踪 |
| OBS2 | seed | released | **真 commit** `0924d4f`；`tests/test_obs2` 已跟踪 |
| OBS3/4/5 | **全流程** | **abnormal** | product×3：`Not logged in` / parse failed；无 plan |

并发：OBS1+OBS2 曾双开（2/3）；批2 因 product 挂未打满 3 槽。Engine 曾卡死需 kickstart。

### 9.2 假说结论（够改）

| # | 结论 | 证据强度 | 优先修 |
|---|------|----------|--------|
| H1 | 无 task commit 仍可记 HEAD 过门 | B1/B1.1 中；OBS1/2 证明「有真 commit 时也能过」→ 缺的是**门禁强制** | P0 |
| H2 | FALLBACK 写 `Verdict: PASS` → 不回滚 | OBS1/2/B1/B1.1 全中；根因含 **claude 未登录** | P0（门禁）+ 运维登录 |
| H5 | 全流程依赖 claude product；未登录必 abnormal | OBS3/4/5 全灭；与 H2 同源 | P0 运维 + product 失败分类 |
| H7 | Engine 可卡死（日志停更） | 批2 投放后 tick 停；kickstart 后恢复 | P0 看门狗/超时 |
| H3 | `tests/` 存在后 Engine 不再「跳过」日志 | OBS1/2 后本地 `pytest tests/` 6 passed；门禁日志弱 | P1 |
| H4 | 无 origin push-fail 仍 released | 每次 kb | P2（WARN 即可） |
| H6 | SELF-CHECKS 可补记 | OBS2/B1.1 | 绑 H1 |

### 9.3 流程修复（2026-07-17 已落地）

| 项 | 改动 |
|----|------|
| H2 | `CCC_REVIEWER_FALLBACK` 默认 `quarantine`；`static`→`stay`；**绝不写 Verdict PASS / 绝不静默 verified** |
| H1 | launch 记 `pre_head`；过 testing 前必须 `git log --grep=task_id` 且 ≠ pre_head；取消 HEAD 降级 |
| H5/auth | product 识别 `Not logged in` → `fatal` 立即 quarantine |
| H7 | Engine tick watchdog（默认 180s 无 tick → exit 78）；patrol 对 stale+alive **kill+restart** |

**更正（鉴权）**：OBS3–5 的 `Not logged in · Please run /login` **不是**要跑 interactive `/login`。  
根因：`_sanitized_env()` 按 `TOKEN` 误剥 launchd 继承的 `ANTHROPIC_AUTH_TOKEN`（中转站鉴权）。  
已修：LLM allowlist 保留 `ANTHROPIC_*`；product/reviewer 走 `_claude_env()`。
