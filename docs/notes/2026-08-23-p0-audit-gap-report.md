# P0 排查报告 · 两环节模型漏洞（P0-1 机审自验收 + P0-2 ledger 真值自证）

> 记录：S116-01 · 2017 Claude Code（环节② 审核合入席）· 2026-08-23
> 依据：老板执行指令（两环节模型漏洞排查与加固）· 审核红线：绝不信 DSH 执行过程，只认独立核验证据
> 状态：**盘点完成，修复设计待老板确认**

---

## P0-1 · 机审自验收模式核查

### 1.1 现状（实锤）

| 事实 | 证据 |
|------|------|
| 开发与机审同工具 | `server/board/roles.py:48-49` `DEFAULT_EXECUTOR = DEFAULT_ACCEPTANCE = "DSH"`；`executors.json` 验收席=DSH |
| 机审"检查"全是 DSH 自述 | `~/.dsh/.agent-presets/dsh-auditor/agent.cordis.yml`（v4 心智：范围核对→找茬→severity→分流→维护区核对→写机审区，全由 DSH 单 agent 执行） |
| 机审真值=DSH 写的文本 | `server/engine/main.py:901-951` `_audit_evidence_passed`：只验卡文件机审区文本「机审：通过」（分支信封 git show 或本地兜底） |
| ledger 由 engine 代写 | `main.py:2984-3009` `_record_machine_audit_pass`：engine 读到 DSH 文本后写 ledger |
| 机械门禁前置仅 1 类 | `scripts/dsh-auditor.sh:67-87`：只有「维护区四问」机械校验，其余全靠 DSH 预设执行 |

### 1.2 dsh-auditor 实际检查的断言类型（盘点）

| # | 断言类型 | 执行方 | 独立于 DSH 的机械核验 | 现状 |
|---|---------|--------|----------------------|------|
| 1 | **范围合规**（改动在卡白名单内）| DSH 自述 | ❌ 无 | 仅机审后漂移检查（被审 sha 后非卡文件改动=拒绝，`approve-merge.sh:435-456`），但"被审 sha"本身是 DSH 写的 |
| 2 | **git 提交真实性**（push 证据/commit 存在）| DSH 自述 | ⚠️ 部分 | approve-merge 会 git 拉分支验证分支存在，但不验证 DSH 声称的 commit 是否存在 |
| 3 | **测试是否真跑** | DSH 自述 | ❌ 无 | 无任何机械核验"测试输出"真实性 |
| 4 | **维护区四问** | 机械门禁 | ✅ 有 | `docgate.verify_maintenance`（dsh-auditor.sh + approve-merge 双处），校验勾选/说明非空/方案同步 |
| 5 | **质量不劣化**（L1 增量分）| 机械 | ✅ 有 | `approve-merge.sh:559-566` quality-score --record（软告警） |
| 6 | **架构漂移/版本一致** | 机械 | ✅ 有 | `arch-drift-check.sh`（approve-merge 前置） |
| 7 | **密钥/凭据** | 机械 | ✅ 有 | `approve-merge.sh:161-176` secret-scan（diff 正则） |
| 8 | **ledger provenance** | 机械 | ✅ 有 | `approve-merge.sh:470-486` 账本 machine_audit_pass 硬校验（08-22 P0-3 单源化） |

**结论**：8 类断言中，**4 类（范围/git真实性/测试真跑/业务质量）完全依赖 DSH 自述，无第二道独立机械核验**。机审通过的真值链 = DSH 写文本 → engine 读文本写 ledger → approve-merge 验 ledger。**若 DSH 整体撒谎（写假通过+假范围+假测试），现有机制会一路放行。**

### 1.3 第二道独立检测：现状与设计

**明确回答老板问题**：DSH 机审整体被绕过或撒谎时，现有机制**没有**第二道独立检测手段——
- ledger 的 `machine_audit_pass` 是 engine 读到 DSH 写的文本后落账的，**来源仍是 DSH 自述**；
- 机审后漂移检查（pin commit）只能防"机审后再改代码"，防不了"机审时就是假的"；
- 维护区/密钥/架构漂移/质量分是"机械合规门禁"，不是"机审结论真实性"的检测。

**需设计**（建议老板确认后实施）：
- **独立复核清单落进 approve-merge.sh 为强制步骤**（非心智软提醒）：① git log 真实性（被审 sha 在 origin 存在且是开发分支 tip）② diff 范围 vs 卡白名单（机械比对文件清单）③ 测试真跑证据（卡声明的测试命令输出留档 + 合入时抽查重跑）④ ledger 记录 vs 分支信封实际内容。
- **抽验机制（第二道检测）**：环节② 验收时随机抽 N 张卡，对分支 **独立重跑测试命令**（不信任 DSH 留存输出），比对差异。

