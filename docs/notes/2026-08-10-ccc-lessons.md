# ccc 066 教训沉淀 (2026-08-10 · 机审钉 commit 与分支命名)

> 来源：ccc066（V6 机审钉 commit + V7 resolve_card 唯一性）。
> 触发：机审后分支漂移无兜底；resolve_card 多命中时 head -1 猜。

## 教训

### 1. 验收证据必须钉不可变对象（commit sha），不能验文本

- **现象**：机审信封「机审：通过」写在卡文件文本里，机审通过后分支被 force-push 改写，信封仍显示通过，漂移无兜底。
- **根因**：文本可被重写；验文本 = 验可篡改对象。
- **解决方案**：机审启动前记录分支远端 tip 做被审 sha，通过后信封改写为「机审：通过（被审 <sha12>）」（幂等、老信封兼容）；approve-merge 合入前解析并校验 `被审 sha..origin/<branch>` 间除 docs/dispatch/** 外无改动——机审后漂移即拒合须重审。落地：`scripts/approve-merge.sh` + `server/engine/main.py`。

### 2. resolve_card 多命中禁止 head -1 猜

- **现象**：卡文件重名/前缀模糊时 `find | head -1` 可能选中错误卡。
- **解决方案**：抽共享库 `scripts/lib/card-resolve.sh`，多命中报错返回非零，单命中才输出；配套 `scripts/tests/test-card-resolve.sh`。

### 3. 执行体分支名必须与卡文件名一致（worktree 分支 = codex/<卡文件名>）

- **现象**：ccc065 卡文件名 ccc065-engine-tip，开发时建分支 codex/ccc065-product-gate，engine 机审 worktree 用 codex/ccc065-engine-tip 找不到代码 → 零工件打回。
- **根因**：engine worktree 分支名 = `codex/<卡文件名>`，开发分支名不一致导致代码在错误分支。
- **解决方案**：出卡后 checkout 分支名必须等于 `codex/<卡文件名>`；开发中途改名需同步 force-push 到正确分支。
