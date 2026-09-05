# P0 修复实施设计 · P0-1b 测试真实性 / P0-1d 抽验 / P0-2a 预设保护（送审）

> 记录：S116-01 · 2017 Claude Code（环节② 审核合入席）· 2026-08-23
> 依据：老板执行指令（P0 修复实施 + 补充设计要求）
> 状态：**P0-1a 范围核验 / P0-1c git 真实性 / P0-2b xy055 事故记录 已实现**；本档送审 P0-1b / P0-1d / P0-2a 三项，**老板确认后接线实施**

---

## 〇、已实现（独立可复现证据）

| 项 | 落点 | 证据 |
|----|------|------|
| P0-1a 范围核验硬门禁 | `scripts/scope-check.sh`（新建）+ `scripts/approve-merge.sh` 接线 | 越界分支 `server/web/server_tmp_marker.txt` 被拒 EXIT=1；范围内分支通过 EXIT=0 |
| P0-1c git 提交真实性 | `scripts/git-truth-check.sh`（新建）+ `approve-merge.sh` 接线 | 伪造 pin（非祖先）被拒；夹带他人 author 业务提交被拒；正常 pin 通过 |
| P0-2b xy055 事故记录 | `docs/notes/2026-08-23-xy055-incident.md`（新建） | ledger 有记录但卡机审区占位，08-22 硬化前断裂，已堵，不追溯 |

---

## 一、P0-1b 测试真实性机械截获（待确认）

### 1.1 机制（与老板要求对齐）

wrapper（dsh-executor.sh / dsh-auditor.sh）在 **DSH 之外** 独立解析卡 `## 门禁` 节的 `测试` 命令 → 独立运行该命令 → 截获**真实 stdout/stderr + 退出码** 写入独立证据日志。approve-merge.sh 合入时**只检查这份 wrapper 截获日志**里的真实退出码与测试框架输出，**不再信卡回写区 DSH 自述的「测试通过」文本**。

### 1.2 哪个脚本改

| 脚本 | 改动 |
|------|------|
| `scripts/test-evidence.sh` | **已建**。解析卡 `## 门禁` 节测试命令 → 在 workdir 运行 → 截获 stdout/退出码写证据日志。每次运行**覆盖**（最新一次为权威），含时间戳+card+cmd+workdir 头。 |
| `scripts/dsh-auditor.sh` | 机审前置加**机械测试真跑门禁**：先跑 test-evidence.sh，测试真实失败 → 硬打回，**不让 DSH 跑机审**（堵「谎报测试通过仍机审」路径）。 |
| `scripts/dsh-executor.sh` | 执行体完成后，wrapper 独立跑 test-evidence.sh 截获测试真实结果（不依赖 DSH 自述）。 |
| `scripts/approve-merge.sh` | 新增门禁：**evidence log 必须存在且 exit_code=0** + 测试框架输出含通过标记（pytest 的 `passed`/`==== 1 passed`；npm/cargo 对应标记）。缺日志/失败 → 拒绝合入。 |

### 1.3 日志落哪里

**建议：`$EXECUTOR_LOG_DIR/<card_id>.test-evidence.log`**（即 `/Users/fan/.ccc/logs/exec/<card_id>.test-evidence.log`）。

理由：
- `work.id == card_id` 已确认（store.py），按卡号定位与 sidecar 流程态一致；
- `_executor_log_dir()` 已被 approve-merge 复用（clear_card_state 处），路径解析逻辑现成；
- 目录为运行时数据，`data/` 同列不进版本库，无 DOC-PROTOCOL 冲突；
- 每次运行覆盖 → 最新一次测试结果为权威，天然防「重试后旧通过日志残留」。

备选：`data/audit/test-evidence/<card_id>.log`（证据与 ledger 同目录，语义更聚合）。**倾向前者**（复用现有基础设施），老板可定夺。

### 1.4 判定口径（approve-merge 门禁）

```
evidence log 存在
  AND 末行 == exit_code=0
  AND log 含测试框架通过标记（pytest: /(passed|OK)/ ; npm test: /passed/ ; cargo: /test result: ok/）
  → 通过
否则 → 拒绝（提示重新机审，--close-only 不放行）
```

### 1.5 验证（老板要求的最关键验证点）

构造「DSH 谎报测试通过但实际测试失败」模拟场景：
1. 卡 `## 门禁` 测试命令 = 一个真实失败的 pytest（断言必败）；
2. 卡回写区 DSH 写「测试：通过」；
3. wrapper 跑 test-evidence.sh → 截获真实 exit_code=1 → evidence log 记失败；
4. approve-merge.sh 读 evidence log → 拒绝合入；
5. 对照组：真实通过场景 → 合入放行。
**此验证在接线后立即执行（任务 #34），不跳过。**

---

## 二、P0-1d 环节②抽验机制（待确认）

> 老板要求：明确抽样比例、频率；**抽验必须由环节②（本席）执行，不能让 DSH 抽验自己**——写进方案显式声明。

### 2.1 抽样设计（建议初值，老板可调）

