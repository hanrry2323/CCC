# 任务卡 T56 · T-B1 统一卡片组件层（Claude Code 执行）

> 关联：阶段 3（T-B1 统一卡片组件，过夜任务前端链 1/2）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t56-card-components`（先 `git fetch origin main && git checkout -b codex/t56-card-components origin/main`）
> **分步提交纪律（硬）**：每完成一个逻辑块立即 commit+push；超时 7200s。与 T55（索引层）并行，文件所有权见下。

## 目标

统一卡片组件层：TaskCard / TaskCardList（分页+虚拟滚动）/ TaskCardDetail + cardApi 统一数据层，看板与右栏卡流接入（消灭三套渲染）。

## 具体项

1. **cardApi**：统一数据层——分页列表 `GET /cards?project=&state=&page=`、搜索 `GET /cards/search?q=`（协议与 T55 对齐，接口若未上线则先实现前端调用层，后端上线后即可用）。
2. **TaskCard**：状态徽章 + ID + 标题 + 执行体 + 打回次数 + 更新时间；色板唯一来源（STATE_TONE 五态）。
3. **TaskCardList**：分页/虚拟滚动/空态/加载态/筛选参数——看板列表与右栏卡流复用。
4. **TaskCardDetail**：统一详情面板（描述/验收/回写/时间线）。
5. **接入**：看板（boardPage）与对话右栏卡流（boardPanel）改接 cardApi+TaskCard*（控制台 T-B3 后置）；删除各自拼 DOM 的旧渲染。

## 红线

1. 只改 server/web/legacy-chat/（js/components/、js/pages/、css/）+ tests；**禁止改 server/board、server/engine、server/web/server.py（T55 所有权）**。
2. 零新依赖（纯 JS）；状态色板与桌面端 StateTone 一致。
3. 回写前 push 成功并附证据。

## 验收标准

1. headless 实测：看板列表（分页/筛选）与右栏卡流用统一组件渲染，数据与 /cards 一致；无重复渲染路径（旧拼 DOM 代码删除）。
2. 虚拟滚动：500+ 卡场景流畅（可用临时数据验证）。
3. TaskCardDetail 展开详情正确（描述/验收/回写/时间线）。
4. 零 console error；pytest 全绿（如涉）；push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：组件结构、cardApi 协议、接入范围、headless 实测（截图/文本）、删除旧渲染清单、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
