# 方案 · 全链自动化闭环：DSH 出卡 → Claude CLI 开发 → CC 审核 → 部署

> 项目：ccc · 编号：ccc-plan-053 · 状态：待排期（含 2 个拍板点，拍板前不动手） · 作者：外脑（ZC-M1 · 老板 2026-08-29 直派） · 工具：ZCode（2017 开发窗口为本方案实施主力）
> 创建：2026-08-29 · 更新：2026-08-29
> 关联卡：无（拍板前不动手；实施按「功能卡」拆解）
> 关联方案：ccc-plan-052（其第 1 期被本方案阶段 4 全盘采纳）· ccc-plan-051（巡检服务段联动）· ccc-plan-050（合入自动化=本方案运行时语义）· ccc-plan-049（前端展示线，独立推进）
> 取证基线：本仓 main @ `a3680ef5f`（2026-08-29 P0 收口）。key 链路实测（2026-08-29 外脑亲测）：`OPENCODE_GO_API_KEY`（~/.zshrc:39）网关探针 200；`claude -p` 端到端回包 OK（模型 deepseek-v4-flash 已默认，~/.zshrc:40-44）；dsh-web plist 旧 key（sk-cFDJ…，即 429 源）已换新 key（备份 `com.deepseek.dsh-web.plist.bak-20260829-keyrot`）；`scripts/dsh-key-check.sh` 探针 200。

## 目标

把「目标 → 出卡 → 开发 → 审核 → 合入 → 部署 → 终态」全链变成标准流程：**DSH 负责出任务卡，Claude CLI（2017 ZCode，deepseek-v4-flash）作为开发主力把每张卡跑完部署流程**；全程看板/ledger 可观测，人工介入点可配置（拍板点 2）。

## 终点流程定义（角色逐一钉死，禁自由发挥）

| # | 环节 | 执行者 | 输入 | 输出 | 既有基础 |
|---|---|---|---|---|---|
| 1 | 出卡 | DSH 会话 | 老板/外脑的目标指令 | `docs/dispatch/<prefix>/<id>.md` + git push | 卡格式现成（tst998/999 实件）；缺 DSH 产卡桥（阶段 2 新建） |
| 2 | 卡校验门 | engine（派发前强制） | 卡文件 | 合法卡入池；非法卡拒+ledger 告警 | 无，阶段 2 新建 |
| 3 | 派发 | engine run_loop | 待分派卡 | 认领+派发记录 | 加固后 run_loop 现成（恢复=052 卡B） |
| 4 | 开发 | **Claude CLI headless（拍板点 1）** | 卡文件+worktree | 代码+自测+卡头 `状态=已回写` | worker-claim.sh EXEC_TOOL 机制现成（默认 opencode，支持 claude -p） |
| 5 | CC 审核 | phase2（独立 Claude CLI 会话，零共享上下文） | 已回写卡+diff | 通过→合入；不通过→打回 | phase2 现成（a3680ef5f 全绿） |
| 6 | 合入+部署 | phase2 `deploy_and_probe`（phase2.py:438） | 已合入 main | deploy-ccc.sh（fetch+ff→pytest 门禁→kickstart）→探活 | 脚本在；指向修复=052 卡C |
| 7 | 终态 | phase2 | 探活成功 | 卡=已关闭 + ledger `phase2_pass` + 分支清理 | 分支清理 652c316f3 已就位 |

**卡头规范（出卡模板钉死，首行与引用行一字不改）**：

```markdown
# 任务卡 <prefix><NNN> · <一句话标题>

> 关联：<plan-id> · 执行体：<W号> · 验收：<角色> · 状态：待分派 · 派发：engine · 项目：<prefix> · 日期：YYYY-MM-DD
```

正文必备段：目标 / 实现要求 / 红线 / 范围 / 步骤（每步有可验证产物）/ 验收标准（≥1 条可核）。

