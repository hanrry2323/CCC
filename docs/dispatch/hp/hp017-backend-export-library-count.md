# 任务卡 hp017 · 后端接口补齐（export 导出 + library 计数）（OpenCode 执行）

> 关联：ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-08

## 目标

后端接口补齐（export 导出 + library 计数）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/data/knowledge/local/graph/server.py`
- `/data/knowledge/local/graph/`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/api.ts`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 后端新增 /api/export 接口：真实导出知识库文档元数据为 zip + json 索引（或等价可下载格式），供前端「导出」按钮使用
2. 后端 /api/library 扩展返回 count_by_status（全部/已发布/草稿/已归档 各计数），供前端 TAB 使用
3. 后端 api.ts 增加 fetchExport 与 count_by_status 类型声明（仅 api.ts 一层，不涉页面）
4. 后端回归测试通过（pytest 相关）；接口实测返回正确数据
5. 后端与 api.ts 改动提交到 codex/hp014-backend-export-library-count 分支，回写区含接口文档与测试证据

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
