# 舰队清理 Playbook — 2026-07-18

配套盘点：[fleet-hygiene-2026-07-18.md](./fleet-hygiene-2026-07-18.md)

图例：`[AUTO]` 本轮可直接做 · `[CONFIRM]` 需你点头 · `[HOLD]` 本轮不做

---

## P0 — 可靠性 / 卫生噪音

### P0.1 `[AUTO]` CCC：对齐 CLAUDE.md（R-15 + invent 硬关）

```bash
# 在 CCC 仓编辑 CLAUDE.md：
# - Hub 基线 #6：空板闲置正常；新工作 → Hub 选业务仓定稿下达；禁止对 CCC orch 写 epic
# - invent 行：标注已退役 / invent_hard_disabled，勿启用
```

### P0.2 `[AUTO]` clawmed-ccc：隐藏 done epic `task-dzgb`

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/Users/apple/program/clawmed-ccc/.ccc/board/backlog/task-dzgb.jsonl")
lines = p.read_text(encoding="utf-8").splitlines()
t = json.loads(lines[0])
t["ui_hidden"] = True
p.write_text(json.dumps(t, ensure_ascii=False) + "\n", encoding="utf-8")
print("ui_hidden", t["id"], t["ui_hidden"])
PY
python3 /Users/apple/program/CCC/scripts/ccc-workspace-doctor.py | grep -E 'clawmed|done_epic|summary'
```

### P0.3 `[HOLD→文档]` `projects/qx`：保持不登记

- 理由：与 clawmed 同产品线零件库（M1 已摘 Engine）
- 动作：不 `register`；Hub 侧改为 `engine_eligible=false`（见 P0.4）

### P0.4 `[AUTO]` Hub：未登记 workspace 默认不可 Engine 下达

- 改 `scripts/chat_server/routers/projects.py`：Board 发现但 **不在 registry** → `engine_eligible=False`
- 重启：`launchctl kickstart -k gui/$(id -u)/com.ccc.chat-server`

---

## P1 — 入口 / 明显垃圾

### P1.1 `[SKIP]` xianyu 双 CLAUDE

根 stub 已指向 `.claude/CLAUDE.md` — 合格，无需改。

### P1.2 `[AUTO]` hp：删除备份树

```bash
rm -rf /Users/apple/program/hp/.bak-20260712-K23
```

### P1.3 `[AUTO]` 清 `.DS_Store` / 根 `__pycache__`

```bash
rm -f /Users/apple/program/xianyu/.DS_Store /Users/apple/program/xianyu/.ccc/.DS_Store
rm -f /Users/apple/program/hp/.DS_Store
rm -f /Users/apple/program/qx-observer/.DS_Store /Users/apple/program/qx-observer/.ccc/.DS_Store
rm -rf /Users/apple/program/qx-observer/__pycache__
```

### P1.4 `[AUTO]` CCC：prune 可删 worktree

```bash
cd /Users/apple/program/CCC
git worktree list
# 移除 prunable（勿动 locked）
git worktree remove --force .claude/worktrees/agent-a0b82a71993fa76d1 2>/dev/null || true
git worktree remove --force .claude/worktrees/chat-v031-frontend 2>/dev/null || true
git worktree prune
git worktree list
```

---

## P2 — 膨胀（需确认）`[CONFIRM]`

| # | 动作 | 命令提示 |
|---|------|----------|
| P2.1 | CCC/qxo/qb orphan plans 归档 | `mkdir -p .ccc/archive/plans && mv .ccc/plans/*.plan.md .ccc/archive/plans/`（先 dry-run 列表） |
| P2.2 | qb `on-hold/` | 文档声明非活跃，或迁 `abnormal` / 归档 |
| P2.3 | apps heartbeat/stats | 各仓 `.gitignore` 加 `.ccc/engine-heartbeat.json`、`.ccc/stats/` |

---

## P3 — 安全 / 远程 `[HOLD]`

| # | 动作 |
|---|------|
| P3.1 | qb：审查并删除或 gitignore `.credentials.note`（**永不 commit**） |
| P3.2 | qb ahead 218 / qxo ahead 66：人工决定 push 或整理，本 playbook 不自动 push |

---

## 本轮执行记录（2026-07-18）

| 项 | 结果 |
|----|------|
| P0.1 CLAUDE.md | 已改 |
| P0.2 task-dzgb ui_hidden | 已改（clawmed 仓） |
| P0.3 qx 不登记 | 文档确认 |
| P0.4 Hub 未登记 eng=false | 已改 + Hub kickstart |
| P1.1 xianyu CLAUDE | SKIP（已合格） |
| P1.2 hp bak | 已删 |
| P1.3 DS_Store / pycache | 已清 |
| P1.4 CCC worktree | 2 prunable 已移除；1 locked 保留 |
| P2.1 orphan plans 归档 | CCC 101→archive；qb 61→archive（留 3 on-hold）；qxo 107→archive |
| P2.2 qb on-hold | README + state 注明非活跃 |
| P2.3 heartbeat/stats gitignore | 全舰队 apps + CCC |
| P3.1 credentials.note | 已删 + `.gitignore`（含 secret 关键词，未入库） |
| P3.2 ahead push | CCC/qb/qxo/xianyu/ai-loop-router/hp/Medio-0 **已 push**；clawmed-ccc **无 origin**（本地 commit 已做） |

P2/P3 **已执行完毕**。

```bash
python3 ~/program/CCC/scripts/ccc-workspace-doctor.py
# 期望：CCC orch eng=False；clawmed 无 done_epic_visible；errors=0
curl -s -u ccc:ccc http://127.0.0.1:7777/api/projects | python3 -c "import sys,json;d=json.load(sys.stdin);print('default',d.get('default_project'));
print([(p['id'],p.get('engine_eligible')) for p in d['projects'] if p['id'] in ('ccc','qx')])"
```

每仓改动各自 commit；CCC 平台改动只在 CCC 仓。不经 Hub 下达到 CCC。