## 拍板点（2 个，回复即视为拍板）

1. **开发执行体 = Claude CLI headless（推荐，即你 08-29「开发主力=2017 ZCode」定调的落地）**：executors.json 开发执行体绑 `scripts/claude-executor.sh`（阶段 3 新建）；DSH 转出卡/编排位。备选=维持 DSH 开发（executors.json 一行切回 `dsh-executor.sh`，本方案其余全部不变）。真枪（阶段 1）形态随本拍板：推荐形态=「CLI 开发+CC 审核」一步验证新形态；备选=「DSH 开发+CC 审核」=交接单原形态。
2. **值班节奏**：真枪通过+legacy 机审拆净后，是否开 7×24 全自动（engine launchd 常驻即自动派发）。外脑建议：先以 phase2 --daemon 半自动过渡 1-2 周，全绿再放全自动。

## 实施阶段（顺序有依赖，不得跳序）

### 阶段 0 · legacy 机审拆除（前置必修，不拆禁恢复 engine）

加固报告项 1 遗留实锤：run_loop（main.py:5059）同时跑 legacy `_run_audit_worker`（main.py:4904 活链路，`EXECUTOR_MAX_AUDIT_CONCURRENT=3` 未关闸）与 phase2 CC 消费（main.py:5123）——**engine 一旦恢复即对同一批已回写卡双审冲突**。
拆除范围：run_once 填槽段（`_audit_round`）+ 3 个直接 import 调用的测试文件 + ENGINEERING-CANON.md:147 与 plans 021/028 文档联动改写。
验收：`grep -rn _run_audit_worker server/ docs/` 零活引用；全量 pytest 绿（EXIT=0）。

### 阶段 1 · 真枪复跑（一张卡全链）

形态按拍板点 1。验收（沿用交接单 v3 口径，不改）：board 终态=已关闭 + ledger 含 `phase2_pass`；外脑独立复核（双向实测，不采信自报）。触发：08-30 15:00 闹钟查配额→外脑拟指令→老板转发→窗口执行。前置：若拍 CLI 开发，先落阶段 3 wrapper 最小版（读卡→实现→自测→回写）。

### 阶段 2 · DSH 出卡桥 + 卡校验门

1. DSH 侧产卡模板（skill/prompt 钉死上文卡头规范，禁改字段名）；产卡动作=写 `docs/dispatch/<prefix>/` → `git commit` → `git push`。
2. 卡校验门（engine 派发前强制）：必填字段齐全 / 状态=待分派 / 项目前缀在 registry / 验收标准≥1 / 范围路径存在；非法卡转「打回」+ ledger 告警。
3. 防呆红线维持：**DSH 只出卡，不执行、不审核、不自改 CCC 仓**（自改禁出卡红线继续有效）；出的是业务卡，由 engine 派发、CLI 执行、phase2 审核，三席分离不变。
验收：DSH 产 1 张测试卡过校验门入池；1 张故意缺字段卡被拒+告警留痕。

### 阶段 3 · claude-executor wrapper 注册

1. 新 `scripts/claude-executor.sh`：参数模板与 dsh-executor.sh 完全一致（`{card_path} {work_id} {worktree} {role} {biz_worktree}`）；内部 `claude -p` headless（权限沿用 2017 settings bypassPermissions）；**env 自包含**——显式 `export ANTHROPIC_BASE_URL=https://opencode.ai/zen/go` + `ANTHROPIC_MODEL=deepseek-v4-flash`，key 经 `source scripts/dsh-key.sh` 单源（launchd 环境无 zshrc，必须自含）；**派发前调 `scripts/dsh-key-check.sh`，429 即拒单**，防无声 429 循环。
2. `executors.json` 开发/维护执行体命令切为 claude-executor.sh；`dsh-executor.sh` 条目保留备选；example 模板同步。
验收：headless 领 1 张 tst 测试卡→改文件→自测→回写成功；`env -i` 模拟 launchd 环境同流程通。

