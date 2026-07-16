# CCC Startup Brief (v0.38.0 启动必读)

> **读完这个文件 = 知道 CCC 怎么用。** 其他文件按需 grep。
> **目标：启动 token < 700。** 不预先全读 STRATEGY-MAP / lessons / red-lines。

---

## 1. CCC 一句话

CCC = **7 角色看板** + **CCC Engine 串行驱动** + **Claude（product/review）+ OpenCode（dev）** + **launchd 常驻 Engine**。

**4 个数字必记**：
- **7 角色** = product / dev / reviewer / tester / ops / kb / regress
- **6 列看板** = backlog → planned → in_progress → testing → verified → released
- **12+ 红线** = 见 `references/red-lines.md`（含 R-04/07/08/09/12/14）
- **2 plist** = `com.ccc.engine` + `com.ccc.board-server`（X5，非 7 角色定时）

---

## 2. 7 角色（Engine 串行，无定时 — X6 已废止）

| 角色 | Engine 触发 | 干 |
|------|-------------|-----|
| product | backlog 非空 → 异步 `claude -p` 拆分（或手动 `--promote`） | 写 plan + phases → planned |
| dev | planned / in_progress 有 task 即跑 | opencode 写代码；多 phase 续跑 → testing |
| reviewer | testing 列门禁（~60s tick） | LLM/静态审查 → 写 **verdict.md** |
| tester | testing 列门禁（紧随 reviewer） | pytest + 验收清单 |
| ops | 调试手动 / 可选空闲检查 | 健康检查 + 告警（不动 board） |
| kb | **verified 列非空即跑**（v0.38） | bump VERSION + tag + CHANGELOG → released |
| regress | 23:30 定时或手动 | released 回测 → backlog(回归 bug) |

**v0.37+ 空闲默认**：空看板不 `auto_replenish` / 不 `evolve`（防内存爆）。显式开：`CCC_AUTO_REPLENISH=1` 等。

**v0.38.1 总开关**：`~/.ccc/DISABLED` 存在时，Engine/patrol/loop-monitor **禁止自启**。
```bash
bash scripts/ccc-autostart-guard.sh disable   # 停机 + 卸 crontab 自启
bash scripts/ccc-autostart-guard.sh enable    # 允许再启（仍需手动 load plist）
bash scripts/ccc-autostart-guard.sh status
```
**禁止**把 `ccc-loop-monitor.sh` 装进 crontab（旧版会每 5 分钟强制 `python3 ccc-engine.py &`）。

**入口**：`python3 scripts/ccc-board.py {product|dev|reviewer|tester|ops|kb|regress}`（调试用手动；生产靠 Engine）

---

## 3. 看板流转（一行图）

```
backlog → planned → in_progress → testing → verified → released
   ↑          ↓          ↓            ↓          ↓          ↓
 老板建     product      dev     reviewer    tester      kb
                                  +tester              regress→backlog
```

**X4 强制**：不可跳列。`complexity=small` 时 reviewer+tester 可跳过（v0.28.1）。

---

## 4. 红线（极简，正文按需 grep）

- **1–12 + R- 系列**：`references/red-lines.md`
- **X1–X5**：进程 + 看板 + Engine plist
- **X6**：角色频率（v0.20.1 起不再适用，保留索引）

**4 条致命 (Critical)**：
- 红线 1：不动系统文件
- 红线 11：Verifier 必写 verdict 文件
- 红线 12：禁止 agent 自主启用 CCC
- 红线 X4：每 phase 必走看板

```bash
grep -A 10 "## 红线 11" references/red-lines.md
```

---

## 5. 教训（只记 5 条最关键）

| # | 教训 | 怎么避 |
|---|------|--------|
| 27 | `claude -p` 是 print 模式，prompt 走 stdin | 不写 `claude -p "..."` |
| 28 | 口头 PASS ≠ 真 PASS | Verifier 必写文件 |
| 32 | opencode 模型名带 provider 前缀 | 用 `loop/flash` |
| 33 | opencode run positionals 截断 200 字符 | 长 prompt 走 `--file` |
| 35 | opencode 写代码 > v0.7 时代人工 | 默认 "opencode 写 + 人工 review" |

```bash
grep -A 8 "## Lesson 36" docs/lessons.md
```

---

## 6. 自动化 / 定时 / 钩子

| 能力 | 入口 | 触发 |
|------|------|------|
| 建 task 落 backlog | `ccc-board.py --batch`（JSONL）或 board-server API | 你手触发 |
| Engine 串行全链路 | `com.ccc.engine` → `ccc-engine.py` | launchd KeepAlive |
| 看板状态 | `python3 scripts/ccc-board.py index` | 任何时候 |
| 装 Engine + board-server | `bash scripts/install-ccc-roles.sh` | 首次 / `--upgrade` 清旧 7 plist |
| 单 phase 执行 | `scripts/ccc-exec-launcher.sh` | dev 角色内部调 |

---

## 7. 模型

```bash
opencode run --model loop/flash "<msg>"   # 唯一允许
```

**禁止**：裸 `flash` / `claude-*` / `minimax-*` / `deepseek-*` / `gpt-*`

---

## 8. 懒加载其他文件

```bash
cat docs/STRATEGY-MAP.md          # 全景（按需）
grep -A 15 "## 红线 N" references/red-lines.md
grep -A 8 "## Lesson N" docs/lessons.md
python3 scripts/ccc-board.py index
head -100 .ccc/state.md
```

**黄金规则**：brief 够了 → 不够再 grep，不预先全读。

---

## 9. Verdict 路径（红线 11）

Engine 门禁只认：`.ccc/verdicts/{task_id}.verdict.md`（含 `**Verdict:** PASS`）。
仅写 `reports/{tid}.review.md` **不算** PASS。

---

## 10. 完整调用链（1 行）

老板 "按 CCC 跑 X" → `create_task` 落 backlog → Engine 自动 `product_role` 拆分 → dev → reviewer+tester → kb → released。

详细见 `docs/STRATEGY-MAP.md` §4。

---

**版本**: v0.30.0（权威：`VERSION` 文件）
**替换**: v0.18 7 plist 定时范式 → Engine 串行 + 2 plist
**维护**: 范式/版本变更时同步 STRATEGY-MAP + SKILL.md + README（均链回本 Brief）
**约束**: 禁止在 Engine 外并发调用 `ccc-board` 并依赖模块全局 `ROOT`（F-CON-03）
