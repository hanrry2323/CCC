# 方案 · clwarp 审计梳理与历史债务清理（M4）

> 项目：clw · 编号：clw-plan-006 · 状态：部分执行 · 作者：Claude（中枢） · 工具：Claude Code
> 创建：2026-08-15 · 更新：2026-08-15
> 关联卡：clw027
> 关联方案：clw-plan-001/002/003/005（已完成历史方案）；clw-plan-004（已作废，归档不再执行）
> 里程碑：M4 · 审计梳理与债务清理

## 目标

清理 clw 项目在 CCC 侧与业务仓的 8 处历史债务，让「文档描述 = 代码实况」，作为新 CCC 框架下 clw 自动化开发的第一程（M4）。

## 背景

clw 是新框架梳理的首个项目。三路并行调查（本地文档 / 远端代码 / 流程基线）发现：代码仓已是真实完整的 v0.3.0（53 commits 已发布），但 CCC 侧文档遗留 8 处不一致与悬空。在进入下一程（M5 Codex 加固）前，先把基线对齐，避免把旧债带进新开发。

8 处遗留（源自 2026-08-15 中枢三路调查）：
1. `clw-plan-004`（agent 状态感知）已作废，但 roadmap 仍挂「待启动」——矛盾
2. `clw022` 编号空缺（clw021→clw023 跳号），全仓无踪迹
3. 交付报告只有 v0.1.0 一份，v0.2.0 / v0.3.0 缺 delivery 报告
4. `AGENTS.md`（业务仓）残留「GPU 原生终端渲染」过时表述（实际 xterm.js 前端渲染）
5. 全局 `docs/roadmap.md` 业务线路表格只到 clw007，clw008-025 只在注记里
6. clw004/005 分支孤岛（功能最终由 clw011 兑现，CCC 卡已关闭）
7. clw019/020 挂 clw 前缀但实属 ccc-plan-020（集群 Worker 池）验证卡
8. `docs/projects/clw/README.md` 近况未同步到 clw021 / clw023-025

## 方案内容

分两块执行：

**A · CCC 仓文档债务清理（中枢直接执行，不转卡）**
- A1：`roadmap.md` 移除「agent 状态感知」待启动里程碑（plan-004 彻底放弃），M4/M5 就位 ✅（已随本方案落库完成）
- A2：`clw022` 编号空缺登记说明（在 README 或本方案备注注明：预留编号未使用，序列保持 clw021→clw023）
- A3：`knowledge/domains/projects/clw-skill.md` 技术栈纠偏（GPU 渲染 → xterm.js 前端渲染 + alacritty 仅 PTY）
- A4：全局 `docs/roadmap.md` clw 业务线路表格补全到 clw025（含 0.3.0 会话加固）
- A5：`docs/projects/clw/README.md` 近况同步到 clw021 / clw023-025（v0.3.0 追加加固）
- A6：clw019/020 归属标注（在 README/卡头注明「关联 ccc-plan-020，非 clw 业务卡」）
- A7：补齐交付报告 `clw-delivery-002`（v0.2.0）、`clw-delivery-003`（v0.3.0）

**B · 业务仓文档纠偏（功能卡 clw026，产线执行）**
- B1：clwarp 仓 `AGENTS.md`「GPU 原生终端渲染」过时表述纠偏为 xterm.js（详见下方功能卡）

## 验收标准

- [ ] `roadmap.md` 已移除「agent 状态感知」里程碑，M4/M5 就位，状态正确
- [ ] `clw022` 编号空缺已登记说明，无歧义
- [ ] `clw-skill.md` 技术栈与 README 定稿一致（无 GPU 渲染表述）
- [ ] 全局 `docs/roadmap.md` clw 业务线路表格补全到 clw025
- [ ] `README.md` 近况同步到 clw021 / clw023-025
- [ ] clw019/020 归属 ccc-plan-020 已标注
- [ ] `clw-delivery-002` / `clw-delivery-003` 已补齐（CHANGELOG / RELEASE / Git Tag / 可复跑验证）
- [ ] clwarp `AGENTS.md` 无「GPU 原生渲染」过时表述（功能卡 clw026 验收）
- [ ] `scripts/validate-plans.sh` 全绿

## 功能卡

> 一个功能一张卡（ccc-plan-027 拆卡原则）。节点② 老板确认此清单后一次转卡（粒度 A）。

### clwarp AGENTS.md 技术栈表述纠偏

目标：修正 clwarp 仓 `AGENTS.md` 中过时的「GPU 原生终端渲染」表述，与 README 技术栈定稿一致（前端 `@xterm/xterm` 渲染，`alacritty_terminal` 仅作 PTY 后端）。只改文档，不动代码。

实现：
- 读 `clwarp/AGENTS.md`，定位「GPU 原生终端渲染 / Metal GPU」类表述
- 改写为「xterm.js 前端渲染 + alacritty 仅 PTY」的准确描述，与 `README.md` 技术栈定稿一致
- 全文扫描无其他技术栈冲突表述后提交

验收：
- `AGENTS.md` 全文件无「GPU 渲染」类过时表述
- 技术栈描述与 `README.md` 一致（xterm.js 前端渲染）
- 仅改文档，无代码改动；`cargo build` / `npm` 均不受影响

## 转卡计划

```ccc-plan
title: clwarp 审计梳理与历史债务清理（M4）——业务仓 AGENTS.md 纠偏
project: clw
slices:
  - title: "clwarp AGENTS.md 技术栈表述纠偏（GPU 原生渲染 → xterm.js 前端渲染）"
    slug: agents-md-fix
    executor: OpenCode
    acceptance:
      - "clwarp/AGENTS.md 全文件无「GPU 渲染」类过时表述（定位第 5 行附近「GPU 原生终端渲染」）"
      - "技术栈描述与 README.md 定稿一致：前端 @xterm/xterm 渲染，alacritty_terminal 仅作 PTY 后端"
      - "仅改文档不改代码；不引入新功能"
    whitelist:
      - "AGENTS.md"
```

## 备注

- **本方案为调度 + 中枢执行混合**：A 块（CCC 仓 7 处）由中枢直接执行，B 块（业务仓 AGENTS.md）出功能卡给产线
- **红线**：不代执行业务仓代码改动；业务仓只允许改 `AGENTS.md` 文档；不动 `README.md` 的代码/配置描述之外内容（README 技术栈定稿为唯一权威）
- **范围外**：agent 状态感知已彻底放弃；M5 Codex 体验加固**已撤销**（Codex 弃用，不立项）
- **项目封板（2026-08-15 老板决策）**：CLW 在 M4 收尾（clw027 跑通）后里程碑封板，项目生命周期完成——定位转「历史尝试型项目 · 示范样板」；主线资源转向 DSH + CCC 插件化（ccc-plan-029）
- plan-004 作废：关联的 herdr 参考文件在仓内不存在，作废成立，roadmap 不再挂此里程碑
