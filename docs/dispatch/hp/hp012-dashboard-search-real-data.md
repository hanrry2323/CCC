# 任务卡 hp012 · Dashboard 与 Search 页面真实数据接入（清假数据）（OpenCode 执行）

> 关联：ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-08

## 目标

Dashboard 与 Search 页面真实数据接入（清假数据）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Dashboard.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Search.tsx`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. Dashboard.tsx 活跃项目/热门标签/最近动态改为渲染 fetch 的真实数据（/api/projects/status、/api/tags、/api/timeline），删除 FALLBACK_PROJECTS/FALLBACK_TAGS/FALLBACK_RECENT/FALLBACK_TIMELINE 无条件渲染
2. Search.tsx 删除 FALLBACK_RESULTS/FALLBACK_HISTORY/FALLBACK_SUGGESTIONS：无结果时显示「无结果」空态，不展示编造结果；耗时/引擎写死值移除
3. 页面空数据/后端不可达时显示真实错误 banner（safeJson _warning），不 fallback 假内容
4. npm run build 通过、npm test 通过；接口验证 Dashboard 展示真实项目名（如 claude-code/docs/qb）而非 HermesPet/Mavis
5. 改动提交到 codex/hp012-dashboard-search-real-data 分支，回写区含改造前后对照

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
