# Hub-Shell Phase14 — Desktop 右栏：绑定与实时正确性（开发 Brief）

> **性质**：需求 / 验收 brief（非实现说明书）  
> **日期**：2026-07-21 · **重做**（先前产物已 `revert` 至 `7812bf8`）  
> **对齐**：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) · [`flow-events.md`](flow-events.md) · [`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md)  
> **版本基线**：根目录 `VERSION` = **v0.52.1**（默认不 bump；大改可自定 bump 并跑 `check-version-sync.py`）  
> **执行者**：**Cursor**（R-15；平台改动不经 Claude Code / 不经 Engine 自消费）  
> **终验者**：规划方复跑验收 + 装机手测后收口状态板  
> **开发通道**：[`dev-channel.md`](dev-channel.md)

---

## 迭代顺序（规划方已拍板）

| Phase | 主题 | 本 brief？ |
|-------|------|------------|
| **14** | **右栏：绑定 + 实时正确性**（本文件） | ✅ |
| 15 | 右栏：卡片内容 + 视觉（对齐 UX 文档字段与密度） | 后续另发 |
| 16 | Desktop 本地优先冷启动（缓存秒开，Hub 后台） | 后续另发 |

**禁止**把 Phase15/16 塞进本阶段。

---

## 0. 你是谁、怎么干（强制）

1. 在 CCC 仓 **`main` 上直接开发**，**不要开分支**。  
2. **技术方案由你自定**；本文只规定背景、目标、硬边界、验收。  
3. 开发过程：**自己跑验收 → 语义化 commit → 可推远端**；每步可回滚。  
4. 自称「完成」无效；以文末验收为准。终验人会再跑 + **装机手测右栏**。  
5. 开始前必读：  
   - 本文  
   - [`flow-events.md`](flow-events.md)（SSE / snapshot / 绑定规则 SSOT）  
   - [`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md)（右栏产品预期；本阶段只修逻辑/实时，不重做视觉）  
   - [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)  
   - 代码：`desktop/Sources/CCCDesktop/AppModel.swift`（flow bind / SSE）  
   - `FlowRail` / `FlowCanvasView` / `FlowThreadSnapshot`（ContentView 或同名文件）  
   - Hub：`scripts/chat_server/services/flow_events.py`、`routers/desktop.py`（仅当客户端不够、必须补服务端时）  
6. 冲突时：边界基线 > `flow-events.md` > 本文 > 个人偏好。  
7. **Phase13 教训**：现网契约必须自测。禁止只跑单测就报 DONE；右栏必须 **装机或至少 `swift build` + 对照契约的自动化/半自动脚本** 后再报。

---

## 1. 背景

### 1.1 产品口径（已定）

- 左/中：对话（本机 sidecar）。  
- **右栏**：编排投影 —— **本对话绑定的 epic 竖轨时间线**，不是全局看板列表。  
- 看板：历史与列视图；右栏失败可链到运维/看板，但不把右栏做成第二看板。  
- Desktop 与 Hub 已分离：对话 SSOT 在本机会话；编排 SSOT 在 Mac2017 board + flow。

### 1.2 用户痛点（本阶段要消）

1. **跟错对象**：未绑定时挂「项目第一个 epic」；多窗/全局 `flow*` 与 `threadFlow` 双轨，偶发串台。  
2. **完成态不对**：`epic_done` 客户端忽略或晚清；done 后时间线粘住或「待拆解」误显。  
3. **实时钝**：只靠项目级 SSE + ~8s 看板轮询；他 epic 事件打扰本轨；本轨完成要等下一次无关刷新。  
4. **和对话的关系不清**：用户不知道右栏盯的是「这一次转任务」还是「整个项目随便一笔」。

### 1.3 本阶段不解决（留给 15/16）

- 卡片字段密度、视觉美化、reveal 动画精修（→ Phase15）  
- 冷启动慢、本地优先秒开（→ Phase16）  
- P3 多端 / Temporal / 主聊天回 Hub / 逐步人批  

---

## 2. 目标（用户可感知）

