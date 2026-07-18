# Plan: [retest-feat-regress-notify-v02315 — 回测失败桌面通知 retest v0.23.15]

> 撰写：ccc-product（retest 模式） | 执行：ccc-dev（auto）
> 来源：feat-regress-notify 曾在 v0.18 in_progress 滞留 6.4h（opencode PATH not found 自动隔离），v0.18 verdict=PASS。重投验证 v0.23.15 流程不再有 PATH 问题。

---

## 当前代码状态

- **当前版本**：v0.23.15（commit `1c35417`）
- **关键资产**：
  - `scripts/ccc-notify.sh` — macOS 桌面通知
  - `scripts/ccc-board.py:regress_role()` — 回测角色，建 bug 后调 `subprocess.run(["bash", ".../ccc-notify.sh", "L2", title, desc])`
  - `scripts/ccc-engine.sh` — Engine 入口，**已 fix PATH**：`export PATH="/Users/apple/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"`
- **历史失败原因**：launchd 环境无 PATH → opencode 找不到 → 滞留 → 隔离
- **当前状态**：PATH 已修（commit `0592c3f` v0.20.1），应已彻底

---

## 范围

- **目标**：验证 v0.23.15 下 regress_role → ccc-notify.sh 链路完整 + PATH 正常
- **只改文件**：`scripts/ccc-board.py`（regress_role 函数附近，仅做检查不改逻辑）
- **不改文件**：`scripts/ccc-notify.sh`、`scripts/ccc-engine.sh`（已修）
- **执行方式**：`auto`
- **Phase 数**：1

---

## 改动 1：验证 regress_role + ccc-notify.sh 调用链

### 做什么
手动验证 regress_role 调 ccc-notify.sh 时 bash PATH 正常、osascript 路径正确、桌面通知能弹出。

### 怎么做
1. 检查 `scripts/ccc-notify.sh` 存在且可执行
2. 在 shell 中执行 `bash scripts/ccc-notify.sh L2 "retest 验证" "v0.23.15 流程复测"` → 应弹桌面通知
3. 验证 regress_role 内 subprocess.run 调用参数：
   - `ccc-board.py` 第 1862 行附近：`subprocess.run(["bash", str(CCC_HOME / "scripts" / "ccc-notify.sh"), "L2", ...])`
4. 检查 `~/.ccc/logs/` 有无 `role-regress-*.log` 最近成功记录
5. 检查 macOS 系统通知设置（系统设置 > 通知 > 脚本编辑器/Script Editor）允许

### 验收清单
- `bash -n scripts/ccc-notify.sh` 0 错误
- 手动触发通知成功（osascript 无报错）
- regress_role 代码内 subprocess.run 路径白名单正确（无 shell=True 注入风险）
- 单 phase 单 commit

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | retest 验证 + 报告 | `chore(retest): feat-regress-notify v0.23.15 复测 (retest-feat-regress-notify-v02315)` |

---

## 全局验收清单

- [ ] bash 通知手动触发成功
- [ ] 代码静态检查无问题
- [ ] regress_role subprocess 路径合法
- [ ] 单 phase 单 commit