# CCC 战略地图 (v0.16 起)

> **必读**：所有 cloud agent 启动时**第一件事**读本文件。
> 这是 CCC 的"全景路线图"——CCC Engine + 7 角色 + 看板。
>
> **v0.20.1 架构变更**：取消 7 角色 launchd 定时轮询，改为单一 CCC Engine 常驻进程串行执行。

---

## 0. CCC 是什么

**CCC = Connect–Claude Code** = 单节点的 SKILL 资产型多角色定时开发框架。

**核心能力**：
- 7 角色（product/dev/reviewer/tester/ops/kb/regress）按频率定时启动
- 任务在 6 列看板上流转（backlog → planned → in_progress → testing → verified → released）
- opencode CLI（loop/flash）作执行器
- post-exec 钩子自动 commit + push 远端
- launchd 装 7 plist 周期跑

**不做**（红线）：
- 跨设备集群调度
- agent 自主启用 CCC（必须用户显式触发）
- 自动合并飞轮候选到 red-lines（必须人工 review）

---

## 1. 范式演进史（v0.5 → v0.16）

| 版本 | 范式 | 关键产出 |
|------|------|----------|
| v0.5-0.7 | 4 文件契约 + 3 角色流水线 | 13 红线、Plan→Exec→Verify |
| v0.8 | 切到 opencode CLI | 3 红线 X1/X2/X3（进程管理）|
| v0.9 | model provider 修复 | loop/flash 中转站 |
| v0.10 | 飞轮 + 队列简化 | 失败模式扫描 |
| v0.11 | 开箱即用调度 | 3 钩子模板 + install-ccc-scheduler |
| v0.12 | bug fix sweep | 3 类 bug 修复模式 |
| v0.13 | 跨项目支持 | qx-observer 接入 |
| v0.14 | 真正落地 | 35 commit push + scheduler 装 |
| v0.15 | 真自动化开发 | ccc-auto-dev.sh + post-exec 自动 commit+push |
| **v0.16** | **7 角色定时开发系统** | **任务看板 + 7 launchd plist** |
| v0.17 | 战略地图（本文件）| 所有文档对齐 7 角色 |

---

## 2. 7 角色系统（v0.16 起核心 / v0.20.1 引擎化）

> **v0.20.1 变更**：取消 7 角色 launchd 定时轮询，改为 CCC Engine 常驻进程串行驱动。
> 以下"频率"列是历史角色轮询频率（v0.20.0 及之前），Engine 模式下无定时，有 task 即执行。

### 2.1 角色矩阵

| 角色 | 历史频率(v0.20.0) | Engine 调度 | 扫哪列 | 处理后挪到 | 入口 |
|------|-------------------|-------------|--------|------------|------|
| **product** | 4h | 手动 `--promote` | backlog | planned | `ccc-board.py product --promote` |
| **dev** | 10min | Engine 自动 | planned + in_progress | in_progress → testing | `ccc-engine.py dev_role_launch()` |
| **reviewer** | 2h | Engine 在 dev 完成后立即调 | testing | testing → verified | `ccc-engine.py → reviewer_role()` |
| **tester** | 4h | Engine 在 dev 完成后立即调 | testing | testing → verified | `ccc-engine.py → tester_role()` |
| **ops** | 30min | Engine 空闲时 | 所有列 | — | `ccc-engine.py → _check_stale()` |
| **kb** | 每天 23:00 | Engine 在 reviewer+tester 通过后 | verified | verified → released | `ccc-engine.py → kb_role()` |
| **regress** | 每天 23:30 | 保留独立定时 / 或嵌在 Engine 内 | released | released → backlog | 待定 |

**引擎约束**：有 task 即串行执行全链路，无 task 休眠 5s（红线 X6 更新版）。

### 2.2 看板流转图

```
┌──────────┐   ┌──────────┐   ┌──────────────┐
│ backlog  │ → │ planned  │ → │ in_progress  │
└──────────┘   └──────────┘   └──────────────┘
   老板建 task    product         dev
                                    ↓
                              ┌──────────────┐
                              │   testing     │
                              └──────────────┘
                                 ↓        ↑
                            reviewer    tester
                                 ↓        ↓
                              ┌──────────────┐
                              │   verified    │
                              └──────────────┘
                                 ↓
                            kb (每天 23:00)
                                 ↓
                              ┌──────────────┐
                              │   released    │ → git tag + push
                              └──────────────┘
                                     ↓ (regress 23:30)
                              ┌──────────────────────┐
                              │   backlog(回归bug)    │ → regress 建 bug task
                              └──────────────────────┘
```