完成 Phase14 后：

1. **一对话一焦点**：右栏只展示 **当前 thread 的 `boundEpicId`** 对应时间线；无绑定时空态文案明确（「转任务后出现在这里」），**禁止**默默挂项目里任意一笔最近 epic。  
2. **transfer 后立刻有轨**：定稿成功 → 右栏焦点切到新 epic；扇出后 works 进入竖轨（允许短防抖）。  
3. **完成即退场**：收到完成信号（SSE `epic_done` 和/或 snapshot `user_stage=done`）→ **清空时间线**，保留 `recentEpics` 供切换；不得长期粘住旧卡。  
4. **失败可见不丢绑定**：`user_stage=failed` / abnormal 保持可见（Phase9 止损仍有效）；不误清。  
5. **实时跟本 epic**：SSE 优先处理本 `epic_id` 相关事件；他 epic 的噪声不得把本轨刷成别的任务。

---

## 3. 范围

### 3.1 必须做（What）

| # | 需求 | 成功标准 |
|---|------|----------|
| A | **绑定权威清晰** | SSOT = 本机会话 `flow.epicId`（boundEpicId）。Hub 空列表 / 空 snapshot **不得**抹掉本地未完成绑定（与 `flow-events.md`「绑定权威」一致）。无本地绑定且无合法 `bound_hint` → **空态**，不挑「列表第一笔」。 |
| B | **SSE 处理 `epic_done`** | 客户端事件过滤包含 `epic_done`；对本 epic 触发清轨（或立即 refresh 后按 done 清轨）。不得只等 8s 看板轮询。 |
| C | **SSE 与 epic 对齐** | 订阅带 `epic_id`（若 Hub 已支持）或客户端按 `data.epic_id` **过滤**；他 epic 事件不导致本轨 `epicId`/works 被换成别的任务。若需改 Hub SSE，保持 v1 兼容（查询参数可选）。 |
| D | **去掉错误双轨** | 右栏渲染以 **当前 window/thread 的 `threadFlow`** 为准；消除或严格隔离全局 `flowWorks`/`flowEpic` 回退，避免多窗串台。 |
| E | **Header / 空态文案正确** | `done` 不得显示「待拆解」；空闲与「与对话故障无关」口径保留；对齐 `flow-events.md` Header 规则。 |
| F | **文档与状态板** | 写 `docs/product/hub-shell-phase14-flow-rail-bind.md`（验收记录）；`hub-shell-phase-status.md` +1 行；`hub-shell-roadmap.md` §11 一句；`CHANGELOG` `[Unreleased]`。必要时补一句到 `flow-events.md`「客户端必须处理 epic_done」。 |
| G | **装机** | `bash desktop/scripts/package-baseline.sh` 并安装到 `/Applications`（或文档写明产物路径）；终验人按此版本手测。 |

### 3.2 明确不做

- 大改卡片视觉 / 新设计体系 / 重做 DAG 多列画布  
- 冷启动重构  
- 通知中心、逐步人批、主聊天回 Hub  
- 无必要的 Hub API 破坏性变更（新字段可加；删字段走 v2）  
- 对 CCC orch 投业务 epic（R-15）；手测可用 ccc-demo 真实/烟测 epic  

### 3.3 允许的技术选择（你定）

- 纯 Desktop 修复 vs 小改 Hub SSE（过滤/`epic_done` 推送确认）  
- 单测：Swift 测（若仓内已有）和/或 Python 契约测（Hub 事件字段）和/或新 `scripts/smoke-desktop-flow-rail-*.sh`  
- 防抖间隔可保留，但 **done 清轨不得依赖 8s 轮询作为唯一路径**

---

## 4. 工程约束

- 语义化 commit；勿 `--no-verify` / force push。  
- 契约变更：先改 docs，再改代码。  
- Desktop 改完必须 **重打包装机** 才算交付（源码 ≠ 用户打开的 App）。  
- Mac2017：若改了 Hub flow，须 `git pull` + kickstart `com.ccc.chat-server`，并在完成回复里写明。  
- 控制面不要动 invent；勿改密钥。

