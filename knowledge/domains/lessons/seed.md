# 教训域

> 来源：种子包 `04-lessons.json`（`docs/lessons.md` + qx-map `__archive__/lessons/` + `references/red-lines.md` + `ccc-refactor-收口重评-2026-08-03.md`）
> 初始化：2026-08-02 · M4 刷新：2026-08-03（补 4 条收口期新教训 LC1–LC4） · 新教训写入本文件（追加），标注编号和日期

## CCC 核心教训

### L1: Plan 必须用自然语言，不能写具体命令
- **根因**: Plan 中出现裸命令（如 `git push origin main`）导致 agent 被当成 shell 执行器
- **修复**: 角色描述加了「输出原则：用自然语言描述目标，不写具体命令」

### L2: Executor 超时后 planner 不应越界 commit
- **根因**: 任务超时后 planner 自己执行 git commit + git push，越界
- **修复**: 角色描述加了「不执行、不 commit、不 push」红线

### L3: Executor 静默退出——prompt 缺完成定义
- **根因**: Executor 跑完主要工作后静默退出，没跑 commit + 写 report。prompt 缺少完成定义
- **修复**: 模板加「完成定义」段：所有改动已 commit / phases.json 标 done / report.md 已写入，退出前跑自检

### L4: report.md 必须前置创建
- **根因**: Lesson 3 修复后 Executor 仍跳过写报告步骤，因为「完成定义」中报告排在 commit 之后
- **修复**: 强制执行顺序：先创建空 report.md 框架（前置，避免漏）

### L5-L10: 执行完成定义、阶段顺序、自检机制等系列教训
- **涉及**: plan 必须先设计、executor 超时兜底、phases.json 状态机一致性、commit 纪律等

### L21: 教训随代码迁入 CCC 仓库
- **涉及**: CCC 从 qxo 子项目独立为立项项目后，所有教训随代码迁入 CCC 仓库

### L28-L32: CCC 工程化教训系列
- **涉及**: verdict 文件必须写、agent 自主启用 CCC 红线、卡死立即止损、每步必 commit 等工程纪律

## CCC 收口期新教训（2026-08-03）

### LC1: 文档口径分裂导致执行漂移
- **日期**: 2026-08-03
- **来源**: `ccc-refactor-收口重评-2026-08-03.md` §三.2 + T28 越界改 CLAUDE.md 事件
- **现象**: T0–T30 账面全部闭环，但仓内权威文档（CLAUDE.md / STARTUP-BRIEF / docs/INDEX.md / roadmap / server README / pyproject）仍描述旧架构（Hub :7777、scripts/ 热路径、能力包、M1 Desktop+sidecar）。执行体按这些文档进场必然漂移——T28 越界改 CLAUDE.md 即证据。
- **根因**: 文档基线未纳入验收硬项；「代码改了」≠「文档同步了」；旧口径只标废弃不物理删除的纪律没贯彻，导致新旧口径并存
- **修复**: T31 收口卡：11 份在范围文档全修订 + 3 份关键入口文档重写 + 14 份超范围文档标「待核/历史归档」；旧口径 grep 零命中；文档基线纳入每次执行体进场验收硬项
- **应用**: 每次执行体进场先对文档口径（T31 模板），旧口径只存归档区；文档与代码同次验收，缺一即打回

### LC2: 验收判定放宽导致 Engine 壳层
- **日期**: 2026-08-03
- **来源**: `ccc-refactor-收口重评-2026-08-03.md` §三.1 + §四.1
- **现象**: Engine 从未真实派发——run_once 只写「模拟拉起」日志，注册表无启动命令字段，无收单实现。但 M2「首个任务经 Engine 全流程」却被宣称达成。不是方案错，是「完成」的判定标准被放宽了：把「壳层就绪」当成「闭环达成」。
- **根因**: M2 判定标准未明确收紧到「真实派发闭环」；占位代码（「T4 前不真拉」「模拟拉起」）被当成已完成功能验收通过
- **修复**: T32 收口卡：M2 判定标准收紧为「Engine 真实派发闭环完成才算 P2 收口」；注册表加启动命令字段；dispatch.py build_command 真实 Popen + 收单 + 状态流转；删全部占位；M2 由 Codex 在 2017 SSH 独立端到端实测验证（T99-M2-demo）
- **应用**: 里程碑判定必须由独立验收席端到端实测（非自报）；占位代码必须标注并禁止进入验收；「壳层就绪」≠「闭环达成」

### LC3: 生产配置与代码 schema 脱节
- **日期**: 2026-08-03
- **来源**: `ccc-refactor-M2-生产验证-2026-08-03.md` §一.2 + T32/T33 任务卡
- **现象**: T32 给注册表加了 command/参数模板/工作目录字段，但 2017 生产 executors.json 没同步——直到 M2 实测前才补：OpenCode/Claude Code 两行补命令绝对路径 + 参数模板（含 {work_id}/{card_path}/{role} 占位符）。T33 给 cluster.py 加了 CLUSTER_SERVICES 环境变量，但 2017 config.env 没补——直到 M2 实测前才补 EXECUTOR_LOG_DIR/DISPATCH_DIR/EXECUTOR_TIMEOUT_SECONDS/CLUSTER_SERVICES 四键。
- **根因**: 代码 schema 扩展与生产配置变更未同次推进；本地通过 ≠ 生产就绪；example 文件改了但实际 config.env/executors.json（gitignored）未同步
- **修复**: M2 实测前由 Codex 在 2017 SSH 同步生产配置（先备份 .bak.M2 再改）；executors.json 补命令+参数模板；config.env 补四键
- **应用**: 代码 schema 扩展时，example + 生产配置同步清单必须写进任务卡验收项；生产配置变更必须先备份再改；M2 类端到端实测前必须由独立验收席核对配置同步

