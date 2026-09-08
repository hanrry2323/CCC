# 2026-09-04 重构批E执行报告：验收席换 claude wrapper（后段=CC CLI 对齐落地）

> 调度外脑下发，老板已授权。执行窗口：2026-09-05 03:35–04:30。产线修复窗口执行体。
> 指令源：`/Users/fan/.ccc/instructions/2026-09-04-align-batchE.md`。

## 目标达成

后段执行（已回写后：审核/验收/合入/部署）= Claude Code CLI。phase2 主链不再调
`scripts/dsh-auditor.sh`（DSH headless），改调 `scripts/cc-auditor.sh`（claude wrapper），
且 phase2 从注册表读验收席命令（插座单源，换绑定只改 executors.json 一行）。

## 灰度顺序执行记录（六步）

### 第一步：新建 wrapper `scripts/cc-auditor.sh` ✅ `1ce7d6e9a`

- argv 签名与 dsh-auditor.sh 完全一致：`{card_path} {work_id} {worktree} {role} {biz_worktree}`
  （注册表参数模板不变，换绑定=改一行命令）。
- 环境：`ANTHROPIC_BASE_URL=http://127.0.0.1:3456`（M1 中转 local-litellm）、
  `ANTHROPIC_MODEL=Code`、`ANTHROPIC_API_KEY=dummy-placeholder`（3456 不校验 key，2026-09-03 实证）、
  `EXECUTOR_LOG_DIR` 继承。launchd PATH 兜底 npm-global + /usr/local/bin。
- 契约 v2：主仓卡只读（prompt 明令禁写卡/仓）；审计输入=卡全文+`$EXECUTOR_LOG_DIR/<work_id>-ccc-result.md`
  结果工件；输出=verdict 写 `$EXECUTOR_LOG_DIR/<work_id>-audit-verdict.md`，含整行
  「机审：通过」或「机审：不通过（原因）」+ 证据四段（范围核对/风险论证/severity/维护区核对），
  沿用 v4 对抗式审查心智，自称「后段验收席（Claude Code CLI）」。
- exit 语义：0=verdict 已产出；2=机械前置不通过（同时写「机审：不通过（…）」工件）；
  其他=基础设施失败（缺失结果工件 → 3）。
- 调用形态：`claude -p "<审计prompt>" --output-format text --max-turns 30 --permission-mode bypassPermissions
  --allowedTools "Read Write"`（限权 Read/Write，禁 Bash/Edit/git，防意外写仓）。
  审计时长上限沿用 phase2 传入 timeout（wrapper 内不设 timeout）。
- 机械前置保留 dsh-auditor 同源两关：docgate.verify_maintenance 维护区四问 + test-evidence.sh
  测试真实性截获；失败均写「机审：不通过」工件 + exit 2。

### 第二步：phase2 改从注册表读验收席命令 ✅ `6c60f4372`

- `server/engine/phase2.py` `_dsh_auditor_path`：优先级 `DSH_AUDITOR_BIN`（测试注入）
  → 注册表 `EXECUTOR_REGISTRY_PATH`「验收席」行「命令」→ 回退仓内 `dsh-auditor.sh`
  （读取失败 warning 不硬断）。
- `_run_dsh_auditor` 函数名保留，加注释「命令来源=注册表，历史名保留」；错误文案改「验收席 wrapper」。
- 定向测试新增三用例：
  - `test_dsh_auditor_reads_command_from_registry`：注册表换命令 → phase2 用新命令（tmp 注册表注入）；
  - `test_dsh_auditor_registry_read_failure_falls_back`：注册表读取失败 → 回退默认 + 不硬断；
  - 既有 `test_dsh_auditor_accepts_empty_worktree_contract` 保持通过。

### 第三步：注册表换绑定 ✅ `a939c4e35`

- `server/config/executors.json` 验收席「命令」→ `/Users/fan/program/CCC/scripts/cc-auditor.sh`；
  「当前绑定」改「后段 CC CLI（claude wrapper，主链 phase2）」；
  备注去「历史绑定 DSH」句，改「2026-09-04 起主链与兜底链统一 claude wrapper」。
- `executors.example.json` 同步：命令用占位绝对路径 `/ABS/PATH/TO/CCC/scripts/cc-auditor.sh` +
  备注注明绝对路径要求。

### 第四步：旧链收敛（删死逻辑）✅ `0bd2e3d59`

- 删 `server/engine/main.py` 交叉配对死逻辑（原 3986-3993：`executor_norm`/`acceptor` 固定工具）
  + 顺带删其支撑函数 `_audit_cli_entry` + `normalize_tool` 导入。
- 删 `MachineAuditPrompt` 死类（原 2222-2238，批B 已标 DEAD）+ 对应测试
  `test_audit_prompt_no_re_run_wording`。
- 机审直接 `registry.cli_entry_for_role("验收席")`（插座单源）。
- `--audit` 手动侧链（`_run_machine_audit_after_writeback`）改指向新 wrapper：结论以
  log_dir verdict 工件为准（新 `_audit_verdict_from_artifact` helper，cc-auditor 契约 v2），
  不再依赖 worktree 心智旧链；旧 worktree 分支卡路径保留兼容旧 wrapper。
- observer：确认无 opencode 探测残留（批D 已清，仅文字退役说明）。

### 第五步：测试同步 + 全量 ✅ `2e09898b2`

