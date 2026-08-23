# 指令A 实施日志 · 基础工作搭建（2026-08-23）

> 执行：管理席 ox-alpha。验收归属：2017 管理席 Claude Code（cga 进入）逐项验收 + 老板最终确认。
> 本文是持久证据索引；聊天汇报为即时通报。

## 状态总览

| 步骤 | 内容 | 状态 |
|---|---|---|
| 1a/1b | registry 启用 tst + 测试仓 | ✅ 完成（commit `26c297170`） |
| 1c | 样例卡上板 | ✅ tst002 可见（`/cards/search`）；**状态流转阻塞**＝服务重启待老板授权 |
| 2a | --patch 挂载实验 | ✅ 三轮，最终路线验证通过 |
| 2b | 席位预设心智 ×3 | ✅ `~/.dsh/.agent-presets/{dsh-executor,dsh-auditor,dsh-prober}/` |
| 2c | wrapper 入编改造 ×4 | ✅（commit `c32a57702`） |
| 2d | tst 卡真实派发心智回归 | ⏳ 等引擎重启后自动进行 |
| 3 | 巡检常活固化 ×2 | ✅ 预设建成 + 只读实跑验证；tst 卡化排程待重启后 |

## 第 1 步证据

- registry tst 条目：`status: active` / `taskable: true` / `paths.mac2017: /Users/fan/program/apps/ccc-tst` / isolation(worktree_root=`apps/.ccc-wt/tst`, max_concurrent=1)；`load_projects()` 解析 OK；`check_path_locations` PASS；check-entry-docs 绿。档案 `docs/projects/tst/README.md` 七节模板。
- 测试仓：`git -C ~/program/apps/ccc-tst log --oneline -1` → `1ceae1b init`；origin=本地裸仓 `~/program/apps/ccc-tst.git`（满足 `_worktree_branch_seed` 的 origin/main 依赖）。
- 方案：`docs/projects/tst/plans/001-pipeline-smoke.md`，validate-plans 全绿。
- 卡：`docs/dispatch/tst/tst002-pipeline-smoke.md`（commit `b847dd4b7` 自动出卡+push）。编号说明：`plan_reserved_ids` 从方案「关联卡」提取保留号——tst-plan-001 保留 tst001，首卡自动 002。
- 看板可见性：`curl 'http://192.168.3.116:7788/cards/search?q=tst002'` → 待分派。
- **已知异常**：`:7788` 主列表 `/cards` 尚无 tst 卡——web 服务进程（08-23 02:12 启动）早于 registry push，内存 PREFIXES 未含 tst；重启后自愈。

## 第 2 步证据

### a) 挂载实验（隔离 DSH_HOME=/tmp/dsh-lab，未碰生产配置）
1. 对照组（无 patch）：问「只回复OK」→ 输出 `OK`（headless 默认 persona）。
2. canary 组（`--patch canary.yml`，id=system-prompt）：首行 `CANARY-MOUNT-OK` → **覆盖式替换生效**。
3. 「预设文件直挂」证伪：`--patch agent.cordis.yml` 报 `patch: entry "persona" not found`——`--patch` 的 id 是组合树槽位，不是插件行列表。（注：此前一次 ccc-card-maker「直挂成功」判断有误，回答实际来自工作区 CLAUDE.md 上下文，已纠正。）
4. 最终路线：wrapper 从预设提取 `id=persona` 行的 text，生成 `{id: system-prompt, config:{persona}}` overlay 再 `--patch`。验证：dump-config 含【DSH-EXECUTOR】×1；live 冒烟自述「CCC 产线开发执行体（dsh-executor）…首行标记【DSH-EXECUTOR】」。

### b) 预设心智（仓外运行面 `~/.dsh/.agent-presets/`）
- `dsh-executor`：读卡→白名单实现→自测→commit+push→回写已回写+维护区四问→停手；输出契约首行【DSH-EXECUTOR】；伪造完成=非0退出。
- `dsh-auditor`：v4 对抗式审查+severity 三级+轻修复/打回分流+维护区核对；结论行正则敏感格式硬约束（冒号后直连 通过/不通过）；通过退 0。
- `dsh-prober`：只读取证红线绝对化；证据优先；【未核实】纪律。

### c) wrapper 改造（commit `c32a57702`）
- `scripts/dsh-executor.sh` / `scripts/dsh-auditor.sh`：预设派生 overlay + prompt 瘦身（仅卡指针/work id/角色/授权声明/工作目录）；保留 PATH 兜底（P0-2）、DSH_PERMISSION_MODE=danger-full-access（P0-3）、退出码传播（R1）。
- `scripts/dsh-card-maker.sh`：移除无效的 settings.yaml agent-presets.default 切换（老板确认成立的 bug），改同款预设挂载。
- `~/.dsh/run-executor.sh`：挂 dsh-prober 预设（改前备份 `.bak-20260823`）；env 仍从 run_audit.sh 提取。

## 第 3 步证据

- 存量 8 预设盘点：6 个 standard 系（verifier/health-patrol 每日/compliance-auditor 每周/arch-scanner/feature-checker）+ explorer（DSH 开发探索）+ quanthive-worker（独立轨道）+ card-maker。
- 新固化：
  - `ccc-pipeline-patrol`：六项巡检（看板五态/引擎心跳/worktree 卫生/孤儿分支/台账一致性/DSH 前置）。实跑（第1/2/6项）：PASS×2+WARN×1——**自主发现 tst002 盘上有卡/主列表不可见异常**并给出根因假设。
  - `ccc-doc-drift-patrol`：现行权威面旧栈扫描+136 处基线对比。实跑（三入口）：B 类 19 行，指出 STARTUP-BRIEF:131「勿写 OpenCode 已禁用」护栏反转的元问题。
- tst 卡化排程：重启后可出 tst 巡检卡让 patrol 进 Engine 正常调度轨道（待定，不阻塞验收）。

## 重启 + 回归 Runbook（等老板授权后执行）

```bash
# 1) 热重启三大服务（等价 kickstart/deploy 的服务动作）
launchctl kickstart -k gui/$(id -u)/com.ccc.engine
launchctl kickstart -k gui/$(id -u)/com.ccc.web-server
launchctl kickstart -k gui/$(id -u)/com.ccc.board-scheduler

# 2) 回归判定（自动进行，无需人工干预派发）
# - 引擎捡起 tst002（新代码 role 推导=开发执行体 → AUTO）
#   grep -a "work=tst002" ~/.ccc/logs/engine.stderr.log | tail   # 应见「拉起执行体…dsh-executor.sh」
# - executor 日志出现【DSH-EXECUTOR】心智标记且 rc=0
#   tail /Users/fan/.ccc/logs/tst002.log
# - 机审自动拉起 dsh-auditor.sh，机审区写入「severity：…」「机审：通过」，台账 machine_audit_pass tst002
#   CCC_AUDIT_LEDGER 默认 data/audit/ledger.jsonl（生产台账）
# - 看板主列表出现 tst 卡（web 服务加载新 PREFIXES）：curl -s :7788/cards | grep -o tst002
# - ready_for_merge 可见 tst002 → 停：合入留老板/cga
```

## 边界与遗留

- P1-b（参数模板缺 `{biz_worktree}`）未修：tst 样例卡白名单自指不受影响；业务仓卡的隔离传递仍是挂账项。
- 生产台账 vs 隔离台账：本次回归用生产默认台账（真实看板流程的一部分）。
- 全部产物提交记录：`26c297170`（第1步）→ `c32a57702`（第2步）；仓外产物（预设/run-executor）以本文件路径+内容为准。
