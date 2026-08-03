# 决策域

> 来源：种子包 `03-key-decisions.json`（qx-map `__archive__/decisions/` + hp-kb `/codex/topics/` + CCC `docs/dispatch/T31–T35`）
> 初始化：2026-08-02 · M4 刷新：2026-08-03（补 6 条新增决策） · 新决策写入本文件（追加），标注日期和状态

## 决策列表

### D1-D10: CCC 重构方案 v2（薄驱动 Engine + 文档流转 + 看板/HTTP）

- **日期**: 2026-08-02
- **状态**: approved（老板批准，方案完善版 v2，永久基线）
- **来源文件**: `ccc-refactor-方案-定稿-2026-08-02.md`
- **摘要**: CCC 重构为自给自足体系：大脑（最强 Agent）+ 薄驱动 Engine + 文档流转 + 看板/HTTP 服务。取消重型机制（角色分层、三档契约、能力包、重试预算等），保留看板/HTTP 对话页/运维页/Desktop 壳。Engine 只传话记账，不评价输出质量。v2 在 v1 基础上重排并新增 D10（杜绝硬编码）+ 终态拓扑 + 契约清单。
- **要点**:
  - D1: 薄驱动 Engine + 文档流转 + 看板/HTTP 界面
  - D2: CCC 与 QXMAP 绝对独立（运行时零依赖）
  - D3: CCC 自建知识库，改造期一次性移植外脑基础信息后独立运行
  - D4: 定时任务由 Engine 承担
  - D5: 看板 = 总调度台（实时 / 7 天 / 项目分类）
  - D6: 验收层仅安全三件套 + 基础编译/测试，深度验收归验收 Agent
  - D7: 改造期由 QXMAP 对话管理，Trae 执行，Codex 验收
  - D8: 外脑治理：重要决策落盘强制影响声明
  - D9: 中转站作为 CCC 基建配属并入 CCC 架构
  - D10: 杜绝硬编码（工具/路径/地址/任务逻辑不硬编码），验收含硬编码扫描
- **里程碑**: M1 契约定稿 / M2 Engine+看板+中转站全流程 / M3 线路图 / M4 知识移植完成 = CCC 独立移交日

---

### D11-Relay-Dual-Track: CCC 中转站双轨终态决议（D11 补充）

- **日期**: 2026-08-02
- **状态**: 生效（永久）
- **来源文件**: `ccc-relay-双轨决议-2026-08-02.md`
- **摘要**: 老板拍板：M1 中转站（ai-loop-router，4100/4102）不停用，继续使用维持现状；CCC 系统中转站已部署在 Mac2017，端口 6100/6102，为 CCC 体系专用。6100/6102 的使用方仅两个：Mac2017 侧的 Claude Code 与 OpenCode；两者均使用 flash 档位。
- **要点**:
  - M1 4100/4102 保留（ai-loop-router，Codex/Claude Code/OpenCode 智能路由）
  - Mac2017 6100 = Anthropic 出口（大脑 Agent Claude Code CLI 走此）
  - Mac2017 6102 = Relay flash 出口（OpenCode 写码槽走此）
  - 6100/6102 仅限 CCC 体系（2017 Claude Code + OpenCode + Engine env），不接纳外部工具
  - 模型档位：6100/6102 统一 flash；更高档位如需引入，另行决议
  - 「M1 旧中转站停用时机」待办关闭——双轨并行
- **影响**: M1 旧中转站停用时机待办关闭；2017 代码流转部署完成后，6100/6102 不随 M1 配置迁移，保持 2017 本地指向

---

### Closeout-Reeval-2026-08-03: CCC 重构收口重评 + T31–T35 指令

- **日期**: 2026-08-03
- **状态**: 已定稿（执行体 Trae，验收 Codex）
- **来源文件**: `ccc-refactor-收口重评-2026-08-03.md`
- **摘要**: Codex 全新取证结论：重构方向没走错，执行停在了「壳」层——账面上 T0–T30 全部闭环，但 Engine 从未真实派发、仓内权威文档仍描述旧架构、硬编码/死代码/双壳残留未清。不是方案错，是「完成」的判定标准被放宽了。收口方式：先补 Engine 真派发（T32），再统一文档基线（T31），最后清零残留（T33/T34）+ 挂账回归（T35）。
- **要点**:
  - M2 判定标准收紧：Engine 真实派发闭环（T32）完成才算 P2 收口；此前不得宣称 M2/M4 达成
  - 文档基线纳入验收硬项：每次执行体进场先对文档口径（T31），旧口径只存归档区
  - D10 与清理升为收口验收：硬编码清零（T33）、双壳/死代码/遗留物清出（T34）、挂账与回归（T35）全部通过才关闭 INT-120
  - T31–T34 可并行，T35 最后（依赖前四项产物）
