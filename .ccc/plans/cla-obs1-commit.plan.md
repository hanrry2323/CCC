# Plan: cla:OBS1 — 流程探针闭环:验证就绪 + 过程文件 + 强制 commit

> 撰写:ccc-product | 执行:ccc-dev(manual)

---

## 前置条件

- OBS1 核心测试文件已提交: `tests/test_obs1_smoke.py` (34c5c99)
- docs 文件已提交: `docs/OBS1.md` (34c5c99)
- 执行报告已提交: `reports/obs1-commit.report.md` (34c5c99)
- 当前 HEAD: 7fe1fc9 (B1.1正式闭环)

---

## Phase 1: 过程文件闭环

### 目标

完成 CCC 过程文件更新:
1. 刷新报告 Run Counter (6→7)
2. 更新 HEAD commit 引用
3. 刷新执行时间戳
4. 追加验证标记到 `docs/OBS1.md`
5. 覆写过时的 plan/phases 文件

### 执行步骤

```bash
# 1. 确认冒烟测试通过
pytest tests/test_obs1_smoke.py -q --tb=short

# 2. 更新报告文件
sed -i '' 's/Executed At: Fri Jul 17 06:05:21 CST 2026/Executed At: Fri Jul 17 06:49:19 CST 2026/' reports/obs1-commit.report.md
sed -i '' 's/Run Counter.*/Run Counter: 7/' reports/obs1-commit.report.md

# 3. 更新 docs 标记
echo "Verified at: 2026-07-17 06:49:19" >> docs/OBS1.md

# 4. 写入 phases 文件
cat > .ccc/phases/cla-obs1-commit.phases.json << 'EOF'
{"phase": 1, "subtasks": {"update_report": "Refresh OBS1-commit report with current timestamp and HEAD commit", "add_doc_marker": "Add verified at marker to docs/OBS1.md", "write_phases_json": "Write current phases.json for cla-obs1-commit", "write_plan_md": "Write current plan.md for cla-obs1-commit"}, "scope": ["docs/OBS1.md", "reports/obs1-commit.report.md", ".ccc/phases/cla-obs1-commit.phases.json", ".ccc/plans/cla-obs1-commit.plan.md"]}
EOF

# 5. 写入 plan 文件
cat > .ccc/plans/cla-obs1-commit.plan.md << 'EOFPLAN'
# Plan: cla:OBS1 — 流程探针闭环:验证就绪 + 过程文件 + 强制 commit

> 撰写:ccc-product | 执行:ccc-dev(manual)

---

## Phase 1: 过程文件闭环

### 目标

完成 CCC 过程文件更新:
1. 刷新报告 Run Counter (6→7)
2. 更新 HEAD commit 引用
3. 刷新执行时间戳
4. 追加验证标记到 docs/OBS1.md
5. 覆写过时的 plan/phases 文件

### 执行步骤

见上方 execute_section

### 验收条件

- pytest smoke test passed (1 passed)
- Run Counter = 7
- HEAD commit = 7fe1fc9
- docs/OBS1.md contains "Verified at: 2026-07-17 06:49:19"
EOFPLAN

# 6. Stage and commit
git add docs/OBS1.md reports/obs1-commit.report.md .ccc/phases/cla-obs1-commit.phases.json .ccc/plans/cla-obs1-commit.plan.md
git diff --cached --stat
git commit -m "test(probe): OBS1 流程压力探针 — 过程文件闭环 + 报告刷新 (phase 1/1, cla-obs1-commit)"
```

### 白名单约束

- ✓ docs/OBS1.md
- ✓ reports/obs1-commit.report.md
- ✓ .ccc/phases/cla-obs1-commit.phases.json
- ✓ .ccc/plans/cla-obs1-commit.plan.md

---

## 后续步骤

- OBS2+ 扩展流程压力探针覆盖 verdict 文件强制写入
- OBS 自检集成：将 pytest tests/test_obs1_smoke.py 纳入 ccc-self-check.sh
- OBS 自动化：纳入 Engine enabled 模式的启动前自检

