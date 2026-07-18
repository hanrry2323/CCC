# Plan: adv-ccc-f10

来源: adversarial-2026-07-09.json

## 目标
[CWE-22/94] _parse_plan_scope 读取 ROOT/.ccc/plans/<task>.plan.md, 提取 - file 行; plan.md 内容由 LLM 写 (ccc-board.py:222 走 claude -p); reviewer_role fallback py_files = _glob.glob(str(ROOT / f)) 若 f 含 '**' 可

## 文件
scripts/ccc-board.py:682

## 验收
- [ ] 修复完成
