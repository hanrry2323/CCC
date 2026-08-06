# 验收看板 SOP（M1 人工终验）

> **状态：现行 · 2026-08-07**  
> 两层验收：① 2017 **机审**（Engine 自动写 `## 机审区`；看板「机审」栏）② **本 SOP = M1 人工终验**（写 `## 验收区` + `已关闭`）。  
> 机审流程：[`machine-audit-flow.md`](machine-audit-flow.md)  
> 权威链：[`dev-channel.md`](dev-channel.md) · [`CLAUDE.md`](../../CLAUDE.md) · [`../INDEX.md`](../INDEX.md) §0

## 一句话

老板说 **「验收看板」**（同义见下）→ 代理**只做终验** → 30 秒内列出可终验 / 仍待机审 → 分席取证 → 通过则关卡，失败则打回。

### 触发同义句（任一即走本 SOP）

`验收看板` · `验收回写` · `终验看板` · `验收已回写` · `验收已回写卡片`

**不是机审口令。** 听到上列句子 → **禁止**自认 2017 机审席、禁止写/改 `## 机审区`、禁止 /tmp merge 考古。

---

## §0 开场硬步骤（必须先做 · 禁止全仓 grep）

收到触发语后**立刻**执行下面之一，再说话。禁止先扫 `docs/dispatch`、禁止猜 `/board/cards`。

```bash
# 1) 看板列语义（机审 ≠ 卡头「已回写」计数）
curl -s http://192.168.3.116:7788/board/snapshot | python3 -c "
import sys,json
d=json.load(sys.stdin)
cols=d.get('columns') or {}
print('机审', [c.get('id') for c in cols.get('机审') or []])
print('可终验已回写', [c.get('id') for c in cols.get('已回写') or []])
print('counts', d.get('counts'))
"

# 2) 或 /cards（含 board_column）
curl -s 'http://192.168.3.116:7788/cards?page_size=200' | python3 -c "
import sys,json
d=json.load(sys.stdin)
for c in d.get('cards') or []:
  if c.get('board_column') in ('机审','已回写'):
    print(c.get('id'), c.get('board_column'), c.get('state'), 'audit', c.get('machine_audit_passed'))
"

# 3) 消歧：/board/states 顶层=卡头五态；.columns=看板列
curl -s http://192.168.3.116:7788/board/states
```

### 分流（看完 §0 再动手）

| 看板列 `board_column` | 代理动作 |
|----------------------|----------|
| **机审** | 向老板报「仍待 2017 Engine 机审」+ 卡号；**停手**（不写机审区、不代跑 audit） |
| **已回写**（且机审已过） | 进入下方「可终验」动作清单 |
| 其它 | 忽略 |

**卡头五态「已回写」计数常包含「机审」列**（`/board/states` 顶层键）。终验只认 **看板列「已回写」** 或 `machine_audit_passed=true`。

---

## 可终验卡条件（全满足）

1. 看板列 = **已回写**（或卡头已回写 **且** `machine_audit_passed` / 正文有合格 `## 机审区`）  
2. 正文有 `## 机审区`，且其后 20 行内含 `机审：通过` 或 `✅` 或 `判定：通过`  
3. 尚无合格的 `## 验收区` 通过标记（否则视为已终验）

缺机审通过 → **跳过**，报「仍待 2017 机审」，不擅自关卡、**不代写机审区**。

---

## 分席（交叉）

| 卡头执行体 | 终验谁做 |
|------------|----------|
| OpenCode | **Claude Code** |
| Claude Code | **OpenCode** |

当前 IDE 若不是该卡终验席 → 列出卡号并提示换对家窗口，或只处理属于本席的卡。  
**Cursor / Codex 不响应本 SOP、不关卡。**

---

## 动作清单（可终验卡）

对每一张归属本席的可终验卡：

1. Read 卡全文（目标 / 红线 / 范围 / 验收标准 / 回写区 / 机审区）。  
2. **取证（真值在分支，不在未 fetch 的 main 卡头）**：

```bash
# 卡文件名例 ccc005-registry-single-source.md → 分支 codex/ccc005-registry-single-source
git fetch origin "codex/<文件名去.md>"
git log --oneline origin/main.."origin/codex/<文件名去.md>"
git diff --stat origin/main..."origin/codex/<文件名去.md>"
```

不采信回写区摘要与机审一句话。本机 `docs/dispatch` 卡头仍「待分派」时，以 **2017 snapshot / 分支 tip** 为准（见 [`machine-audit-flow.md`](machine-audit-flow.md)「代理易错」）。

3. **通过**：卡末写 `## 验收区`（含 `判定：通过` 或 `✅`）；卡头 `状态：已关闭`；需要时 ff 合入 `main`（按卡说明）。  
4. **不通过**：卡头 `状态：打回（…）`，问题清单写清；**不**写验收通过；不合入。

---

## 禁止（终验席）

- 自验：开发执行体 = 本 IDE 时，不对本卡终验关卡。  
- 跳过机审未过的卡；**禁止 M1 代写 / 改写 `## 机审区`**（机审只属 2017 Engine）。  
- 为「搞清差异」在 `/tmp` merge main、满仓 grep、把 feature 分支机审 push 冒充 Engine。  
- 改业务代码冒充终验（终验只改卡文件状态/验收区，合入按卡约定）。  
- 让老板手选「先验哪张」——默认扫全板可终验卡，一次性汇报结果。

---

## Worktree / 提交 / 打回（中间过程定稿）

| 环节 | 谁 | 规则 |
|------|----|------|
| Worktree | Engine | `ccc-dev-ws-<id>` 一卡一树；可复用，不随意删 |
| 业务 commit | 仅开发执行体 | push 卡内分支；禁止直推 main |
| 机械门禁 | Engine | 无新 commit 或 diff 空 → 打回 |
| 机审 | 2017 验收席 CLI | 只写 `## 机审区`；失败 → 打回 → 再派开发 |
| 终验 | M1 本 SOP | 写验收区 + 已关闭，或打回 |
| 重写 | Engine 自动 | 打回→待分派→OpenCode（或卡头执行体）再跑 |

冲突/脏树：执行体自行 `git status` 处理；人不管中间。

## 老板面

只需：出卡意图 + 看板看流转 + 说「验收看板」。不必管 pull、worktree、机审命令。

## 2017 探活（运维）

配置：`server/config/executors.json` 验收席须为「可后台 CLI」且有命令（见 `executors.example.json`）。

```bash
# 注册表验收席是否可机审
python3 -c "from server.engine.dispatch import load_registry; r=load_registry('server/config/executors.json'); print([(e.binding,e.category,bool(e.command)) for e in r.entries if e.role=='验收席'])"

# 回写后日志应出现机审拉起（Engine 日志目录）
tail -n 200 ~/.ccc/logs/engine*.log | rg -n '机审|audit|验收席'
```

代码门禁与钩子在 `server/engine/main.py`；合入 main 后 2017 `git pull --ff-only` + kickstart Engine 才生效。