- **取证发现**:
  - Engine 是空心壳：run_once 只写「模拟拉起」日志，注册表无启动命令字段，无收单实现
  - 权威文档还在讲旧系统：CLAUDE.md / STARTUP-BRIEF / docs/INDEX.md / roadmap 仍描述 Hub :7777、scripts/ 热路径
  - D10 硬编码违规：cluster.py DEFAULT_SERVICES 硬编码且服务名是旧系统；前端 utils.js/ports.js/settings.js 硬编码本机路径与 IP
  - 双壳 + 孤儿页面 + 死代码：desktop/ 与 src-tauri/ 并存；server/web/index.html 看板壳未挂载；legacy-chat 旧 Hub 文案残留
  - 跨项目遗留物：QuantHive _update_handoff.py 丢在 CCC 仓根

---

### T31-T35-Closeout-Done: T31–T35 重构收口五卡全部完成

- **日期**: 2026-08-03
- **状态**: 已回写/已关闭（5 卡全闭环）
- **来源文件**: `docs/dispatch/T31-refactor-closeout-docs-baseline.md` ~ `T35-refactor-closeout-hangover-regression.md`
- **摘要**: Codex 指令的 5 张收口卡全部执行完成并合入 origin/main：T31 文档基线切新架构（VERSION→v0.70.0，旧口径 grep 零命中）；T32 Engine 真派发闭环（注册表加启动命令、真实拉起/收单/状态流转、删「不真拉」占位）；T33 硬编码清零+集群修正（DEFAULT_SERVICES 配置化、前端路径/IP 改注入）；T34 死代码/双壳/遗留清理（孤儿看板壳与 src-tauri 归档、旧 Hub 文案清零、QuantHive 脚本移出）；T35 挂账清零+全量回归。
- **要点**:
  - T31: 11 份在范围文档全修订 + 3 份关键入口文档重写 + 14 份超范围文档标「待核/历史归档」；209 pytest 通过
  - T32: 注册表 schema 扩 command/参数模板/工作目录；dispatch.py build_command 真实 Popen；225 pytest（16 新增）；端到端演示 echo 执行体→收单→回写
  - T33: cluster.py 解析 CLUSTER_SERVICES 环境变量；server.py 加 /config 端点；238 pytest 通过
  - T34: server/web/index.html 等 4 文件归档；src-tauri/ 27 文件归档；legacy-chat 文案改「2017 单端 :7788 四视图」；238 pytest 通过
  - T35: patrol/W292/卡头状态/REFACTOR-INDEX 全部收口；双端实测；全量测试绿

---

### M2-Production-Verified: M2 里程碑生产验证通过（2017 全链路跑通）

- **日期**: 2026-08-03
- **状态**: ✅ 生产验证通过
- **来源文件**: `ccc-refactor-M2-生产验证-2026-08-03.md`
- **摘要**: Codex 在 2017 SSH 独立操作执行 M2 端到端实测：临时演示卡 T99-M2-demo 经 2017 生产 Engine + 真实执行体（Claude Code via 6100 中转站）+ 卡头回写 + 看板派生，全链路跑通。Engine 接单→真实执行→收单回写→看板派生四阶段全部生产流程验证（非模拟）。
- **要点**:
  - Engine 接单：卡头 待分派 → 执行中（守护进程心跳轮询拉起）约 40s
  - 真实执行：claude -p（经 6100 flash）读取任务卡并输出确认，约 20s
  - 收单回写：退出码 0 → 卡头 执行中 → 已回写（原子回写，问题清单为空）80s 内闭环
  - 看板派生：/board/states 已回写:1；/board/realtime 含 T99-M2-demo；静态 board.js 同步
  - 生产配置同步：executors.json 补命令+参数模板；config.env 补 EXECUTOR_LOG_DIR/DISPATCH_DIR/EXECUTOR_TIMEOUT_SECONDS/CLUSTER_SERVICES
  - 三服务重启：launchctl kickstart -k gui/501/{com.ccc.engine,com.ccc.board-scheduler,com.ccc.web-server}；com.ccc.ai-loop-router 零接触
- **里程碑状态**:
  - M1 契约: ✅
  - M2 Engine看板中转站全流程: ✅ 生产验证通过
  - M3 线路图: ✅ 接口/视图已具备（T6/T35 覆盖）
  - M4 知识移植独立移交: 骨架已建（knowledge seed），完整移植按方案 P5 另行推进

---

### D10-Hardcode-Discipline: D10 杜绝硬编码（永久纪律）细则

