# Hub-Shell Phase15 — Desktop 右栏：卡片内容与视觉（开发 Brief）

> **性质**：需求 / 验收 brief（非实现说明书）  
> **日期**：2026-07-21 · 对齐 [`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md) · [`flow-events.md`](flow-events.md)  
> **版本基线**：`VERSION` = **v0.52.1**（默认不 bump；大改可自定 bump + `check-version-sync.py`）  
> **执行者**：**Cursor**（R-15；见 [`dev-channel.md`](dev-channel.md)）在 **main 上直接开发**  
> **终验者**：规划方复跑 + 装机手测后收口状态板  
> **前置**：Phase14 右栏绑定/实时（须先完成重做；本阶段**不要重做**绑定/SSE，除非修回归）

---

## 迭代顺序

| Phase | 主题 | 本 brief？ |
|-------|------|------------|
| 14 | 右栏绑定 + 实时 | **green（Cursor 重做）** |
| **15** | **右栏卡片内容 + 视觉**（本文件） | ✅ |
| 16 | Desktop 本地优先冷启动 | 后续另发 |

**禁止**把 Phase16 或大范围绑定重构塞进本阶段。

---

## 0. 你是谁、怎么干（强制）

1. **`main` 上直接开发**，不要开分支。  
2. **技术方案你自定**；本文定目标、边界、验收。  
3. 自己验收 → 语义化 commit → 可 push。  
4. 自称完成无效；以文末验收为准。  
5. 开始前必读：  
   - 本文  
   - [`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md)（**本阶段主 SSOT**）  
   - [`flow-events.md`](flow-events.md)（字段契约）  
   - [`hub-shell-phase14-flow-rail-bind.md`](hub-shell-phase14-flow-rail-bind.md)（勿破坏绑定/done 清轨）  
   - `desktop/Sources/CCCDesktop/FlowCanvasView.swift`、`FlowNodeView`、`FlowRail`（ContentView）、`Models.swift`（`FlowWork`/`FlowEpic`/`FlowSnapshot`）  
6. 冲突时：UX 文档阶段表 > 本文 > 个人审美。

### 0.1 Phase13/14 教训（本阶段硬规则）

| 规则 | 要求 |
|------|------|
| 装机必须可证伪 | `package-baseline` 后 **`cp -R` 到 `/Applications`**；报 DONE 时贴：`stat` 装机二进制 mtime **与** `.build` 一致（禁止只编不装） |
| 手测不可 deferred | §5.2 **至少 4 项**写成「我亲眼看到…」；禁止整表「代码合规 / deferred」 |
| 不扩 Hub 协议 | 优先消费 **已有** snapshot 字段；确需新字段才改 Hub，且向后兼容 |
| 不破坏 Phase14 | done 清轨、`epic_done`、无 `epics.first` 乱绑、SSE epic 过滤必须保持 |

---

## 1. 背景

### 1.1 用户痛点

右栏「能跟 epic」之后，卡片仍难用：

1. **内容干**：Hub 已有 `goal_summary` / `executor_label` / `depends_on_titles` / `failure_note` / `note` / `headline` / `user_status`，卡片上用得少，多藏在 sheet。  
2. **阶段话术不对齐**：UX 表要求 pending→failed 各有主文案/次要信息；现状常只剩标题+色点。  
3. **视觉与层次弱**：状态优先级（running / failed）、依赖关系、空态/完成态可读性不足；reveal 可能闪一下。  
4. **和看板关系弱**：失败可去运维，但从 work 卡到「看板里那张卡」的路径弱（本阶段允许最小深链，不重做看板页）。

### 1.2 本阶段目标一句话

**让右栏竖轨「一眼能盯进度」**：卡片信息密度对齐 UX 文档；视觉层次清楚；不改绑定/SSE 主逻辑。

---

## 2. 目标（用户可感知）

1. **Epic 头**：始终能看到阶段主文案（对齐 UX 表：待拆解 / 已拆 N 步 / 正在：… / 验收中 / 已完成 / 卡住…）；有目标时露出 **一句** `goal_summary`（或等价）。  
2. **Work 卡**：标题 + 人话状态（`user_status` 优先于生硬列名）+ 执行面白话（`executor_label`）+ 依赖用**标题**（`depends_on_titles`）；失败时卡上可见 `failure_note`（或一行原因），不必先开 sheet。  
3. **testing / running**：次要行可露 `note` 摘要（截断）；不要整墙日志。  
4. **空态 / done**：空态保留「与对话故障无关」口径；done 清轨后不强塞旧卡（Phase14 行为保留）。  
5. **视觉**：竖轨层次清楚（当前活动段强调、失败醒目、完成弱化可选）；减少无意义闪烁；点击仍可开 sheet 看全文。  
6. **可选加分**：work 失败 → 一键到运维或看板（已有则打磨；不要新造通知中心）。

---

## 3. 范围

### 3.1 必须做（What）

| # | 需求 | 成功标准 |
|---|------|----------|
| A | **阶段文案对齐 UX 表** | Header / Epic 区按 `user_stage`（及有无 works）显示主文案；`done` 不显示「待拆解」 |
| B | **字段上卡** | 卡片或紧邻次要行消费：`goal_summary`（epic）、`executor_label`、`depends_on_titles`、`failure_note`；`note` 在 testing/running 可截断显示 |
| C | **Sheet 仍完整** | 点击节点：目标/状态/失败/依赖全文；卡上是摘要，sheet 是详情 |
| D | **视觉层次** | running 可辨；failed 强于普通；空态不空洞；reveal 不导致整轨闪白/消失再出现（可减动画或改触发） |
| E | **不回归 Phase14** | 绑定权威、`epic_done` 清轨、SSE 过滤行为保持；相关单测仍绿 |
| F | **文档** | `docs/product/hub-shell-phase15-flow-rail-cards.md` 验收记录；`hub-shell-phase-status.md` +1；roadmap §11 一句；CHANGELOG `[Unreleased]`；必要时补 UX 文档「已落地」勾选 |
| G | **装机可证伪** | 见 §0.1：`/Applications` mtime = `.build` mtime；报 DONE 贴命令输出 |

