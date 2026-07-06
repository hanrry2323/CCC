你是 CCC Verifier(独立 `claude -p` session,**新 UUID**,与 Executor 隔离)。

# 任务: 验收 readme-zcode-update

## 红线 6 验证(必跑)

首先验证你的 session UUID 与 Executor 不同:

```bash
EXEC_SID=$(cat /Users/apple/program/CCC/.ccc/plans/readme-zcode-update-executor-session-id.txt)
MY_SID=$(cat /Users/apple/program/CCC/.ccc/plans/readme-zcode-update-verifier-session-id.txt)
test "$EXEC_SID" != "$MY_SID" && echo "ISOLATION_OK" || echo "ISOLATION_FAIL"
```

## 启动顺序(必读)

1. 读 `/Users/apple/program/CCC/.ccc/plans/readme-zcode-update.plan.md`
2. 读 `/Users/apple/program/CCC/.ccc/reports/readme-zcode-update.report.md`
3. 读 `/Users/apple/program/CCC/README.md`

## 验收(≥3 adversarial probes)

### Probe 1: README.md 真含 ZCode Adapter 段
```bash
grep -c "ZCode Adapter (v1.2.1" /Users/apple/program/CCC/README.md
```
期望: ≥1

### Probe 2: README 引用了真 scripts
```bash
grep -E "scripts/ccc-zcode-bridge.sh|scripts/ccc-znode-register.py|scripts/ccc-zcode-orchestrate.sh" /Users/apple/program/CCC/README.md | wc -l
```
期望: ≥3

### Probe 3: Executor 报告含 VERDICT 引用段
```bash
grep -E "^> VERDICT:" /Users/apple/program/CCC/.ccc/reports/readme-zcode-update.report.md
```
期望: 1 行引用 `.ccc/verdicts/readme-zcode-update.verdict.md`

### Probe 4 (可选): 4 文件契约未坏
```bash
bash /Users/apple/program/CCC/scripts/ccc-status.sh 2>&1 | tail -10
```
期望: profile=ok, state=ok, plans 数量 +1 (从 5 → 6)

## 写 verdict.md

写到 `/Users/apple/program/CCC/.ccc/verdicts/readme-zcode-update.verdict.md`,格式:

```markdown
# Verdict — readme-zcode-update

> Plan: .ccc/plans/readme-zcode-update.plan.md
> Report: .ccc/reports/readme-zcode-update.report.md
> Verifier session: <YOUR_UUID>
> Executor session: <EXEC_UUID> (must differ)

## VERDICT: PASS|CONDITIONAL_PASS|FAIL

## Probe 1 — README ZCode Adapter 段
- 结果: ...
- 证据: (上面命令的真实 stdout)

## Probe 2 — README 引用真 scripts
- ...

## Probe 3 — Executor 报告含 VERDICT 引用
- ...

## 总结
- probe 通过数: X/3
- 最终: VERDICT
```

## 完成定义

1. verdict.md 真文件存在(红线 11)
2. 含 ISOLATION_OK 验证证据
3. ≥3 probes
4. 末行 `## VERDICT: PASS|CONDITIONAL_PASS|FAIL`

退出前 echo:
```
VERIFIER_RESULT: success
VERDICT_FILE: /Users/apple/program/CCC/.ccc/verdicts/readme-zcode-update.verdict.md
PROBES_PASSED: <N>/<total>
```