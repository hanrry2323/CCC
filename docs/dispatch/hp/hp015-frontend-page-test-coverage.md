# 任务卡 hp015 · 前端页面测试覆盖（React Testing Library）（OpenCode 执行）

> 关联：ccc-plan: HP 前端测试覆盖补齐（页面渲染 + 关键交互，目标测试评分 4→7） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-08

## 目标

前端页面测试覆盖（React Testing Library）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/Users/fan/program/apps/hp/local/graph/dashboard/src/__tests__/`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/components/`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/store.ts`
- `/Users/fan/program/apps/hp/local/graph/dashboard/package.json`
- `/Users/fan/program/apps/hp/local/graph/dashboard/vitest.config.ts`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 引入 React Testing Library + jest-dom 依赖（若 vitest 已配置则复用），package.json 更新测试脚本
2. 页面渲染测试：Dashboard 真数据渲染（mock /api 返回真实项目名如 claude-code/docs/qb，断言渲染）、Dashboard 空态渲染、Search 空结果显示「无结果」空态（不显示 FALLBACK 假数据）、Library 过滤（status/tag 参数传递正确 + 空态）、Document 404 空态
3. 交互测试：主题切换（light/dark/auto 持久化 localStorage）、Spotlight 打开/关闭、NoteModal 保存/删除笔记调用真实 api
4. 测试全绿：npm test 全部通过（含已有 api.test.ts 9 个 + 新增页面测试），覆盖率报告显示页面组件有覆盖
5. 测试代码提交到 codex/hp015-frontend-page-test-coverage 分支（hp 仓），回写区含测试清单与通过证据

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