### 3.2 明确不做

- Phase16 冷启动 / 本地优先  
- 真多列 DAG / 力导向 / 缩放画布（UX「后续」）  
- 节点预览完整 plan/report 文件  
- 重做绑定/SSE（除非修本阶段引入的回归）  
- 通知中心、逐步人批、主聊天回 Hub、P3  
- 大改全局 Design System（只动右栏相关 SwiftUI）  
- 对 CCC orch 投业务 epic（R-15）

### 3.3 允许你自定

- 纯 SwiftUI 改 `FlowCanvasView` / `FlowNodeView` / `FlowRail` vs 抽小组件  
- 是否微调 Hub snapshot 字段填充（若字段有但常空）——须向后兼容 + 测  
- 截断长度、字号、色 token（避免紫光晕、默认 Inter 堆砌；跟随现有 Desktop 视觉语言）

---

## 4. 工程约束

- 语义化 commit；勿 force / `--no-verify`。  
- 契约：先 docs（若改字段语义），再代码。  
- Desktop 改完必须 package + **真正**装进 `/Applications`。  
- 若改 Hub：Mac2017 `git pull` + kickstart `com.ccc.chat-server`，完成回复写明。  
- 控制面 / 密钥不动。

---

## 5. 验收清单

### 5.1 自动化

```bash
# Phase14 不回归
pytest tests/scripts/ -q --tb=short -k "phase14 or flow or snapshot or epic_done or stoploss"

# 若改 Hub
python -m py_compile scripts/chat_server/services/flow_events.py \
  scripts/chat_server/routers/desktop.py

# Desktop
cd desktop && swift build -c release
bash desktop/scripts/package-baseline.sh
# 装机（必须）
rm -rf /Applications/CCCDesktop.app
cp -R desktop/.build/CCCDesktop.app /Applications/
# 证伪（必须贴输出）
stat -f '%Sm %N' -t '%Y-%m-%d %H:%M' \
  /Applications/CCCDesktop.app/Contents/MacOS/CCCDesktop \
  desktop/.build/CCCDesktop.app/Contents/MacOS/CCCDesktop
# 两行时间必须一致

python3 scripts/check-version-sync.py
```

可选：为卡片字段映射加轻量单测/快照测（有则加分）。

### 5.2 装机手测（强制 · 不可整表 deferred）

环境：新装 `/Applications/CCCDesktop.app` + Mac2017 Hub（若改了 Hub 须已对齐）。

| # | 步骤 | 期望 | 你必须填写 |
|---|------|------|------------|
| 1 | 打开有进行中 epic 的项目（或先 transfer 一笔） | Epic 头有阶段主文案；有目标则见一句 goal | 亲眼看到的文案原文 |
| 2 | 扇出后看 work 卡 | 见执行面白话和/或依赖标题；不只是生硬列名 | 卡上可见字段列表 |
| 3 | 若有失败/abnormal（或 Phase9 路径） | 卡上有原因摘要；止损/运维仍可用 | PASS/FAIL |
| 4 | 点开一张卡 sheet | 详情完整；关 sheet 回竖轨不丢绑定 | PASS/FAIL |
| 5 | epic done 后 | 清轨；不粘旧卡；无「待拆解」 | PASS/FAIL |
| 6 | 空闲项目/无绑定（或非 main 且无历史） | 空态可读；不假装有进度 | PASS/FAIL |

至少 **#1 #2 #4 #5** 必须为实填（非 deferred）。无失败样例时 #3 可写「无样例，代码路径说明」。

### 5.3 DoD

- [ ] §3.1 A–G  
- [ ] §5.1 绿 + 装机 mtime 一致  
- [ ] §5.2 至少 4 项实填  
- [ ] Phase14 相关测仍绿  
- [ ] 未混入 Phase16  

---

## 6. 建议工作顺序

1. 对照 UX 表 vs `FlowNodeView` 现状，列「缺字段 / 错文案 / 闪烁」清单写入验收文档草稿。  
2. 先内容映射，再视觉层次，最后动效收敛。  
3. 跑 §5.1 → 装机 → §5.2 实填。  
4. 状态板 / CHANGELOG / commit / push。  

---

## 7. 完成时回复规划方

```text
Phase15 DONE
- HEAD: <short sha>
- VERSION: …
- Commits: …
- 装机证伪（两行 stat 输出）: …
- Hub 是否改动 + 2017 对齐: …
- 自动化摘要: …
- 手测 §5.2（含亲眼看到的文案）: …
- 留给 Phase16 / 已知风险: …
```

---

## 8. 关联

| 文档 / 代码 | 用途 |
|-------------|------|
| [`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md) | 主 SSOT |
| [`flow-events.md`](flow-events.md) | 字段与事件 |
| [`hub-shell-phase14-flow-rail-bind.md`](hub-shell-phase14-flow-rail-bind.md) | 绑定不回归 |
| `FlowCanvasView.swift` / `Models.swift` | 实现面 |

---

*Brief 作者：规划方 · 实现：Claude · 终验：规划方*