### 2.3 7 plist 装上后

```bash
$ launchctl list | grep com.ccc
com.ccc.product    # 4h
com.ccc.dev        # 10min
com.ccc.reviewer   # 2h
com.ccc.tester     # 4h
com.ccc.ops        # 30min
com.ccc.kb         # 每天 23:00
com.ccc.regress    # 每天 23:30
com.ccc.flywheel-scan  # 老的（保留作 1h 周期飞轮备份）
```

---

## 3. 任务看板 `.ccc/board/`

6 列目录：
```
.ccc/board/
├── backlog/         # 老板提的原始需求
├── planned/         # product 写好 plan.md
├── in_progress/     # dev 在写
├── testing/         # dev 完成, 等 reviewer/tester
├── verified/        # 双检查通过
├── released/        # kb 归档 + tag
├── index.json       # 状态总览
└── README.md        # 流转规则
```

**单 task JSONL 格式**：
```json
{"id":"v0.16-e2e","title":"...","status":"backlog",
 "created_at":"2026-07-07T17:30:00Z","updated_at":"...",
 "assignee":null,"tags":["e2e","v0.16"]}
```

**操作命令**：
```bash
# 看总览
python3 ~/program/CCC/scripts/ccc-board.py index

# 跑单个角色
python3 ~/program/CCC/scripts/ccc-board.py product
python3 ~/program/CCC/scripts/ccc-board.py dev
python3 ~/program/CCC/scripts/ccc-board.py reviewer
python3 ~/program/CCC/scripts/ccc-board.py tester
python3 ~/program/CCC/scripts/ccc-board.py ops
python3 ~/program/CCC/scripts/ccc-board.py kb
python3 ~/program/CCC/scripts/ccc-board.py regress

# 一键装 7 plist
bash ~/program/CCC/scripts/install-ccc-roles.sh
```

---

## 4. 完整调用链

```
老板 (你)
  ↓ "按 CCC 跑 X"
ccc-auto-dev.sh (scripts/ccc-auto-dev.sh)
  ↓ 写 task 到 .ccc/board/backlog/
launchd (每 4h 启动 com.ccc.product)
  ↓ product role
  写 .ccc/plans/<task>.plan.md + .ccc/phases/<task>.phases.json
  挪 task → planned/
launchd (每 10min 启动 com.ccc.dev)
  ↓ dev role
  调 opencode run --model loop/flash (loop 中转站)
  opencode 写代码 + 写 report
  挪 task → in_progress/ → testing/
launchd (每 2h 启动 com.ccc.reviewer)
  ↓ reviewer role
  python3 -m py_compile 全 .py
  通过则挪 task → verified/
launchd (每 4h 启动 com.ccc.tester)
  ↓ tester role
  pytest tests/scripts/ -q
  通过则挪 task → verified/
launchd (每天 23:00 启动 com.ccc.kb)
  ↓ kb role
  git tag board-<task> + git push
  挪 task → released/
launchd (每天 23:30 启动 com.ccc.regress)
  ↓ regress role
  从 released 取任务，每日回测
  发现回归 bug → 建 bug task → 挪到 backlog/
```

---

## 5. 红线（永久约束）

| # | 红线 | 短句 |
|---|------|------|
| 1 | 不动系统文件 | /etc、~/.env、密钥 |
| 2 | 验收可执行 | 自然语言 + 命令 |
| 3 | 不超出 plan 文件范围 | 白名单 |
| 4 | 单 phase 单 commit | 兜底脚本做 |
| 5 | phases.json 必写全 | JSONL, 不嵌套 |
| 6 | 角色不互串 | 边界硬性 |
| 7 | 启动顺序固定 | 读 profile 第一 |
| 8 | 每步必 commit | 不攒 |
| 9 | Executor 卡死立即止损 | kill + Planner 接管 |
| 10 | 禁止跨会话隐式记忆 | state.md 强制接力 |
| 11 | Verifier 必写 verdict 文件 | 口头 PASS 不算 |
| 12 | 禁止 agent 自主启用 CCC | 老板显式触发 |
| 13 | 禁止未使用路线代码 | v0.7-slim 精简 |
| X1 | OpenCode 进程池 ≤ 3 | M1 8GB 内存敏感 |
| X2 | 每 phase 必杀 opencode | finally + watchdog |
| X3 | OpenCode 启动前必跑残留 watchdog | launcher Step 1 |
| **X4** | **每 phase 必走看板流转** | 跨角色不可跳列 |
| **X5** | **7 plist 必装** | install-ccc-roles.sh |
| **X6** | **角色频率不许改** | 老板拍板 |

