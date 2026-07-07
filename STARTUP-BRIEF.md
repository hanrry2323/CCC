# CCC Startup Brief (v0.18 启动必读)

> **读完这个文件 = 知道 CCC 全部怎么用。** 其他文件按需 grep。
> **目标: 启动 token < 200。** v0.17 4 文件 11k → 1 文件 200 = 省 98%。

---

## 1. CCC 一句话

CCC = 单节点 + 6 角色定时开发 + 任务看板 + opencode CLI 执行器 + launchd 周期。

**4 个数字必记**：
- **6 角色** = product / dev / reviewer / tester / ops / kb
- **6 列看板** = backlog → planned → in_progress → testing → verified → released
- **19 红线** = 13 经典 + 2 历史 + 3 v0.8 进程 + 3 v0.16 看板
- **6 plist** = com.ccc.{product,dev,reviewer,tester,ops,kb} + 1 老的 flywheel-scan

---

## 2. 6 角色（频率不许改 — 红线 X6）

| 角色 | 频率 | 干 |
|------|------|-----|
| product | 4h | 扫 backlog → 写 plan.md + phases.json，挪 planned |
| dev | 30min | 调 opencode 写代码，挪 in_progress → testing |
| reviewer | 2h | py_compile，挪 testing → verified |
| tester | 4h | pytest，挪 testing → verified |
| ops | 30min | 健康检查 + 告警（不动 board）|
| kb | 23:00 | git tag + push，挪 verified → released |

**入口**：`python3 scripts/ccc-board.py {product|dev|reviewer|tester|ops|kb}`

---

## 3. 看板流转（一行图）

```
backlog → planned → in_progress → testing → verified → released
   ↑          ↓          ↓            ↓          ↓
 老板建     product      dev     reviewer    tester    kb
                                  +tester
```

**X4 强制**：不可跳列。跳列 = 跳过对应角色 = Critical 违规。

---

## 4. 19 红线（极简，**正文按需 grep**）

- **1-15**: `references/red-lines.md` §编号索引表
- **18-20**: 同表
- **X1-X3**: 进程管理（v0.8）
- **X4-X6**: 看板+plist+频率（v0.16）

**4 条致命 (Critical)**：
- 红线 1：不动系统文件
- 红线 11：Verifier 必写 verdict 文件
- 红线 12：禁止 agent 自主启用 CCC
- 红线 X4：每 phase 必走看板

**怎么查具体某条红线**：
```bash
grep -A 10 "## 红线 11" references/red-lines.md
```

---

## 5. 38 教训（只记 5 条最关键）

| # | 教训 | 怎么避 |
|---|------|--------|
| 27 | `claude -p` 是 print 模式，prompt 走 stdin | 不写 `claude -p "..."` |
| 28 | 口头 PASS ≠ 真 PASS | Verifier 必写文件 |
| 32 | opencode 模型名带 provider 前缀 | 用 `loop/flash` 不是 `flash` |
| 33 | opencode run positionals 截断 200 字符 | 长 prompt 走 `--file` |
| 35 | opencode 写代码 > v0.7 时代人工 | 默认 "opencode 写 + 人工 review" |

**怎么查其他 33 条**：
```bash
grep -B 1 -A 3 "## Lesson 36" docs/lessons.md
```

---

## 6. 自动化 / 定时 / 钩子（按需查 commands）

| 能力 | 入口 | 触发 |
|------|------|------|
| 你说"按 CCC 跑 X" | `scripts/ccc-auto-dev.sh <ws> <task> "<goal>"` | 你手触发 |
| 6 角色轮询 | launchd 6 plist | 自动定时 |
| 看板状态总览 | `python3 scripts/ccc-board.py index` | 任何时候 |
| 跑单个角色 | `python3 scripts/ccc-board.py <role>` | 任何时候 |
| 装 6 plist | `bash scripts/install-ccc-roles.sh` | 首次 / 重新装 |
| 周期飞轮备份 | `com.ccc.flywheel-scan` (3600s) | 自动 |

---

## 7. 模型（CLAUDE.md 红线）

```bash
opencode run --model loop/flash "<msg>"   # 唯一允许
```

**禁止**：裸 `flash` / `claude-*` / `minimax-*` / `deepseek-*` / `gpt-*`

---

## 8. 怎么"懒加载"其他文件（v0.18 核心规则）

**你看到本 brief 不够** = 按需 grep：

```bash
# 战略地图全貌（330 行）
cat docs/STRATEGY-MAP.md

# 红线某条细节
grep -A 15 "## 红线 <编号>" references/red-lines.md

# 教训某条
grep -A 8 "## Lesson <编号>" docs/lessons.md

# 看板状态
python3 scripts/ccc-board.py index

# 当前任务接力
head -100 .ccc/state.md
```

**黄金规则**：
1. **不预先全读**（4 个文件 11k token 太贵）
2. **按关键词 grep**（"red line 11" → `grep "## 红线 11"`，几百 token）
3. **brief + 按需** = 200 token 启动

---

## 9. 完整调用链（1 行）

老板 "按 CCC 跑 X" → `ccc-auto-dev.sh` → `launcher` → `opencode run --model loop/flash` → `post-exec` 自动 commit+push → 远端。

详细见 `docs/STRATEGY-MAP.md` §4。

---

**版本**: v0.18
**大小**: ~200 token
**替换**: v0.17 启动必读 4 文件（11k token）
**省**: 98%