- `test_engine_dispatch.py` 验收席断言改新命令/新绑定文本。
- `test_skeleton.py` dsh 契约用例核对：开发/维护行仍指 `dsh-executor.sh`（前段不变），
  断言保持通过；验收席行不再匹配 dsh 过滤。
- 新增 `scripts/cc-auditor.sh` bash -n 语法检查入测试（`test_cc_auditor_script_bash_syntax`）。
- 全量 `pytest server/tests/` 绿（FAILED/ERROR 0 行）+ `.venv-hub/bin/ruff check server/` 净。

### 第六步：灰度验证（三步，顺序执行）✅

#### 6.1 wrapper 直测（独立 /tmp 目录）

```
EXECUTOR_LOG_DIR=/tmp/cc-gray-log bash scripts/cc-auditor.sh \
  docs/dispatch/tst/tst905-smoke-clean-full-probe.md \
  tst905-cc-gray /tmp/cc-gray-log 验收席 ""
```

- 独立目录 `/tmp/cc-gray-log`，不碰生产 EXECUTOR_LOG_DIR（事后核验：生产无 `cc-gray` 工件）。
- 结果：verdict 工件产出 `tst905-cc-gray-audit-verdict.md`，首行整行结论
  「机审：不通过（卡内证据自相矛盾：…）」+ 证据四段（范围核对/风险论证/severity/维护区核对），
  **exit 0**。
- verdict 内容不作为 tst905 卡机审依据（纯灰度；tst905 早已关闭，卡内机审区不变）。

verdict 工件样例（首 2 行 + 段标题）：

```
机审：不通过（卡内证据自相矛盾：探针 git 短 hash `d9ae1f26e` 与 `## 2. 自测输出` 内嵌 dump 的 `79f461dc9` 不一致，证据链不闭合；卡头「已关闭」不符验收标准要求的「已回写」；卡内无 `## 机审区` 与机审结论）

## 一、范围核对
```

#### 6.2 mock 驱动 phase2

```
.venv-hub/bin/python3 -m server.engine.phase2 --config server/config/config.env \
  --once --audit-driver mock:pass
→ {"scanned": 0, "closed": 0, "rejected": 0, "audit_failed": 0, "deploy_failed": 0, "error": 0}
```

- mock 下全链走通、配置加载正常、无异常日志。当前看板无「已回写」卡（安全窗），scanned=0 符合预期。
- 定向验证：`_dsh_auditor_path(cfg)` 从注册表读到
  `/Users/fan/program/CCC/scripts/cc-auditor.sh` 且文件存在（命令读取链真实生效）。

#### 6.3 重启引擎

```
launchctl kickstart -k gui/$(id -u)/com.ccc.engine
旧 pid 78771 → 新 pid 17765
```

- 重启后：scheduler 线程启动、`executors.json 热重载完成`（读到新注册表）、
  heartbeat 正常（scanned=0，无已回写卡安全窗）、无 ERROR/WARNING 异常日志、看板 `/health` ok。

## 红线遵守核对

| 红线 | 状态 |
|------|------|
| 灰度三步缺一不可 | ✅ 6.1/6.2/6.3 顺序执行全部完成 |
| wrapper 直测只用 /tmp 独立目录 | ✅ `EXECUTOR_LOG_DIR=/tmp/cc-gray-log`，生产 EXECUTOR_LOG_DIR 无新工件 |
| 前段 DSH 相关不动 | ✅ dsh-executor.sh / dsh_gateway / dsh-auditor.sh 均未改（dsh-auditor.sh 保留为回退默认路径） |
| 全量测试不过不得重启引擎 | ✅ pytest 全绿 + ruff 净后才 kickstart |
| 续跑纪律：每步一 commit 即 push | ✅ 六步各一 commit 均已 push |
| 绝不信执行过程自报 | ✅ 结论文件为独立核验产物（卡文件/commits/测试输出） |

## 回滚说明

**一行回滚**：把 `server/config/executors.json` 验收席「命令」改回
`/Users/fan/program/CCC/scripts/dsh-auditor.sh`，然后 `launchctl kickstart -k gui/$(id -u)/com.ccc.engine`
重启引擎即生效（注册表热重载 + 引擎重启）。
- phase2 侧已天然兼容：`_dsh_auditor_path` 从注册表读到哪个命令就用哪个；读不到回退仓内 dsh-auditor.sh。
- 若需彻底回退到旧链（不建议）：`git revert` 本次六 commit 或 `git checkout <批E前 sha>`。
- dsh-auditor.sh 本身未删除（保留为回退路径与历史参考），DSH 机审心智预设亦未动。

## 交付物清单

- 报告：`docs/notes/2026-09-04-align-batchE-report.md`（本文件）
- 生产变更 commit（均已 push）：
  - `1ce7d6e9a` feat(auditor): add cc-auditor.sh claude CLI wrapper
  - `6c60f4372` refactor(phase2): read auditor command from registry (socket single source)
  - `a939c4e35` refactor(config): switch 验收席 binding to cc-auditor.sh (claude wrapper)
  - `0bd2e3d59` refactor(audit): converge old chain, delete dead cross-pairing + MachineAuditPrompt
  - `2e09898b2` test(align): sync 验收席 assertions + cc-auditor.sh bash -n gate

## 结论

head = `2e09898b2e75e8feb54d219ab8146d30a8520eea` · engine pid = `17765`

后段验收席已切换为 Claude Code CLI wrapper（cc-auditor.sh），主链 phase2 与手动兜底链统一从
注册表读验收席命令（插座单源），灰度三步全部通过，引擎运行正常。