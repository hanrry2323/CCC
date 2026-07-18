# Plan: manual-test-001 — 手动测试：能否自动开发

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 范围

- **目标**：验证用户将 backlog task 手动移到 planned 列后，dev 角色能否自动拾取并执行
- **只改文件**：`无`（纯测试，不改代码）
- **不改文件**：全部
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1：手动挪卡 → 观察 dev 响应

### 做什么

测试 CCC 看板的核心流转能力：用户手动把 `manual-test-001` 从 backlog 挪到 planned 列，dev 角色（每 10 分钟巡检一次）应能自动检测到 planned 有任务，启动执行并生成 report。

如果 dev 自动执行完成，证明 7 角色定时系统在「从 planned 拾取任务」环节工作正常。
如果 dev 没有拾取或执行失败，说明看板流转/launchd/dev 角色入口存在断裂点，需要排查。

### 怎么做

1. 用户手动执行 `ccc-board.py` 将 `manual-test-001` 从 backlog → planned（可借助 `--promote` 或直接挪文件）
2. 等待 dev 角色巡检周期内自动拾取
3. 观察 `.ccc/board/in_progress/` 是否会生成对应文件
4. 观察 `.ccc/board/testing/` 及后续列是否有任务流转
5. 15 分钟内若无任何动静，视为 dev 响应失败

### 验收

- [ ] 手动挪到 planned 后 dev 拾取并进入 in_progress（不超 15 分钟）
- [ ] 看板卡最终到达 released 或留下 report 证明 dev 尝试过（参考：`ls -la .ccc/board/in_progress/` 和 `ls -la .ccc/board/released/`）
- [ ] 测试完成后将结论写回本次测试描述

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 纯测试，无代码改动 | `test(manual): 验证手动挪 planned 后 dev 自动拾取 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误 — 不涉及
- [ ] 全部测试通过 — 不涉及
- [ ] diff 范围仅限"只改文件"列表 — 不涉及
- [ ] 每个 phase 对应一个 commit — 可选
- [ ] phases.json 与 plan phase 数一致 —  1 phase
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

- 若测试通过：说明 7 角色看板流转就绪，可以开始正式 backlog 任务
- 若测试失败：需排查 dev 角色的 launchd plist 是否正常、dev.sh 入口是否有读取 planned 列的逻辑、ccc-board.py 的 `--promote` 是否可用