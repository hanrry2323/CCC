# 任务卡 mx008 · HTTP 页面体验巡检（RSS 优先）（OpenCode 执行）

> 关联：ccc-plan: HTTP 页面体验巡检：RSS 优先 + 全页面代码/显示/双端适配 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

medio-0 HTTP 页面体验巡检（纯只读，不开发）：**RSS 优先**——专项排查 RSS 页/订阅功能的代码问题与显示问题；再全页面巡检（播放/媒体库/设置/登录/首页等）的代码问题、显示问题，并按 PC 端 / 移动端双端适配标注；输出 ≥10 项问题清单（分代码/显示/PC/移动四类，每项现状+建议+成本）回写 `docs/roadmap.md`「业务线路（mx）」段，作为后续修复卡拆分依据。

## 红线（先看）

1. **绝对禁止**修改、添加、删除 medio-0 业务仓（`/Users/fan/program/apps/medio-0`）任何文件；只读 `ls`/`cat`/`git log`/`rg`；禁止 `cargo build`/`npm install`/启服务/改配置。
2. 文档改动**只允许**在 CCC 仓本机：`docs/roadmap.md`、`docs/projects/mx/README.md`、本任务卡。
3. 禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/mx/xxx.md` 业务详文）。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- 只读侦察：`/Users/fan/program/apps/medio-0`（前端页面组件 `src/frontend/src`、RSS 相关前后端代码路径、`docs/lessons.md` 已知问题、响应式/Tailwind 适配、移动端处理逻辑）
- 回写：`docs/roadmap.md`「业务线路（mx）」段追加问题清单；`docs/projects/mx/README.md`「线路 / 近况」≤3 行同步一句

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，先读 `docs/lessons.md` 与 `adr/`（重点 RSS 相关教训：HTML tags 过滤、RSS 双栏、增量扫描网络挂载误删保护），建立已知问题基线。
2. **RSS 专项（优先，重点产出）**：`rg -n "rss|RSS" src/` 梳理 RSS 前后端代码路径（抓取/解析/过滤/展示/双栏），逐路径复核：
   - 代码问题：HTML 过滤实现、解析健壮性、错误处理、并发/定时任务风险
   - 显示问题：RSS 条目渲染（缩略图/标题/日期/摘要）、双栏布局、加载态与空态
   - 结论：每项标注 现状 + 问题 + 建议 + 预估成本（S/M/L）
3. **全页面巡检**：`src/frontend/src` 按页面组件逐个检查（播放页/媒体库页/设置页/登录页/首页/随机发现等）：
   - 代码问题：`rg -n "TODO|FIXME|HACK|any|@ts-ignore" src/`、错误处理缺失、状态管理隐患
   - 显示问题：布局错乱风险、loading/empty/error 三态、Toast/弹窗一致性
   - 双端适配：Tailwind 断点使用、移动端触摸/尺寸处理（参考 mx005 清单第 9 项移动端防呆）、桌面键盘交互
4. 整理问题清单（≥10 项）：分四类（代码/显示/PC 端/移动端），每项写「页面 + 现状 + 建议动作 + 预估成本」；RSS 相关项单独标 P0/P1/P2 优先级。
5. 回写 `docs/roadmap.md`「业务线路（mx）」段：追加「HTTP 页面巡检清单（mx008）」子段；`docs/projects/mx/README.md`「线路 / 近况」≤3 行同步一句。
6. 探针自检：`git -C /Users/fan/program/apps/medio-0 status -sb` clean（业务仓零改动）；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. RSS 专项排查：RSS 页/订阅功能代码问题与显示问题清单（含现有 HTML 过滤、双栏、增量扫描误删保护相关代码路径复核结论）
2. 全页面巡检：其余页面（播放/媒体库/设置/登录/首页等）代码问题与显示问题清单，按 代码/显示/PC端/移动端 四类标注，每项含现状+建议+预估成本
3. 问题清单（≥10 项）回写 docs/roadmap.md「业务线路（mx）」段；RSS 问题单独标记优先级
4. medio-0 业务仓零改动（纯只读）；python3 -m server.board.validate docs/dispatch 通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 1. 实现说明
严格按照任务卡要求，对业务仓 `medio-0`（`/Users/fan/program/apps/medio-0`）的前后端进行了全面只读巡检。重点排查了 RSS 页/订阅功能、已知教训、HTML tags 过滤、RSS 3栏/双栏布局，并针对全页面代码问题、显示问题、PC端与移动端双端适配进行了深度盘点，共输出并整理了 12 项高质量问题清单。
巡检清单分类汇总后已回写至 `docs/roadmap.md`「业务线路（mx）」段，并同步更新了 `docs/projects/mx/README.md`「线路 / 近况」部分，作为后续修复卡拆分依据。

### 2. 测试与自检结果
- 业务仓状态自检：`git -C /Users/fan/program/apps/medio-0 status -sb` 为 clean，符合零改动红线。
- 任务卡校验：运行 `python3 -m server.board.validate docs/dispatch`，卡头及格式校验 100% 通过。

### 3. Push 证据 (Commit Hash)
- 审计回写 Commit Hash: `ab1d263ec88faf2655f60f67b843bad89bc232a1` (short: `ab1d263e`)
- 本卡回写 Commit Hash: fcc6ac155c180240eeb1efe77ded79d9bda2e89b (short: fcc6ac15)

## 机审区

机审：通过