- **日期**: 2026-08-02
- **状态**: 永久纪律（验收含硬编码扫描）
- **来源文件**: `ccc-refactor-方案-定稿-2026-08-02.md`（§三 D10）
- **摘要**: D10 是 CCC 重构方案 v2 新增的永久纪律，包含 5 条细则：工具不硬编码（执行体按角色/能力分类注册，Engine 从注册表派发）；路径不硬编码（所有机器/项目路径走路径权威表）；地址/端口/模型/密钥不硬编码（全部配置化 env/config）；任务逻辑不硬编码（Engine 不内置业务规则，任务内容全在任务卡文档）；验收含硬编码扫描（发现硬编码即打回）。
- **要点**:
  - 1. 工具不硬编码：执行体按「角色/能力分类」注册（可后台 CLI / 手动 GUI），Engine 从执行体注册表派发，不写死任何工具名
  - 2. 路径不硬编码：所有机器/项目路径走路径权威表；代码内不出现绝对路径
  - 3. 地址/端口/模型/密钥不硬编码：中转站、看板、对话口、模型档位、API 密钥全部配置化（env/config），挪机只改配置不改代码
  - 4. 任务逻辑不硬编码：Engine 不内置业务规则，任务内容全在任务卡文档；规则进文档，不写死在程序里
  - 5. 验收含硬编码扫描：发现硬编码即打回
- **执行**: T33 收口卡已完成硬编码清零（cluster.py DEFAULT_SERVICES 配置化 + 前端路径/IP 改 /config 注入），三扫描零命中

---

### 双工具共管外脑——心智独立、事实单一端口

- **日期**: 2026-08-02
- **状态**: 已落地并验证
- **来源文件**: `external-brain-dual-tools-2026-08-02.md`
- **摘要**: Codex 与 Claude Code 共同运维外脑，各自保持心智独立（Codex 读 AGENTS.md、Claude Code 读 CLAUDE.md），事实层只认 AGENTS.md 一份权威。方案/决策全文唯一主档 = `__archive__/decisions/`。hp-kb 降级为检索索引（仅标题+摘要+指针）。管理席去单点（Codex 与 Claude Code 皆可为管理/验收席，但执行席与验收席强制异席）。
- **要点**:
  - 心智独立：各工具读各自入口文件，事实层只认一份权威
  - 决策文件唯一写点：`__archive__/decisions/`
  - hp-kb 降级为检索索引
  - 管理席去单点，执行席与验收席强制异席

---

### 职责角色化——工具绑定与规则文档解耦

- **日期**: 2026-08-02
- **状态**: 已落地并验证
- **来源文件**: `tool-roles-decoupling-2026-08-02.md`
- **摘要**: 将「角色（能力槽位）」和「工具（当前实现）」解耦。规则文档只写角色名（主力入口体/知识查询体/开发执行体等），唯一绑定表 `ide/tool-roles.md` 是所有角色→工具绑定的唯一事实源。机器守卫（`check-tool-roles.py`）强制四条硬规则 + 白名单令牌警告。换工具只改绑定表 + 入口薄封装。
- **要点**:
  - 规则文档只写角色名，不写工具名
  - 唯一绑定表 `ide/tool-roles.md`
  - 机器守卫（`check-tool-roles.py`）强制校验
  - 换工具 SOP：改绑定表 → 换入口 → 跑校验 → 重跑同步 → 决策留痕

---

### 意图表机制守卫（防撞号 · 防状态乱 · 防结果缺失）

- **日期**: 2026-08-02
- **状态**: 已落地并验证
- **来源文件**: `intents-mechanism-guard-2026-08-02.md`
- **摘要**: 意图总表 54 条记录中 18 个编号重复使用，根因是两套意图序列并行起号。修复：编号分区（主表 001~099 / CCC 轨 101~199，INT-100 保留禁用），机器守卫（`check-intents.py`）强制五条规则（编号格式/唯一/轨道分区/状态机/终态必填结果列），同步链路强制复检。
- **要点**:
  - 编号分区：主表 001~099，CCC 轨 101~199
  - 机器守卫 `check-intents.py` 强制五条规则
  - 同步链路每日自动复检
  - 写前纪律：回写完成后必须跑校验

---

### medio-0 S5 阶段审核

- **日期**: 2026-08-02
- **状态**: 审核完成
- **来源文件**: `medio-0-s5-review-2026-08-02.md`
- **摘要**: medio-0 项目 S5 阶段代码审核与验收。

---

### medio-0 Trae 独立简要说明

- **日期**: 2026-08-01
- **状态**: 已记录
- **来源文件**: `medio-0-trae-standalone-brief-2026-08-01.md`
- **摘要**: medio-0 项目中 Trae 工具独立使用的简要说明和配置。

---

## 新增决策模板

```
### 决策标题

- **日期**: YYYY-MM-DD
- **状态**: 待定 / 已批准 / 已落地并验证 / 已废弃
- **摘要**: 一句话总结
- **要点**:
  - 要点1
  - 要点2
```
