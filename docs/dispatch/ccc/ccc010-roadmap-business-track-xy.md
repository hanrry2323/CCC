# 任务卡 ccc010 · 总线路图：roadmap 增业务线路（xy）总览段（OpenCode 执行）

> 关联：ccc-plan: 文档卫生与业务总线路图 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-07

## 目标

总线路图：roadmap 增业务线路（xy）总览段（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `docs/roadmap.md`
- `docs/projects/xy/README.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. docs/roadmap.md 含「业务线路（xy）」段：视频质量 5 卡（xy009-013）进度 + 下一程意向一行
2. docs/projects/xy/README.md 线路/近况 ≤3 行同步
3. validate 通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 实现说明

1. 成功在 `docs/roadmap.md` 末尾增设 `## 业务线路（xy）` 全新总览段，详细罗列了 `xy009` 到 `xy013` 共 5 张视频质量加固核心任务卡片的进度，且其状态均精确标识为「待分派」，并附上了业务下一程意向的归纳。
2. 同步在 `docs/projects/xy/README.md` 中的 `## 线路 / 近况` 段落进行了 ≤3 行（实际 2 行）的极简精准同步，确保两处描述绝对一致。

### 测试结果

- 通过了 `python3 -m server.board.validate docs/dispatch` 任务卡与看板全量一致性对账校验。
- 通过了后端全量单元测试：`python3 -m pytest server/tests/ -q --tb=short` 100% green。

### push 证据

- **分支**：`codex/ccc010-roadmap-business-track-xy`
- **Commit Hash**：`1cc13130103be07084026965b93d8181662e7ae6`