---

## P0-2 · 机审 ledger 真值来源自证

### 2.1 DSH 是否有权限写自己的 preset（结论：有）

| 检查 | 结果 |
|------|------|
| `~/.dsh/.agent-presets/` 权限 | `drwxr-xr-x`，当前用户 `fan` 可写（stat 确认） |
| `~/.dsh/.agent-presets/dsh-auditor/agent.cordis.yml` | `-rw------- fan` 可写 |
| 风险 | DSH headless 会话以 `fan` 运行，**理论上可改自己的机审预设**（放宽审查标准/伪造输出） |

**建议**：`agent-presets` 改只读（chmod 444 或 chown root）或加外部校验（预设文件 sha256 与引擎侧登记比对）。**需老板确认**（涉及 DSH 运行权限，可能影响 DSH 日常预设更新）。

### 2.2 机审通过卡抽样复核报告

**抽查方法**：ledger 全量扫描 → 过滤 pytest 污染（test 源 + `/private/var/folders` 路径）→ 真实生产 `machine_audit_pass` 记录仅 **7 张** → 逐张核对 ledger 记录 vs main 卡实际机审区 vs 分支信封 vs 关闭状态。

**核对结果**：

| 卡 | ledger machine_audit_pass | main 卡机审区 | 分支信封 | 关闭 | 结论 |
|----|--------------------------|--------------|---------|------|------|
| mx053 | ✅ 08-19 | ✅ 通过 | 已删 | ✅ 已关闭 | 一致（08-20 合入）|
| mx056 | ✅ 08-19 | ✅ 通过 | 已删 | ✅ 已关闭 | 一致（08-20 合入）|
| mx057 | ✅ 08-19 | ✅ 通过 | 已删 | ✅ 已关闭 | 一致（08-20 合入）|
| xy053 | ✅ 08-20 | ✅ 通过 | 已删 | ✅ 已关闭 | 一致（08-20 合入）|
| xy054 | ✅ 08-20 | ✅ 通过 | 已删 | ✅ 已关闭 | 一致（08-21 合入）|
| **xy055** | ✅ 08-20 | **❌ 占位「（机审方填写）」** | 已删 | ✅ 已关闭 | **⚠️ 断裂：ledger 有记录但 main 卡机审区是占位，仍被合入** |
| tst002 | ✅ 08-23 | 已作废 | 已删 | 作废 | 合法（冒烟卡机审后作废，非合入）|

**全量一致性审计**：main 上 160 张卡机审区含「通过」但 ledger 无 `machine_audit_pass` 记录（**pre-era 兼容：ledger 能力 08-16 前落账的旧卡，降级卡文机审区**，符合 `approve-merge.sh:476-486` 降级逻辑）。真实风险点 = **xy055 一类**（ledger 有记录但卡机审区缺失，本应被合入门禁拒绝却通过）。

**根因**：xy055 于 08-21 合入，当时 approve-merge 的机审证据检查仍允许"分支信封含通过"即放行，且 `close_card` 写验收区时可能覆盖/未保留机审区原文。08-22 后的硬化（ledger 强校验 + 卡文自写不算真值 + 机审后漂移硬拒绝）已封堵此路径。

**验证证据**：合入 commit `6188bd929`（08-21）`git show 6188bd929^1:<卡>` 机审区=占位；ledger `machine_audit_pass xy055` ts=08-20T18:51Z。

---

## 修复建议（待老板确认后实施）

1. **P0-1a**：`approve-merge.sh` 新增「环节② 独立复核清单」为强制步骤（git 真实性/diff 范围/测试重跑抽查/ledger↔信封一致性）。
2. **P0-1b**：新增第二道检测——验收时对分支独立重跑测试命令抽验。
3. **P0-2a**：`~/.dsh/.agent-presets/` 只读保护或 sha256 外部校验（需确认是否影响 DSH 预设更新）。
4. **P0-2b**：xy055 类历史断裂卡（ledger 有记录但卡机审区缺失）——补机审区或标注「历史断裂」归档，避免误导后续审计。
5. **P1 批次**：密钥统一（audit-merge-agent.sh:36）、引擎版本漂移监控、快照排查、孤儿卡扫描、数值一致性校验——待 P0 确认后按 P1 清单逐项加固。