### 阶段 4 · 常驻化 = 052 第 1 期全盘采纳

web-server + engine launchd 恢复、kickstart/deploy 脚本对齐两服务、巡检服务段联动 051 卡B。验收=ccc-plan-052 第 1 期清单原文，此处不重复。

### 阶段 5 · 值班节奏启用（按拍板点 2）

全自动=engine 常驻即 7×24 派发（配额护栏=dsh-key-check 强制预检）；半自动=phase2 --daemon 常驻、派发手动。

## 风险与对策

| # | 风险 | 对策 |
|---|---|---|
| R1 | 开发与审核同为 deepseek-v4-flash，模型多样性下降 | 审核独立会话零共享上下文；卡内验收标准为唯一判据（不靠模型感觉）；外脑对交付逐卡抽审（评估职责）；如需异模型审核，audit 席可走中转站其他可用档——**由老板定，禁自行增设上游** |
| R2 | opencode go 周配额再次耗尽（429） | dsh-key-check.sh 探针+ledger 告警+exit 2 阻断已有；wrapper/engine 派发前强制预检；配额状态入每日巡检与外脑晨报 |
| R3 | DSH 出卡质量参差（拆解过粗/验收不可核） | 卡校验门机器拦截 + 外脑入池抽审；连续 2 张被拒即暂停出卡、待外脑复盘后再开 |
| R4 | 跳过阶段 0 恢复 engine 即双审 | 阶段 0 写成 launchd 装回的硬前置：boot engine 前必须 grep 断言 legacy worker 已拆 |

## 验收标准（总）

- [ ] 阶段 0-5 各自验收全过，顺序无跳越
- [ ] 一张业务卡从「DSH 出卡」到「部署探活+已关闭」全程零人工（全自动态）
- [ ] ledger 七事件留痕可查：出卡/认领/回写/审核/合入/部署/终态
- [ ] 全量 pytest 绿（EXIT=0）；交付由外脑独立复核，不采信自报

## 功能卡

### C0 · legacy 机审拆除专项

目标/实现/验收=§阶段 0。
颗粒度：run_once 段+3 测试文件+文档联动。
依赖：无（**必须最先做**）。
架构位置：server/engine/main.py + server/tests/ + docs。

### C1 · 真枪复跑

目标：全链一卡验证（形态随拍板点 1）。
实现：既有流程执行，零代码；若拍 CLI 开发则依赖 C3 最小版先行。
验收：board 关闭+ledger phase2_pass+外脑独立复核。
颗粒度：运行面演练，零代码改动。
依赖：C0（engine 路径）；纯手动触发可暂不依赖。
架构位置：2017 运行面（board/ledger/phase2）。

### C2 · DSH 出卡桥+卡校验门

目标=§阶段 2。
颗粒度：DSH 侧产卡模板+engine 校验器约 150 行。
依赖：无（可与 C0 并行）。
架构位置：~/.dsh（2017 本机）+ server/engine/。

### C3 · claude-executor wrapper

目标=§阶段 3。
颗粒度：1 脚本+executors.json 两处+example 同步。
依赖：C1 通过（通道已验）。
架构位置：scripts/ + server/config/。

### C4 · 052 第 1 期实施

按 ccc-plan-052 功能卡 A/B/C 原文执行，本卡不重复其内容。
颗粒度：沿用 052 卡 A/B/C 各自颗粒度（两服务切换+两脚本小改）。
依赖：**C0 完成**（engine 装回硬前置）。
架构位置：2017 launchd + scripts/kickstart-ccc.sh + scripts/deploy-ccc.sh。

### C5 · 值班节奏启用

按拍板点 2 切换全自动/半自动。
颗粒度：运行面配置切换，零代码。
依赖：C1-C4 全过。
架构位置：2017 launchd 运行面（engine 常驻 or phase2 --daemon）。
