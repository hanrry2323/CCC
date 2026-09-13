# 任务卡 xy073 · 工作流可视化页最小版（xy009 6.4）

> 关联：xy-plan-009（前端展示台 · M6 6.4 工作流可视化）+ xy-plan-008 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy073 · 状态版本：1
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓，DSH 在业务 worktree 改）

## 目标
实现 xy-plan-009 6.4「工作流可视化页」最小版：在 xianyu 的 admin/index.html 增加一个「工作流状态」区，展示运行中任务的阶段流转（消费现有工作流状态入口；若 `GET /api/v1/workflows` 尚未实现，则最小实现一个返回运行中任务 state 的接口）。让生产展示台能看到任务阶段，而非只有静态页面。

## 实现要求
- 在 `admin/index.html` 增加「工作流状态」区块：列出运行中任务 ID + 当前 stage + 状态（运行中/失败），页面加载时请求接口渲染。
- 后端：若已有 workflows 状态接口则直接消费；若无，在现有 API 最小加一个 `GET /api/v1/workflows`（返回运行中任务数组），或复用现有能表达任务状态的接口。
- 补对应最小测试（后端接口返回正确 + 前端区块存在）。
- 接口/页面改动要小：整体 diff **<300 行**，单卡一发命中。

## 红线
- 只改 xianyu 业务仓；范围=admin/index.html + 后端 API 一处 + 一个测试文件。
- 禁碰：CCC 仓文件（docs/projects/xy/*）、M7 发布/Cookie、video-pipeline 核心逻辑、publish 通路。
- 改完 commit + push 当前分支（codex/xy073），让信封可见（phase2 自动合入依赖）。
- 禁推 main（phase2 会自动合入，勿手工）。

## 范围
- /Users/fan/program/apps/xianyu/admin/index.html
- /Users/fan/program/apps/xianyu/src/xianyu
- /Users/fan/program/apps/xianyu/tests

## 步骤
1. 读 admin/index.html 现值 + 找现有 API 入口（src/xianyu/ 下路由/接口）。
2. 确认是否有 workflows 状态接口可用；无则最小加一个。
3. 前端加「工作流状态」区 + fetch 渲染。
4. 后端接口补测试；跑相关测试绿。
5. commit + push codex/xy073，写 .ccc-result.md（五段）交回写，停手（phase2 会自动合入 main）。

## 验收标准
1. `GET /api/v1/workflows`（或复用接口）返回运行中任务 stage 数组（测试绿）。
2. admin/index.html 有工作流状态区块且 fetch 渲染（无 console 报错）。
3. diff 总 <300 行。
4. 测试通过数 ≥2（后端 + 前端存在性）。
5. 本卡走完产线后 **phase2 自动合入 main**（main 出现 codex/xy073 的 merge，无需人工补合）——这是 F1 修复的自证。

## 门禁
- card_gate 五项校验（必填齐全、状态=待分派、项目 xy 在 registry、验收=DSH、范围路径在仓内存在）——本卡全部满足。

## 回写要求
- 回写区四问逐项填；教训沉淀引用 docs/notes 具体文件（机审 Q2 要求）。

## 人工批注
无批注。

## 回写区
1. 方案同步：[是] xy-plan-009 6.4 实现，本卡号 xy073。
2. 教训沉淀：[否]（若有机审要求时改 [是] + 具体文件路径）。
3. 档案/README：[否] 内部页面，不涉接口契约对外。
4. 线路图：[否] 不涉 roadmap。