---

## 5. 验收清单

### 5.1 自动化（你自跑 + 终验复跑）

```bash
# 仓根
bash -n scripts/smoke-hub-shell-gate.sh   # 若你改了相关 sh
# 若新增 smoke：
# bash -n scripts/smoke-desktop-flow-rail-*.sh

# Hub 侧若有改动：
python -m py_compile scripts/chat_server/services/flow_events.py \
  scripts/chat_server/routers/desktop.py
pytest tests/scripts/ -q --tb=short -k "flow or snapshot or epic_done or stoploss"

# Desktop 至少能编过
cd desktop && swift build -c release
```

若你新增专用 smoke（推荐：对 Hub 种 epic / 模拟 `epic_done` / 断言 snapshot 字段），写入 Phase14 验收文档并保证终验可复跑。

### 5.2 装机手测（强制 · 报 DONE 前你自己做一遍）

环境：M1 Desktop（新装包）+ Mac2017 Hub（同 commit 若改了 Hub）。

| # | 步骤 | 期望 |
|---|------|------|
| 1 | 打开某业务/ccc-demo 对话，右栏无绑定 | 空态，**不是**随机历史 epic 时间线 |
| 2 | 定稿转任务一笔 small | 右栏焦点 = 新 epic；随后出现 works（或「待拆解」仅在 pending/planned 且无 works） |
| 3 | 等待扇出/推进（或用已有 in-flight epic） | 仅本 epic 状态变化；不跳成别的 epic |
| 4 | epic 至 done（或注入/等到 `epic_done`） | 时间线清空；`recentEpics` 仍可切换；Header 无「待拆解」 |
| 5 | failed / abnormal（若方便复现 Phase9 路径） | 止损可见；绑定不丢 |
| 6 | 两窗同项目不同 thread（若可）或切换 thread | 右栏不串台 |

把结果摘要写进 Phase14 验收文档（PASS/FAIL 表）。

### 5.3 DoD

- [ ] §3.1 A–G 均有交付  
- [ ] §5.1 绿；§5.2 手测表写入验收文档  
- [ ] `/Applications/CCCDesktop.app` 版本与本次构建一致（或文档标明用户须重装的路径）  
- [ ] 未混入 Phase15/16 范围  

---

## 6. 建议工作顺序（可调）

1. 摸底：读 `AppModel` SSE 过滤、`bindFlowToCurrentThread`、无绑定时 fallback；对照 `flow-events.md` 列缺口。  
2. 修绑定 + `epic_done` + 过滤/订阅 + 去全局回退。  
3. 单测/契约测 +（推荐）smoke。  
4. package-baseline 装机，手测 §5.2。  
5. 文档 / 状态板 / CHANGELOG / commit / push。  
6. 若改 Hub：2017 pull + kickstart，再手测一轮。

---

## 7. 完成时回复规划方

```text
Phase14 DONE
- HEAD: <short sha>
- VERSION: <unchanged | v…>
- Commits: …
- Desktop 装机：版本 / 时间 / 路径
- Hub 是否改动 + 2017 是否已 pull/kickstart
- 自动化验收摘要
- 手测 §5.2 表结果
- 已知风险 / 留给 Phase15 的内容项
```

---

## 8. 关联

| 文档 / 代码 | 用途 |
|-------------|------|
| [`flow-events.md`](flow-events.md) | SSE / 绑定 / done 退场 |
| [`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md) | 右栏产品预期（本阶段逻辑优先） |
| [`hub-shell-phase9-stoploss.md`](hub-shell-phase9-stoploss.md) | 失败可见，勿破坏 |
| `desktop/Sources/CCCDesktop/AppModel.swift` | bind / SSE / refresh |
| `scripts/chat_server/services/flow_events.py` | Hub 事件与 snapshot |
| [`dev-channel.md`](dev-channel.md) | 谁改 CCC / Desktop 模型默认 |

---

*Brief 作者：规划方 · 实现：Cursor · 终验：规划方*