| 维度 | 建议值 | 依据 |
|------|--------|------|
| 抽样比例 | 每批合入 ≥1 张 + 每 5 张抽 1 张（20%）随机 | 合入频率低（当前 ready 队列常空），比例设 20% 保证有覆盖又不阻塞 |
| 频率 | **每次合入动作时**执行（非定时） | 抽验的是「待合入证据」，必须在合入前完成才有拦截价值 |
| 执行方 | **环节②（Claude Code = 本席）**，DSH 不参与抽验决策 | 与审核红线一致：绝不信 DSH 执行过程 |
| 抽样源 | 本次 `approve-merge.sh --ready` 批次 ID 列表 | 随机种子取批次内容 hash，避免「抽不到」被操纵 |

### 2.2 抽验动作（对抽中卡）

1. **独立重跑测试**：用与 test-evidence.sh 同一套逻辑（不信任 DSH 留存输出），对分支 worktree 重跑卡声明测试命令，比对退出码/通过标记与 evidence log。
2. **范围复核**：`scope-check.sh` 再跑一遍（双确认）。
3. **git 真实性复核**：`git-truth-check.sh` 再跑一遍。
4. **ledger↔信封一致性**：ledger 有 machine_audit_pass + 分支信封机审区「通过」+ 被审 pin 在分支上。
5. 抽验结论（通过/打回）→ 打回须带「问题 → 文件:行号 + 唯一最佳动作」，写进验收区/ledger。

### 2.3 落地方式

新增 `scripts/spot-check.sh <card_id>`：封装 2.2 四步 + 出结论；approve-merge.sh 在批次循环里按 2.1 抽样调用，抽中卡先 spot-check 再过合入门禁。**抽验是环节②的人审动作**（本席执行脚本并签核），脚本只是机械助手。

---

## 三、P0-2a 预设只读保护 + 变更治理（待确认）

### 3.1 现状事实（已验证）

| 检查 | 结果 |
|------|------|
| `~/.dsh/.agent-presets/` | `drwxr-xr-x fan:staff`，fan 可写 |
| `dsh-auditor/agent.cordis.yml` 等 | `-rw------- fan:staff`，fan 可写 |
| DSH headless 运行用户 | **fan**（`dsh --profile headless` 进程属主 fan） |
| 能否 sudo | `sudo -n true` → exit=0（**可免密 sudo**） |
| 现有 hash 监控 | watchdog-ccc.sh **无** preset hash 检查 |

### 3.2 权限模型评估（能否技术隔离）

**纯 `chmod 444` 不能隔离**：文件属主是 fan，DSH headless 以 fan 运行，同用户进程可 `chmod` 改回权限自写预设——只读位对同属主是**摆设**（P0 报告 §2.1 已指出）。

**技术隔离可行方案**：`chown root` 预设文件 + 目录 → 属主 root，fan 进程无法 chmod/写；DSH 以 fan 读 root 属主文件：**需要保留其他用户可读位（444）**，否则 DSH 读不了预设（运行中断）。sudo 可用 → 一次性 chown 可行。

**代价**：预设更新不再能由 fan 直接写，需 root/sudo —— 恰好强制「预设变更走人工直改」流程（见 3.3 红线），与治理目标一致。

### 3.3 治理方案（组合拳）

| 层 | 措施 | 防什么 |
|----|------|--------|
| **权限隔离** | `sudo chown -R root:staff ~/.dsh/.agent-presets/` + 保留 `r` 位（文件 444、目录 555） | DSH（fan）直接改预设 |
| **变更监控** | watchdog-ccc.sh 新增 **preset hash 基线校验**：首次登记 sha256，之后每次心跳比对，变化即写告警（复用 observer/ledger 告警通道） | DSH 间接改写 / 绕过权限的变更 / 人工直改后忘机审 |
| **红线治理** | 预设变更纳入平台自研红线：**只走「2017 本机人工直改 + 异席机审」**；DSH 运行路径无写预设授权 | 治理闭环（改动有审批、有痕迹） |

> 3.2/3.3 结论：**做得到技术隔离**（chown root + 保留可读位），配合变更监控双保险。建议三管齐下。

---

## 四、待老板确认清单

1. **P0-1b**：改 `dsh-executor.sh` / `dsh-auditor.sh` / `approve-merge.sh` 三个脚本；证据日志落 `$EXECUTOR_LOG_DIR/<card_id>.test-evidence.log`（或备选 `data/audit/test-evidence/`）——确认后接线实施。
2. **P0-1d**：抽样 20%（每批≥1 张）、每次合入时执行、**环节②执行**、`scripts/spot-check.sh` 落地——确认后实施。
3. **P0-2a**：`sudo chown -R root:staff ~/.dsh/.agent-presets/`（保留 444/555 可读）+ watchdog hash 告警 + 预设变更红线——确认后实施（涉及改 DSH 运行权限，须老板点头）。

## 五、实施顺序（确认后）

1. P0-1b 接线三个脚本 → 任务 #34 谎报模拟验证（最关键，不跳过）
2. P0-1d spot-check.sh + approve-merge 抽样接线
3. P0-2a chown + watchdog hash + 治理文档
4. 全量回归：`pytest server/tests/` + `approve-merge.sh` 门禁不劣化
5. 推进 P1 清单（#23-#26）