### LC4: 挂载死功能残留
- **日期**: 2026-08-03
- **来源**: `ccc-refactor-收口重评-2026-08-03.md` §三.4 + §三.5 + T34 任务卡
- **现象**: T0–T30 闭环后仓内残留四类死功能：①双壳并存（desktop/ SwiftUI 现行 + src-tauri/ Tauri 旧 Cockpit）；②孤儿页面（server/web/index.html 看板壳未被静态白名单挂载，整组 js/css 成孤儿）；③旧 Hub 文案残留（legacy-chat 「对话在 M1 :7788」）；④跨项目遗留物（QuantHive _update_handoff.py 丢在 CCC 仓根未跟踪）。
- **根因**: 新功能上线后旧实现未归档（双壳）；静态资源挂载白名单未与文件实际存在对齐（孤儿页面）；文案未跟随架构变更同步（旧 Hub 文案）；跨项目工作树污染未清理（QuantHive 脚本）
- **修复**: T34 收口卡：src-tauri/ 27 文件归档到 `docs/archive/ccc-legacy-2026-08-02/tauri-desktop-legacy/`；server/web/index.html 等 4 文件归档到 orphan-shell-web/；legacy-chat 文案改「2017 单端 :7788 四视图」；QuantHive _update_handoff.py 移到 /tmp；11 份项目文件更新引用
- **应用**: 新功能上线时旧实现必须同卡归档（git mv，禁物理删除）；静态资源挂载白名单定期与文件实际存在对账；文案跟随架构变更同步；跨项目工作树污染每日清理

## 外脑教训

### EB-L1: HP 操作直接走 CLI，不试 MCP
- **日期**: 2026-07-29
- **根因**: MCP 写操作受限时不应让用户代劳
- **修复**: 所有 HP 操作直接走 CLI，保持突破思维而非受限心态

### EB-L2: launchd 脚本要保证 PATH
- **日期**: 2026-08-01
- **根因**: launchd 里跑脚本缺 `~/.codex/bin` 会让 hp-kb CLI 误报未安装
- **修复**: 明确设置 PATH 环境变量

### EB-L3: 端口表要标注口径
- **日期**: 2026-08-01
- **根因**: M1 探测 vs 远程确认是两个视角，不标注就会自相矛盾
- **修复**: 端口表标注探测口径

### EB-L4: 健康检查要打真实存在的端点
- **日期**: 2026-08-01
- **根因**: memory-store 只有 `/memories`，打 `/health` 永远 404 误报
- **修复**: 健康检查打真实端点

### EB-L5: 状态类记录一律带时间戳
- **日期**: 2026-08-01
- **根因**: 状态类信息（磁盘、服务状态）会变，禁止写永久断言
- **修复**: 状态类记录一律带时间戳或「以当日 manifest 为准」

## 工程红线（CCC 核心）

| # | 红线 | 一句话 |
|---|------|--------|
| R1 | 不动系统文件 | /etc、~/.env、密钥不改 |
| R2 | 验收必须可执行 | 自然语言 + 可选命令 |
| R3 | 不超出 plan 范围 | 白名单外不动 |
| R4 | 单 phase 单 commit | 兜底由脚本做 |
| R5 | phases.json 必写全 | JSONL，不嵌套 |
| R6 | 角色不互串 | product 不写代码，reviewer 不写 plan |
| R7 | 启动顺序固定 | 读 state.md + profile.md 第一 |
| R8 | 每步必 commit | exec-commit 兜底 |
| R9 | 卡死立即止损 | kill + 下一个角色接管 |
| R10 | 禁止跨会话隐式记忆 | state.md 强制接力 |
| R11 | Verdict 必须写 verdict 文件 | 口头 PASS 不算 |
| R12 | 禁止 agent 自主启用 CCC | 用户显式触发 |

完整 18 条 + X 系列(8) + R 系列(7) 见 `references/red-lines.md`。

## CCC 重构红线

1. 不破独立：CCC 运行时不读不写外脑，违反即漂移
2. 最强脑不抢执行：脑负责拆方案/验收/裁决，不自己下场写码
3. 验收 Agent 不能砍薄：唯一质量兜底，必须接知识库、能看全上下文
4. 定时任务默认只读，变更类保留确认
5. 线路图是派生视图，禁止手工维护
6. 旧内容标废弃不删除；删除权在老板
7. 杜绝硬编码（D10 细则），验收含硬编码扫描
8. 多壳必须锁门：对话口账号密码 + 会话 token

## 新增教训模板

```
### L-N: 教训标题
- **日期**: YYYY-MM-DD
- **根因**: 发生了什么
- **修复**: 怎么修
```
