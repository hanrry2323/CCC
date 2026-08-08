# 任务卡 hp013 · Library/Document/Activity/Notes 页面真实数据接入与空态统一（OpenCode 执行）

> 关联：ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-08

## 目标

Library/Document/Activity/Notes 页面真实数据接入与空态统一（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Library.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Document.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Activity.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Notes.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/components/NoteModal.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/components/EmptyState.tsx`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. Library.tsx 删除 FALLBACK_DOCS 与硬编码 TABS count：空数据/过滤无结果显示空态；TAB count 接后端 count_by_status（后端接口 hp014 落地前先用真实文档总数，接口就绪后切换）
2. Library「导出」按钮改为调用 /api/export 并下载 zip（原生 fetch，不依赖 api.ts 新函数；接口由 hp014 后端补齐）
3. Document.tsx 删除 FALLBACK_DOC/FALLBACK_BACKLINKS/FALLBACK_NOTES：文档不存在/空显示 404 空态
4. Activity.tsx 删除 FALLBACK 假时间线；Notes.tsx 初始不预填 FALLBACK_NOTES，空态兜底；saveNote/deleteNote 保持真实 /api/notes 写接口
5. 新建统一 EmptyState 组件并用于上述页面空态
6. npm run build 通过、npm test 通过；接口验证 Document 展示真实文档内容
7. 改动提交到 codex/hp013-library-doc-activity-notes-real-data 分支，回写区含对照

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
