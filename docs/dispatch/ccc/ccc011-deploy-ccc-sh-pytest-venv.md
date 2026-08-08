# 任务卡 ccc011 · deploy-ccc.sh pytest 路径修复（venv 兼容）（Claude Code 执行）

> 关联：升级批次 4 交付脚本 · 执行体：Claude Code · 验收：Claude Code · 状态：待分派 · 派发：manual · 项目：ccc · 日期：2026-08-08

## 目标

deploy-ccc.sh 的 pytest 门禁改用 ${PYTHON_BIN} -m pytest（兼容 venv 环境），2017 无 PATH 前置也可直接跑。

## 红线（先看）

1. 1. 只改 scripts/deploy-ccc.sh 第 55 行 pytest 调用；不动其他任何文件/服务。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

白名单：`scripts/deploy-ccc.sh` 第 55 行 `pytest --ignore=...` → `"${PYTHON_BIN}" -m pytest --ignore=...`。

权威路径：scripts/deploy-ccc.sh（批次 4 交付，M1 与 2017 同源）。禁止新建 worktree。

## 步骤

1. 修改 scripts/deploy-ccc.sh 第 55 行：pytest 裸命令 → `"${PYTHON_BIN}" -m pytest --ignore=server/tests/test_t53_console_roadmap.py -q`（PYTHON_BIN 变量文件内已定义 :16）。
2. `bash -n scripts/deploy-ccc.sh` 语法通过；本地跑一次全流程验证门禁段可执行。
3. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `bash -n scripts/deploy-ccc.sh` 通过。
2. 在 PATH 不含 venv 的 shell 下（`env -i PATH=/usr/bin:/bin bash scripts/deploy-ccc.sh` 前两阶段）pytest 门禁不再报 command not found（可在 M1 用临时 git 仓/或 2017 直接跑验证）。
3. 探针=git 对齐：改动仅限该文件，diff 可审。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：Claude Code · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
