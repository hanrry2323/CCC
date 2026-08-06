# 验收看板 SOP（M1 人工终验）

> **状态：现行 · 2026-08-06**  
> 两层验收：① 2017 机审（Engine 拉 Claude/OpenCode 写 `## 机审区`；看板「机审」栏）② **本 SOP = M1 人工终验**（写 `## 验收区` + `已关闭`）。  
> 机审流程详述：[`machine-audit-flow.md`](machine-audit-flow.md)
> 权威链：[`dev-channel.md`](dev-channel.md) · [`CLAUDE.md`](../../CLAUDE.md) · [`../INDEX.md`](../INDEX.md) §0

## 一句话

老板在 M1 IDE（Claude Code 或 OpenCode）说 **「验收看板」**（同义：`验收回写` / `终验看板`）→ 代理只扫「可终验」卡 → 分席取证 → 通过则关卡，失败则打回。

## 可终验卡条件（全满足）

1. 卡头 `状态：已回写`（非已关闭 / 非执行中）
2. 正文有 `## 机审区`，且其后 20 行内含 `机审：通过` 或 `✅` 或 `判定：通过`
3. 尚无合格的 `## 验收区` 通过标记（否则视为已终验）

缺机审通过 → **跳过**，向老板报「仍待 2017 机审」，不擅自关卡。

## 分席（交叉）

| 卡头执行体 | 终验谁做 |
|------------|----------|
| OpenCode | **Claude Code** |
| Claude Code | **OpenCode** |

当前 IDE 若不是该卡终验席 → 列出卡号并提示换对家窗口，或只处理属于本席的卡。  
**Cursor / Codex 不响应本 SOP、不关卡。**

## 动作清单（模型自决细节）

对每一张归属本席的可终验卡：

1. Read 卡全文（目标 / 红线 / 范围 / 验收标准 / 回写区 / 机审区）。
2. 独立取证：卡内分支 `git log` / `git diff origin/main...HEAD`（或 GitHub），**不采信**回写区摘要与机审一句话。
3. **通过**：在卡末写 `## 验收区`，含 `判定：通过` 或 `✅`；卡头 `状态：已关闭`；需要时 ff 合入 `main`（按卡说明）。
4. **不通过**：卡头 `状态：打回（…）`，问题清单写清；**不**写验收通过；不合入。

## 禁止

- 自验：开发执行体 = 本 IDE 时，不对本卡终验关卡。
- 跳过机审未过的卡。
- 改业务代码冒充终验（终验只改卡文件状态/验收区，合入按卡约定）。
- 让老板手选「先验哪张」——默认扫全板可终验卡，一次性汇报结果。

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
# 关键字示例：机审 / machine_audit / 验收席
tail -n 200 ~/.ccc/logs/engine*.log | rg -n '机审|audit|验收席'
```

代码门禁与钩子在 `server/engine/main.py`；合入 main 后 2017 `git pull --ff-only` + kickstart Engine 才生效。
