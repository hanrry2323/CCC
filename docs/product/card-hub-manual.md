# CCC 制卡发卡操作手册（工具无关自举路径）

> 定位：**任何 IDE/CLI 工具加载本仓后**的自举手册。读完本手册与必读链，即可担任「制卡发卡中枢」。
> 工具无关：出卡 / 校验 / 取证 / 合入全部是 bash + python CLI + HTTP API，不依赖特定 IDE；
> 机器路径、端口、工具绑定一律不写死，只认下面的真值源。
> 入口文档：`AGENTS.md`（Codex/OpenCode/Cursor 系）与 `CLAUDE.md`（Claude 系）是**唯一双入口**，本手册由两个入口共同指向。

---

## 0. 先确认你是谁（双模式）

| 场景 | 你是谁 | 干什么 |
|------|--------|--------|
| 人在本仓打开 IDE / CLI 聊天 | **制卡发卡中枢** | 陪聊 → 收敛意图 → 出卡 → 盯板。**不代执行** |
| 被 Engine `-p` / `--dir` 拉起 | **产线执行体** | 只按卡白名单写码 → 已回写 → 停 |

## 1. 必读链（按序，五分钟）

1. 本手册（你在读的这份）
2. [`../INDEX.md`](../INDEX.md) §0 — 权威链与北星（冲突裁决顺序）
3. [`../DOC-PROTOCOL.md`](../DOC-PROTOCOL.md) — 文档落点 + **卡命名定死**
4. [`../projects/registry.yaml`](../projects/registry.yaml) — 项目唯一事实源
5. [`hub-context-sop.md`](hub-context-sop.md) — 出卡前怎么了解项目（固定 6 步）
6. [`dev-channel.md`](dev-channel.md) · [`accept-board-sop.md`](accept-board-sop.md) — 谁改 CCC / 怎么合入
7. [`../references/red-lines.md`](../references/red-lines.md) — 红线全集

## 2. 查项目（出卡前）

- 项目边界：`docs/projects/registry.yaml`（前缀 / `taskable` / `paths` / `forbidden`）
- 每项目一页档案：`docs/projects/<prefix>/README.md`
- `forbidden: true` 或 `qh` → **不出卡**，按 registry 改门禁

## 2.5. 查方案（计划页面）

- 方案池：`docs/projects/<prefix>/plans/`（模板 `_template/plan-template.md`，命名 `DOC-PROTOCOL.md` §2.7）
- 校验：`scripts/validate-plans.sh`
- 转卡：方案确认后在计划页面（`#/plans`）点「转为任务卡」，脚本调 `new-card.sh` 生成任务卡进看板。**转卡由人触发，不全自动。**

## 3. 出卡（唯一入口脚本）

```bash
# 单卡（预览不写盘）
scripts/new-card.sh --project <prefix> --title "…" --dry-run
# 单卡（真写 + 自动 validate）
scripts/new-card.sh --project <prefix> --title "…"
# 多卡（方案确认 ccc-plan 后）
scripts/plan-to-cards.sh
```

命名定死（违反 = validate 红 = 出不了卡）：

```text
路径   = docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md
卡 ID  = <prefix><NNN>            分支 = codex/<文件名去 .md>
```

出卡后：`python3 -m server.board.validate docs/dispatch` 必须绿 → **只提交任务卡** → push 到 `main` → 停手盯板。

### 3.1 方案拆卡（ccc-plan-027 功能卡清单）

方案正文用 `## 功能卡` 段拆卡（**一个功能一张卡**），节点② 老板确认清单后一次转卡（粒度 A）：

```markdown
## 功能卡

### <功能卡标题——一个独立功能>

目标：<2-3 句人话，一眼看懂这一步做什么>
实现：<详细实现，可选；注入卡文件 ## 实现 段>
验收：<验收点，可选>
```

- **拆卡原则**：一张功能卡 = 一个可独立交付的功能；验收标准 >5 条说明该拆成两张。
- **两级卡**：一级人话目标（老板/看板导航看），二级实现详情（执行体看）。
- **节点② = 确认功能卡清单**：计划页方案详情 →「转为任务卡」→ 弹层展示功能卡清单 → 老板确认 → 一次生成全部卡进看板「待分派」，方案自动推进「部分执行」。
- 旧 `## 转卡计划` 段（每行一卡）仅兼容存量方案，转卡脚本自动识别两种格式。

## 4. 盯板（进度真值）

- 看板 / API 端点：**只认 `docs/deploy/topology.md`**（不在此写死端口与机器名）
- 取证：`scripts/card-evidence.sh <card-id>`（只认 `origin/codex/<stem>`）
- ready 队列：`/board/ready_for_merge`
- 禁止：全文 grep「待分派」当进度；`/tmp` merge 考古

## 5. 合入（人唯一常规动作）

老板说 **「合入批准」**（别名：验收看板 等同义）→ `scripts/approve-merge.sh <card-id>`（或 `--ready`）。
禁止自认机审席 / 改写 `## 机审区`；机审由引擎自动拉起（交叉配对见工具绑定表）。

## 5.5 人审调整动作（作废 / 取消 / 修改 · 2026-08-14 统一化）

人审时老板对「不要了 / 要改」的调整，走固定动作：

| 对象 | 动作 | 入口 |
|------|------|------|
| 草案（节点①） | 取消 | 线路图页草案池「取消」→ `DELETE /roadmap/<prefix>/draft/<index>`（直接移除） |
| 草案（节点①） | 修改 | 线路图页草案池「编辑」→ `PUT /roadmap/<prefix>/draft/<index>` |
| 方案（节点②） | 作废 | 计划页状态下拉选「作废」→ 弹确认（提示将级联作废关联卡）→ `POST /plans/update {status:作废}` |
| 单卡（节点③） | 作废 | 看板卡详情「作废」→ 填原因确认 → `POST /tasks/<id>/transition {status:作废, reason}` |
| 单卡（节点③） | 打回/修改 | 看板卡详情「重新分派」→ `POST /tasks/<id>/transition {status:待分派}`（批注写卡头 `## 人工批注`） |

**规则**：作废=终态不可逆；方案作废自动级联其未关闭关联卡；作废卡从方案进度总数剔除；打回自动递增卡头 `打回次数：N`。

## 6. 工具无关原则（硬）

1. 本仓出卡 / 校验 / 取证命令全是 bash + python CLI，任何能跑 shell 的工具即可担任中枢。
2. **入口文档不写机器细节**：绝对路径、IP、端口、工具绑定名一律不进 `AGENTS.md` / `CLAUDE.md` / `CURSOR.md`（门禁：`scripts/check-entry-docs.py`）。
3. 真值源分层：机器路径 → `registry.yaml`；端口/拓扑 → `topology.md`；角色→工具绑定 → qx-map `ide/tool-roles.md`（规则文档只写角色）；执行体注册表模板 → `server/config/executors.example.json`。
4. 新工具接入 = 读双入口 → 顺指针自举；工具特殊性只写在该工具自己的薄桥接文件（如 `CURSOR.md`），不写入通用入口。

## 7. 边界（硬）

- 中枢 ≠ 执行体；了解 ≠ 代执行；禁止代执行体 commit/push 业务仓分支。
- 卫生类意图 → 出极窄维护卡（卡内写权威路径 / 禁新建 worktree / 探针=git 对齐），中枢不下场收口。
- 卡头状态五态与流转、批注/回写区规则见 `DOC-PROTOCOL.md` §2；本手册不重复，防止双写漂移。
