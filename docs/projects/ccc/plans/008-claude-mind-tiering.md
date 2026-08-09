# 方案 · Claude Code 心智分层方案

> 项目：ccc · 编号：ccc-plan-008 · 状态：已确认 · 作者：老板 · 工具：Claude Code
> 创建：2026-08-03 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无
> 迁移自：qx-map `__archive__/decisions/claude-code-心智分层-方案-2026-08-03.md`
> 备注：待核——是否已被 2026-08-06 双脑架构替代
> 日期：2026-08-03
> 背景：CCC 会话全盘排查心智冲突，四类发现经 qx-map 侧独立核实，全部属实或修正定性后成立。
> 原则（老板定）：全局中性 · 项目隔离 · 各项目职责不同。

---

## 一、核实结论（全部带证据）

| # | 冲突项 | 核实结果 | 证据 |
|---|--------|---------|------|
| 1 | m1-env-config.md 过期自相矛盾 | ✅ 属实 | `effortLevel: medium` vs `~/.claude/settings.json`=`effortLevel: xhigh`；`FREEZE.md: CCC 平台开发已冻结` vs FREEZE.md 不存在且 8/2–8/3 持续开发（T22–T27）；MCP 同一文件两行矛盾（`memory + fetch` + `无 MCP config`）vs `~/.claude/.mcp.json` 真实存在 |
| 2 | agent-mind/decided.json 僵尸目标 | ✅ 属实 | 主仓 `/Users/apple/program/CCC/.ccc/agent-mind/decided.json` + 9 个 worktree 全有；goal `g-14d07e4b59`「加标记」dispatched（8/2 12:24 更新），5 仓还有「第一笔」「第二笔」；文本模糊、exit_condition 裸 pytest，与看板 T26/T27 脱节 |
| 3 | QuantHive SSE 记忆互斥 | ⚠️ 修正定性 | 非「两条做法互斥」——是「一条悬挂待裁决 + 一条已出结论」。`git-index-race.md`(8/1 10:39) 标「A 收口时裁决」；`sse-shared-pool.md`(8/1 11:00) 已给结论「逐流独立 XREAD + 尾 id 增量，6/6 修复」，与 INT-004 终裁「逐流+尾 id 胜出」一致。真实问题是第一条未收口 |
| 4 | 全局 vs 项目 CLAUDE.md 席位措辞 | ✅ 属实 | 全局「不受四席限制、全功能」；CCC 项目「Claude Code=运维 · 开发工具=开发席」；qx-map 项目「开发执行体+方案评审者」。运行时以项目文件为准故不炸，但全局给相反信号 |

---

## 二、心智分层模型（目标态）

```
┌─ 全局（~/.claude/CLAUDE.md）────── 中性：通用能力 + 安全红线 + 工作风格
│   不定义任何项目的职责/角色/席位
│   声明「项目 CLAUDE.md 优先于全局」
├─ 项目 CLAUDE.md（CCC / QuantHive / qb / qx-map）
│   各自定义自己的职责、角色、红线、工作流 ← 职责唯一的定义处
├─ 用户级记忆（~/.claude/projects/-Users-apple/memory/）
│   只放跨项目通用事实（如 Windows SSH quirk）← 禁止项目状态
└─ 项目记忆（<project>/memory/）
    只放该项目独有决策/教训；有仓内 decisions/ 的以仓内为准
```

**判据**：心智冲突的根源 = 全局文件里混入项目状态 + 记忆里存了会变的状态快照。分层后：
- 职责只在项目层定义，全局不重复 → 措辞冲突消失
- 状态不落记忆（或落记忆必须带「以实际配置为准」验证提示）→ 过期冲突消失
- 决策全文只在仓内 decisions/，记忆只做索引 → 单一事实源（qx-map 已定，推广到各项目）

---

## 三、处置清单（按优先级）

### P0 — 全局 CLAUDE.md 中性化（需老板确认文案后改）
改法：删对抗性措辞，职责下沉到项目。
- 删「禁止任何形式的自我限制」「不受任何四席限制」「禁止推诿给 Cursor/Desktop/Codex」等否定式对抗句 → 改为中性能力声明
- 「项目职责」表（我负责 CCC/QuantHive/qb）→ 改为「各项目职责以各自 CLAUDE.md 为准」
- 保留：xhigh effort、MCP 全开、操作风格（结论先行/不甩选择题/带证据）
- 新增优先级硬规则：**项目 CLAUDE.md > 全局 CLAUDE.md > 记忆**
- 推荐文案见 §四

### P1 — 用户级记忆瘦身（可逆，可随 P0 一起做）
- `cluster-windows-ssh-quirk.md` 保留（跨项目通用事实，符合定位）
- `m1-env-config.md` 剥离：删 CCC 专属段（角色/控制面/FREEZE）与过期段（effort/FREEZE/MCP 矛盾）；保留纯通用（硬件/语言运行时/密钥路径安全提醒）。或整档删除（信息已在 settings.json + 各仓文档）

### P1 — QuantHive SSE 记忆收口（一处编辑）
- `git-index-race.md`：「A 收口时裁决」→「已裁决 = 逐流 + 尾 id 增量（INT-004 终裁，见 [[sse-shared-pool-missed-fills]]）」

### P2 — agent-mind 僵尸目标（CCC 管理席）
- 非 Claude Code 心智，是 CCC Hub 侧产物（主仓 + 9 worktree 的 `.ccc/agent-mind/decided.json`）
- 处置：CCC 管理席把 3 笔 dispatched 打 done/归档；另登记机制问题「agent-mind 目标投递无收尾闭环」（7-29 投递至今全 dispatched）
- Claude Code 不越权改 CCC 侧

### P2 — 项目 CLAUDE.md 消歧（可选）
- CCC/QuantHive/qx-map 项目文件角色定义已各自明确，保持
- P0 中性化后，全局不再给相反信号，张力自然消除，无需额外改动

---

## 四、全局 CLAUDE.md 推荐文案（草稿）

```markdown
# Claude Code — 全栈项目助理（通用心智）

> 通用能力声明 + 安全红线。**具体项目的职责、角色、红线一律以该项目 CLAUDE.md 为准，项目定义优先于本文件。**

## 通用定位
- 全栈工程助理：写代码、架构设计、运维排障、项目管理。
- 能力不绑定任何工具/席位；本文件不定义你在具体项目中的角色。
- 各项目（CCC / QuantHive / qb / …）的职责分工见各自 CLAUDE.md。

## 通用工作原则
1. 结论先行，直接给最佳方案，不甩选择题。
2. 能动手就动手；需要老板决策时给推荐让他选。
3. 每条结论可核实：带证据（文件名/行号/命令输出）。
4. 最高 effort：xhigh（settings.json 已配）。
5. MCP 能力全开。

## 安全红线（所有项目通用）
1. 不碰密钥明文 / 运行面黑名单；密钥只允许占位引用。
2. 显式路径提交，禁 `git add -A`；业务代码提交到各自仓。
3. 方案/决策落仓内唯一路径（如 qx-map `__archive__/decisions/`），不建第二套描述。
4. 执行席/验收席分离：不审自己写的活，不自我放行。
```

---

## 五、执行路径
1. 老板确认 §四 文案 → 改 `~/.claude/CLAUDE.md`
2. 同步执行 P1 两项（m1-env-config 瘦身 / QuantHive SSE 收口）
3. P2 两项转 CCC 管理席登记，不本会话执行
