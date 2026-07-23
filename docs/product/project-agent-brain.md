# 项目 Agent 脑包（舰队标准 · qb 样板）

> **状态**：现行 · 2026-07-24  
> **权威摘要**：[`loop-engineer-authority.md`](loop-engineer-authority.md) §项目脑包  
> **目的**：按 `project_id` 隔离业务 Agent 知识；**不新造 TODO**；qb 改造完成后其它仓按本表抄，防漂移。

---

## 1. 六层认领（禁止另起炉灶）

| 角色 | 标准名 | qb 样板路径 | 其它仓 |
|------|--------|-------------|--------|
| 定位 / 铁律 | CLAUDE | `CLAUDE.md` | 根目录必有；含「项目脑索引」 |
| 规划 / 未来待办 | 规划文 | `docs/DEV_PLAN_v1.1.md` | 可用等价文件名；**必须在 CLAUDE 声明「规划 SSOT = …」** |
| 当前产品意图 | decided.goals | `.ccc/agent-mind/decided.json` | 须 `exit_condition`；空闲推 next |
| 共识 / 约束 | decided.constraints + CLAUDE 铁律 | 同上 | |
| 档案 / 双机 | profile | `.ccc/profile.md` | |
| 开发过程 | board | `.ccc/board/*` | **过程 ≠ 未来目标** |

**禁止**：根级 `TODO.md` 当主路径；用 board 文件数当待办；M1 业务第二树 CLAUDE；把 `AGENTS.md` / 薄 `STATUS.md` 升 SSOT。

---

## 2. CLAUDE「项目脑索引」（每仓必有）

放在 `CLAUDE.md` 靠前位置（样板）：

```markdown
## 项目脑索引（CCC）

| 层 | 路径 |
|----|------|
| 规划 / 未来待办 | docs/DEV_PLAN_v1.1.md |
| 当前产品意图 | .ccc/agent-mind/decided.json |
| 开发过程 | .ccc/board/（看板；非目标清单） |
```

---

## 3. 注入（Hub → Desktop）

- 编译：`scripts/chat_server/services/project_brain.py`
- 出口：`GET /api/desktop/mind/{id}/digest` 字段 `brain`（文本，有长度帽）+ 结构化 `brain_meta`
- sidecar：业务项目每轮与 live board 并行拉取；**`project_id=ccc` 编排运维不灌业务规划文**
- 新鲜度：live board / lens git > brain/digest > 聊天 resume
- 脑包**不作**代码细节终局（仍 hub_locate / hub_file）

长度帽（约）：CLAUDE 2KB · profile 1KB · 规划文头 1.5KB · decided 摘要计入 digest 既有段。

---

## 4. 改造验收勾选（每仓）

样板 **qb**（2026-07-24）：

- [x] 根 `CLAUDE.md` 含项目脑索引三行（规划路径真实存在）
- [x] 规划文存在且 CLAUDE 指向正确（`docs/DEV_PLAN_v1.1.md`）
- [x] `.ccc/profile.md` 有权威路径 + 规划/意图指针
- [x] `decided.goals` 至少 1 条未完成产品目标且含 `exit_condition`（4/4）
- [x] Desktop/Hub：digest/`brain`/`inject` 可见定位或规划要点
- [x] 板堵本会话 `hub_repair` 自清；禁止甩锅「打开编排运维」
- [x] **未**新建根 `TODO.md` 主路径

其它仓改造时复制上表为未勾选再逐项绿。

---

## 5. 舰队 Rollout 表

| project_id | 规划文路径 | CLAUDE 索引 | profile | decided+exit | 注入验 | 备注 |
|------------|------------|-------------|---------|---------------|--------|------|
| qb | docs/DEV_PLAN_v1.1.md | 2026-07-24 | 2026-07-24 | 2026-07-24 | 2026-07-24 Hub brain+digest | **样板 · 已对齐** |
| hp | （改造时填） | | | | | |
| xianyu | （改造时填） | | | | | |
| medio-0 | （改造时填） | | | | | |
| clawmed-ccc | （改造时填） | | | | | |
| qxo | （改造时填） | | | | | |
| ccc-demo | （改造时填） | | | | | 可选烟测仓 |

每仓改造 = 抄 §2–§4；**平台注入代码不改**。填表时把空格改成日期；完成行备注写「已对齐」。

---

## 6. 关联

- 双 Agent：项目 vs 编排运维 → authority §双 Desktop Agent  
- L1 mind API → `agent_mind.py` / `project_brain.py`  
- 模板 → `templates/project-CLAUDE.md`