---

## 6. 自动化 / 定时 / 钩子全表

| 能力 | 实现 | 工件 |
|------|------|------|
| 单 phase 启动 | `scripts/ccc-exec-launcher.sh` | 5 步：watchdog → pre-exec → exec → on-error → post-exec |
| 多 phase 队列 | `scripts/ccc-queue.sh` | 3 次失败升级 L3 |
| 周期飞轮 | launchd `com.ccc.flywheel-scan` | 3600s |
| **7 角色周期** | launchd `com.ccc.{product,dev,reviewer,tester,ops,kb,regress}` | 老板指定频率 |
| 进程池 | `scripts/opencode-pool.py` | Semaphore(3) |
| 必杀 | `scripts/opencode-watchdog.sh` | killpg + pkill -f 兜底 |
| 钩子 | `~/.ccc/hooks/{pre-exec,post-exec,on-error}.sh` | 模板在 `templates/hooks/` |
| 通知 | `scripts/ccc-notify.sh` | L1/L2/L3 桌面通知 + 告警存档 |
| **看板流转** | `scripts/ccc-board.py` | 7 角色核心 |
| **自动 commit+push** | `templates/hooks/post-exec.sh` | CCC_PUSH=1 默认 |
| **入口** | `scripts/ccc-auto-dev.sh` | 你说"按 CCC 跑 X"后调 |

---

## 7. 模型路由（CLAUDE.md 红线：唯一对外模型名 = flash）

```bash
opencode run --model loop/flash "<msg>"     # 唯一允许
```

**禁止**：
- 省略 `--model`（落默认值 `loop/code`）
- 硬编码 `claude-opus-*` / `claude-sonnet-*` / `claude-haiku-*` / `claude-fable-*`
- 硬编码 `minimax-*` / `deepseek-*` / `gpt-*` / `gemini-*` / `glm-*`

**注意**：opencode 1.17 真实命令是 `run` 不是 `exec`（Lesson 32+33）。
**注意**：opencode run positionals 截断 200 字符，长 prompt 走 `--file` 附件（v0.11 修）。

---

## 8. 沉淀教训（v0.16 时点 = 36 条）

**关键教训**（任何 agent 必读）：
- **Lesson 27**：`claude -p` 是 print 模式，prompt 走 stdin
- **Lesson 28**：口头 PASS ≠ 真 PASS，Verifier 必写 verdict 文件
- **Lesson 32**：opencode 模型名必须带 provider 前缀（loop/flash）
- **Lesson 33**：opencode run positionals 截断 200 字符，长 prompt 走 --file
- **Lesson 34**：opencode run 起 node 孙子进程，killpg 在 macOS 不可靠
- **Lesson 35**：opencode 写代码 > v0.7 时代人工基线
- **Lesson 36**：bug 分类（数据泄漏 / 静默失败 / 配置硬编码）

---

## 9. 怎么用本文件

| 你是 | 读 | 然后 |
|------|----|------|
| 新 cloud agent 启动 | 本文件 | 读 CLAUDE.md → 读 SKILL.md → 开工 |
| 老板（你）| 决策点 | 说"按 CCC 跑 X" |
| 任何 agent 调红线条目 | 必查 references/red-lines.md | 13+2+X3+X4/X5/X6 |

---

## 10. 下一步（v0.17+ 决策点）

- **v0.17a**：跑 1 个真 backlog task 看 7 角色端到端流转（要 harness 配合）
- **v0.17b**：加红线 X4/X5/X6 到 red-lines.md 正式版
- **v0.17c**：让 product 角色能根据 .ccc/board/backlog/ 自动生成 plan（不只读 task）
- **v0.18**：跨项目任务（qx-observer / xianyu 也能用这 7 角色系统）

---

**最后更新**: 2026-07-07 v0.16 完结后
**维护者**: 任何 agent 改完后追加 changelog
**优先级**: 最高（启动必读第一）
