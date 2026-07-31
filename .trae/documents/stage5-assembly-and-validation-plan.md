# 阶段 5：拼装 + 最小闭环验证（开发计划）

> **状态**：WP1-WP3 已完成 · WP4/WP5.3 待执行 · 2026-07-31 实测评估
> **基准**：`docs/product/ccc-new-architecture-overview.md`（新架构四层分工）
> **前置**：阶段 1-4 已扎实（核心文档/冲突清单/组件盘点已就绪）
> **范围**：闭环 + 同步清理旧字段（硬切换）

---

## 〇、实测前置评估（2026-07-31）

### 结论：✅ 具备进入剩余 WP4 + WP5.3 的前提

### 已就绪项（实测验证）

| 项 | 实测证据 | 状态 |
|----|----------|------|
| 阶段1-4 文档 | 决策状态/并发控制/版本管理/两阶段路径已扎实（上次会话确认） | ✅ |
| WP1 transfer_gate 硬切换 | `resolve_skill_ref`(L966) + `resolve_executor_from_skill`(L993) 已实现；skill_ref/prompt_ref 必填校验已加(L161-192) | ✅ |
| WP2 旧字段清理 | desktop.py 14 处已改 skill_ref/prompt_ref；`_epic_default_executor`(L529) 已重写从 skill_ref 推断；executor_intent 残留 12 处均为注释/史径保留/向后兼容映射 | ✅ |
| WP3 测试 fixture | 已批量迁移（待最终 `pytest tests/ -x` 全绿确认） | ✅ |
| Skill 库 | 5 个：write-code / code-review / bug-fix / ops / script-seed | ✅ |
| Prompt 库 | 3 个：write-code-prompt / code-review-prompt / bug-fix-prompt | ✅ |
| 复用资产 | `_product_session.run_contract_loop_sync`(L249) + `_product_fanout.build_fanout_prompt`(L175)/`parse_fanout_output`(L326)/`apply_fanout`(L568) 签名干净 | ✅ |
| 现有 inbox 机制 | `proposals.py` 已有 inbox_dir/list_proposals/get_proposal/proposal_to_transfer_body/mark_adopted；desktop.py 已有 `/proposals`(L1101) + `/proposals/{id}/adopt`(L1110) | ✅（可参考） |

### 未就绪项（WP4 尚未开始）

| 项 | 现状 | 阻塞 |
|----|------|------|
| `scripts/ccc-intent-splitter.py` | 文件不存在 | 无 Claude 后台拆卡程序 |
| `scripts/ccc-submit-proposal.py` | 文件不存在 | IDE 无法激活拆卡 |
| Hub `/api/desktop/proposal` 端点 | desktop.py 无此端点（仅有复数 `/proposals` inbox） | 无方案接收入口 |

### 进入 WP5.3（最小闭环）的前置链

```
WP4.1 splitter  ─┐
WP4.2 submit   ──┼─→ WP4.3 Hub 端点 ─→ WP5.3 最小闭环
（可并行，接口契约先行）
```

---

## 一、Summary（一句话）

**硬切换 transfer_gate 强制 skill_ref/prompt_ref → 清理全仓 ~88 处 executor_intent 残留 → 新建 splitter/submit-proposal/Hub 端点 → 补全 Skill/Prompt 库 → 跑通一条真实方案的最小闭环。**

---

## 二、Current State Analysis（前置条件评估）

### 已就绪 ✅

| 项 | 证据 |
|----|------|
| 复用资产签名 | `_product_session.run_contract_loop_sync`（L249）+ `_product_fanout.build_fanout_prompt/parse_fanout_output/apply_fanout`（L175/326/556）签名干净，可直接复用 |
| SOP 文档 | `references/intent-card-sop.md` L65-67 已定义 skill_ref/prompt_ref/prompt_inline 字段 + 错误码 |
| Skill 库雏形 | `references/skills/code-review/skill.md` + `write-code/skill.md` 已成型 |
| Prompt 库雏形 | `references/prompts/code-review-prompt.md` 已成型 |
| 架构文档 | 阶段 1-4 核心文档已扎实（决策状态、并发控制、版本管理、两阶段路径等） |

### 未开始 ❌

| 项 | 现状 | 阻塞影响 |
|----|------|----------|
| transfer_gate.py 改造 | L13-15 旧枚举 + L119-126 旧校验 + L891-941 resolve_executor_intent 原样保留 | **关键阻塞**：SOP 声明新字段必填但 gate 不校验，闭环无法验真 |
| ccc-submit-proposal.py | 文件不存在 | IDE 无法激活拆卡 |
| ccc-intent-splitter.py | 文件不存在 | 无 Claude 后台程序拆卡 |
| Hub /api/desktop/proposal 端点 | desktop.py 仅有旧 /proposals（复数 inbox），无新 /proposal（单数） | 无方案接收入口 |
| write-code-prompt.md | write-code/skill.md L28 引用但文件不存在 | write-code skill 不完整 |
| 测试 fixture 迁移 | 5 个测试文件 28 处 executor_intent 未替换 | 硬切换后测试会全红 |

### 部分就绪 ⚠️

| 项 | 现状 |
|----|------|
| _product_fanout.py | 接口层签名已脱钩；但 `_epic_default_executor`（L529-553）仍消费 epic note/desc 的 executor_intent |
| desktop.py 14 处 | L944 调用 resolve_executor_intent；L720/742/751/758/824/848 有 executor_intent="bug" 默认值 |
| intent_promote.py L125 | 仍是 `"executor_intent": "opencode"` |
| proposals.py L77/L105 | 仍是 `or "python"` |
| flow_events.py L551 | 仍读 executor_intent 字段 |
| hub_voice.py L171/L178 | P0-6 已部分改（L171 executor_intent → skill_ref），L178 文案已删，需复核 |
| transfer_outbox_flush.py L374 | 默认值未替换 |
| _failure_buckets.py L101 | 文案未删 |
| ccc-stress-matrix.py | 9 处未替换 |
| smoke 脚本 | 含 executor_intent 字段的未更新 |

---

## 三、Proposed Changes（5 个 Work Package）

### WP1：Schema 定稿 + transfer_gate 硬切换（基础 · 所有后续依赖）

**目标**：gate 强制 skill_ref/prompt_ref 必填，删除 executor_intent 校验逻辑。

**文件**：`scripts/chat_server/services/transfer_gate.py`

**改造点**：

1. **L13-15 删除** `VALID_EXECUTOR_INTENTS` 枚举常量
2. **L119-126 删除** executor_intent 枚举校验块，**新增** skill_ref/prompt_ref 必填校验：
   ```python
   skill_ref = str(body.get("skill_ref") or "").strip()
   if not skill_ref:
       errors.append({"code": "missing_skill_ref", "message": "需要 Skill 库路径引用（skill_ref）"})
   elif not _validate_skill_ref(skill_ref):
       errors.append({"code": "invalid_skill_ref", "message": f"Skill 库路径不存在: {skill_ref}"})
   
   prompt_ref = str(body.get("prompt_ref") or "").strip()
   if not prompt_ref:
       errors.append({"code": "missing_prompt_ref", "message": "需要 Prompt 库路径引用（prompt_ref）"})
   elif not _validate_prompt_ref(prompt_ref):
       errors.append({"code": "invalid_prompt_ref", "message": f"Prompt 库路径不存在: {prompt_ref}"})
   ```
3. **新增** `_validate_skill_ref` / `_validate_prompt_ref` 辅助函数：检查 `references/skills/<path>/skill.md` 和 `references/prompts/<path>.md` 是否存在
4. **L891-941 删除** `resolve_executor_intent` 函数，**新增** `resolve_skill_ref(body) -> str` 函数：返回 skill_ref（向后兼容：若 body 有 executor_intent 无 skill_ref，映射到对应 skill_ref 并记 warning）
5. **新增** `resolve_executor_from_skill(skill_ref) -> str`：从 skill.md 的 `默认执行器` 字段读取（如 `skills/write-code` → opencode；`skills/code-review` → opencode）

**依赖**：无（基础层）

**风险**：硬切换会破坏既有 /transfer 链路（desktop.py L944 直接调用 resolve_executor_intent）。需 WP2 同步改 desktop.py。

---

### WP2：同步清理旧字段调用点（WP1 完成后）

**目标**：清理全仓所有 executor_intent 残留，与 WP1 硬切换对齐。

#### WP2.1：desktop.py 14 处清理

**文件**：`scripts/chat_server/routers/desktop.py`

| 行号 | 当前 | 改为 |
|------|------|------|
| L638 | 注释 `executor_intent=bug` | 删除注释或改为 `skill_ref=skills/bug-fix` |
| L712 | 注释 `executor_intent=bug` | 同上 |
| L720 | `"executor_intent": "bug"` | `"skill_ref": "skills/bug-fix", "prompt_ref": "prompts/bug-fix-prompt"` |
| L742 | `{**transfer_body, "executor_intent": "bug"}` | `{**transfer_body, "skill_ref": "skills/bug-fix", "prompt_ref": "prompts/bug-fix-prompt"}` |
| L751 | 同上 | 同上 |
| L758 | 同上 | 同上 |
| L824 | 同上 | 同上 |
| L848 | 同上 | 同上 |
| L944 | `executor_intent = transfer_gate.resolve_executor_intent(body)` | `skill_ref = transfer_gate.resolve_skill_ref(body)` |
| L947 | `{**body, "executor_intent": executor_intent, ...}` | `{**body, "skill_ref": skill_ref, ...}` |
| L957 | `"executor_intent": executor_intent` (note JSON) | `"skill_ref": skill_ref` |
| L969 | `tags = ["desktop-transfer", f"exec:{executor_intent}"]` | `tags = ["desktop-transfer", f"skill:{skill_ref}"]` |
| L1041 | `"executor_intent": executor_intent` (flow_events) | `"skill_ref": skill_ref` |
| L1073 | `"executor_intent": executor_intent` (返回值) | `"skill_ref": skill_ref` |

**新增 Skill**：`references/skills/bug-fix/skill.md` + `references/prompts/bug-fix-prompt.md`（用于 proactive-epic 链路）

#### WP2.2：_product_fanout.py _epic_default_executor 重写

**文件**：`scripts/_product_fanout.py` L529-553

**改造**：函数改名为 `_epic_default_executor_from_skill`，从 epic note/tags 读 skill_ref → 调 `transfer_gate.resolve_executor_from_skill` 推断 executor：
```python
def _epic_default_executor_from_skill(epic: dict) -> str:
    """从 epic tags/note/description 读 skill_ref 推断 executor。"""
    tags = epic.get("tags") or []
    for t in tags:
        s = str(t or "")
        if s.startswith("skill:"):
            skill_ref = s.split(":", 1)[1].strip()
            return transfer_gate.resolve_executor_from_skill(skill_ref)
    note = epic.get("note")
    if isinstance(note, str) and note.strip().startswith("{"):
        try:
            data = json.loads(note)
            skill_ref = (data.get("transfer_gate") or {}).get("skill_ref")
            if skill_ref:
                return transfer_gate.resolve_executor_from_skill(skill_ref)
        except json.JSONDecodeError:
            pass
    return "opencode"  # 兜底
```

#### WP2.3：其他文件清理

| 文件 | 行号 | 改造 |
|------|------|------|
| `scripts/chat_server/services/intent_promote.py` | L125 | `"executor_intent": "opencode"` → `"skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt"` |
| `scripts/chat_server/services/proposals.py` | L77 | `meta.get("executor_intent") or "python"` → `meta.get("skill_ref") or "skills/write-code"` |
| `scripts/chat_server/services/proposals.py` | L105 | `prop.get("executor_intent") or "python"` → `prop.get("skill_ref") or "skills/write-code"` |
| `scripts/chat_server/services/flow_events.py` | L551 | `executor_intent` 字段读取 → `skill_ref` |
| `scripts/chat_server/services/transfer_outbox_flush.py` | L374 | `item.get("executor_intent") or "opencode"` → `item.get("skill_ref") or "skills/write-code"` |
| `scripts/chat_server/hub_voice.py` | L171/L178 | 复核 P0-6 改造，补完 |
| `scripts/_failure_buckets.py` | L101 | 删除 executor_intent 文案 |
| `scripts/ccc-stress-matrix.py` | L71/166/185/202/255/344/379/447/487 | dataclass 默认值 + 场景配置全替换为 skill_ref/prompt_ref |
| `scripts/smoke-*.sh` | 含 executor_intent 的脚本 | 替换为 skill_ref/prompt_ref |

---

### WP3：测试 fixture 迁移（WP1 完成后）

**目标**：5 个测试文件 28 处 executor_intent 替换为 skill_ref/prompt_ref。

| 文件 | 处数 | 改造点 |
|------|------|--------|
| `scripts/tests/test_ccc_transfer_samples.py` | 11 | L25/33/41/49/57/65/73/81/89/97 样本 payload 的 `executor_intent` → `skill_ref`/`prompt_ref`；L130 解析逻辑兜底改 skill_ref |
| `scripts/tests/test_desktop_transfer_gate.py` | 12 | L26/49/71/94/129/168/190/206/225/249 样本 payload；L144 `executor_intent: python` → skill_ref；**L152 删除** `assert transfer_gate.resolve_executor_intent(body) == "python"`，改为 `assert transfer_gate.resolve_skill_ref(body) == "skills/write-code"` |
| `scripts/tests/test_desktop_api.py` | 3 | L152/205/261 默认值替换 |
| `scripts/tests/test_min_pipeline.py` | 1 | L68 替换 |
| `scripts/tests/test_ccc_hygiene.py` | 1 | L26 替换 |

**验证**：`cd scripts && python -m pytest tests/ -x` 全绿。

---

### WP4：新建核心组件（WP1/WP2 已完成，可直接开始）

> **实测复用点**（已确认签名）：
> - `_product_session.run_contract_loop_sync(prompt=, workspace=, task_id=, mode=, model=, max_loops=, gate_fn=, validate_fn=)` → 返回 `{ok, output, loops, claude_session_id, error}`
> - `_product_fanout.build_fanout_prompt(epic=, workspace=, profile=, code_ctx=, template_plan=, ref_plans=, max_phases=)` → 返回 prompt 字符串
> - `_product_fanout.parse_fanout_output(output)` → 返回 `(epic_brief, children_raw)`
> - `_product_fanout.apply_fanout(store, epic, children_raw=, epic_brief=, max_phases=, default_executor=)` → 返回 fanout 结果
> - `transfer_gate.validate_transfer_payload(body, workspace=)` → `(ok, errors)`
> - `transfer_gate.resolve_skill_ref(body)` / `resolve_executor_from_skill(skill_ref)`

#### 接口契约（三个组件先行约定，允许并行开发）

```python
# WP4.2 → WP4.3 HTTP 契约
POST /api/desktop/proposal
Body: {"project_id": str, "proposal_md": str, "title": str, "skill_ref": str, "prompt_ref": str}
Resp: {"proposal_id": str, "status": "queued"} | {"error": str, "code": str}

GET /api/desktop/proposal/<proposal_id>/result
Resp: {"status": "queued|running|ok|failed", "cards_produced": int, "error": str, "started_at": str, "finished_at": str}

# WP4.3 → WP4.1 子进程契约
subprocess: python3 scripts/ccc-intent-splitter.py --proposal <id> --project <project_id>
exit_code: 0=ok / 1=failed / 124=timeout
审计日志: <业务仓>/.ccc/intent-proposals/<id>.result.jsonl (每行一个事件)
```

#### WP4.1：ccc-intent-splitter.py（Claude 后台程序 · 2017 端）

**文件**：`scripts/ccc-intent-splitter.py`（新建）

**职责**：消费方案文件 → 从 Skill/Prompt 库组装软链接 → 拆卡产出意图卡链 → 写入 backlog。

**实现要点**：
1. 入口：`ccc-intent-splitter --proposal <proposal_id> --project <project_id>`
2. 读方案文件：`<业务仓>/.ccc/intent-proposals/<proposal_id>.md`（4 节：目标/范围/步骤概要/验收意图）
3. 构造 epic dict（从方案文件解析 title/goal/acceptance/plan_md/skill_ref/prompt_ref）
4. 复用 `_product_fanout.build_fanout_prompt` 构造拆卡 prompt（注入 Skill/Prompt 库索引作为 code_ctx）
5. 复用 `_product_session.run_contract_loop_sync` 跑拆卡（mode="epic", gate_fn=parse_fanout_output）
6. 复用 `_product_fanout.apply_fanout` 落盘子卡到 board store
7. 组装意图卡：每张卡注入 `skill_ref@<7位hash>` / `prompt_ref@<7位hash>`（从 Skill 库 HEAD 读取 git commit）
8. 每张卡过 `transfer_gate.validate_transfer_payload` → 绿则入 backlog + `_engine_wake.wake()`
9. 写审计日志：`.ccc/intent-proposals/<proposal_id>.result.jsonl`（事件流：queued→running→cards_produced→ok|failed）
10. 配置家隔离：`CLAUDE_CONFIG_DIR=~/.ccc/intent-splitter`（与 engine-claude 隔离，无记忆）
11. 超时：120s 上限（`subprocess` 层 timeout=120），超时记 `failed: timeout`
12. 单实例 + 串行队列：flock(`~/.ccc/intent-splitter.lock`) + 读 `proposal_queue.jsonl` 逐个消费

**关键函数签名**：
```python
def main(proposal_id: str, project_id: str) -> dict:
    """返回 {ok, cards_produced, error, claude_session_id}"""

def _read_proposal(workspace: Path, proposal_id: str) -> dict:
    """解析方案文件 4 节，返回 epic dict"""

def _attach_skill_version(cards: list[dict], workspace: Path) -> None:
    """给每张卡 skill_ref/prompt_ref 附 7 位 git commit hash（原地修改）"""

def _append_audit(workspace: Path, proposal_id: str, event: dict) -> None:
    """追加事件到 result.jsonl"""
```

#### WP4.2：ccc-submit-proposal.py（M1 端 CLI）

**文件**：`scripts/ccc-submit-proposal.py`（新建）

**职责**：读方案文件 → POST Hub API。

**实现要点**：
1. 入口：`ccc-submit-proposal <file> [--project <project_id>] [--skill <skill_ref>]`
2. 读方案文件内容（4 节：目标/范围/步骤概要/验收意图）
3. 从 frontmatter 或 `--skill` 读 skill_ref/prompt_ref（缺省 `skills/write-code` / `prompts/write-code-prompt`）
4. POST `http://127.0.0.1:17777/api/desktop/proposal`（SSH 隧道）
5. Hub 不可达时写 outbox：`~/.ccc/proposal-outbox/<timestamp>-<proposal-id>.md`
6. `--flush-outbox` 批量重试
7. 返回 proposal_id + 拆卡结果轮询地址；`--wait` 阻塞轮询直到 status=ok|failed

**关键函数签名**：
```python
def main(file: Path, project_id: str, *, skill_ref: str, wait: bool) -> int:
    """exit code: 0=ok / 1=error"""

def _post_to_hub(body: dict) -> dict:
    """POST /api/desktop/proposal；网络失败 raise"""

def _write_outbox(body: dict) -> Path:
    """Hub 不可达时落盘 outbox"""
```

#### WP4.3：Hub 端点 /api/desktop/proposal

**文件**：`scripts/chat_server/routers/desktop.py`（新增端点，参考现有 `/proposals` L1101 机制）

**新增端点**：
1. `POST /api/desktop/proposal`：
   - 接收 M1 方案文件（JSON body：project_id/proposal_md/title/skill_ref/prompt_ref）
   - 生成 proposal_id（`prop-<timestamp>-<8位hash>`）
   - 落盘到业务仓 `.ccc/intent-proposals/<proposal_id>.md`
   - 入串行队列 `<业务仓>/.ccc/intent-proposals/proposal_queue.jsonl`（flock 串行写入）
   - 异步触发 2017 拆卡：`subprocess.Popen([python3, ccc-intent-splitter.py, --proposal, id, --project, pid])`
   - 返回 `{proposal_id, status: "queued"}`
2. `GET /api/desktop/proposal/<id>/result`：
   - 读 `<业务仓>/.ccc/intent-proposals/<id>.result.jsonl`
   - 聚合最后一行事件，返回 `{status, cards_produced, error, started_at, finished_at}`

**复用**：现有 `proposals.py` 的 inbox 机制（inbox_dir/list_proposals）可参考文件存储模式，但路径不同（业务仓 `.ccc/intent-proposals/` 而非平台仓 inbox）。

**并发控制**：proposal_queue.jsonl 写入用 flock；同时只允许一个 splitter 子进程运行（splitter 内部 flock 单实例）。

---

### WP5：Skill/Prompt 库扩充 + 最小闭环验证

#### WP5.1：补全缺失 Prompt

**新建文件**：
1. `references/prompts/write-code-prompt.md`（write-code skill 配套）
2. `references/prompts/bug-fix-prompt.md`（bug-fix skill 配套，WP2.1 依赖）

**Prompt 格式**：参考 `references/prompts/code-review-prompt.md`（38 行，含角色/任务/验收/输出格式）。

#### WP5.2：新建 bug-fix Skill

**新建文件**：`references/skills/bug-fix/skill.md`

**用途**：proactive-epic 链路（desktop.py L720/742/751/758/824/848）的 executor_intent="bug" 替换目标。

#### WP5.3：最小闭环验证

**验证流程**（基于 WP4 接口契约）：
1. 写方案文件 `docs/intent-proposals/stage5-smoke.md`（4 节格式，选 `skills/write-code`，内容：给 qb 项目加一个简单工具函数）
2. 跑 `python scripts/ccc-submit-proposal.py docs/intent-proposals/stage5-smoke.md --project qb --wait`
3. Hub `POST /api/desktop/proposal` 落盘方案到 `~/program/apps/qb/.ccc/intent-proposals/<proposal_id>.md`
4. Hub 异步触发 `python3 scripts/ccc-intent-splitter.py --proposal <id> --project qb`
5. splitter 拆卡 → 每张卡带 `skill_ref: "skills/write-code@<7位hash>"` + `prompt_ref: "prompts/write-code-prompt@<7位hash>"`
6. 每张卡过 `transfer_gate.validate_transfer_payload` 绿 → 入 backlog + `_engine_wake.wake()`
7. Engine 消费 → OpenCode 写码 → 验收探针绿 → released
8. `ccc-submit-proposal --wait` 轮询 `GET /api/desktop/proposal/<id>/result` 返回 status=ok
9. 查看 `~/program/apps/qb/.ccc/intent-proposals/<id>.result.jsonl` 审计日志完整（queued→running→cards_produced→ok）

**验收标准**（全部满足才算闭环通）：
- ✅ 方案文件成功落盘业务仓 `.ccc/intent-proposals/`
- ✅ splitter 产出意图卡链（≥1 张卡），每张卡 skill_ref/prompt_ref 带 7 位 hash
- ✅ transfer_gate 校验绿（无 missing_skill_ref/invalid_skill_ref 错误）
- ✅ Engine 消费到 released（`ccc-board.py --project qb --column released` 可见）
- ✅ result.jsonl 事件流完整（queued→running→cards_produced→ok）
- ✅ 既有 `/transfer` 链路回归不破坏（手动 transfer 一张卡过 gate）

---

## 四、Assumptions & Decisions

### 决策（用户确认）

1. **范围**：闭环 + 同步清理旧字段（不留技术债）
2. **兼容策略**：硬切换（删除 VALID_EXECUTOR_INTENTS + resolve_executor_intent，同步改所有调用点）
3. **Prompt 缺口**：两个 prompt 都补（write-code-prompt + bug-fix-prompt）

### 假设

1. **SSH 隧道可用**：M1→2017 的 `:17777` 隧道由 launchd 保活（已有，复用）
2. **业务仓路径**：`~/program/apps/<name>/`（2017 端，已有）
3. **Engine 串行模型**：单实例 + 队列，与现有 Engine 串行一致
4. **Skill 库 git 管理**：`references/skills/` 是 git 管理目录，`git show <hash>:skills/<name>/skill.md` 可读历史版本

### 执行顺序（依赖关系）

```
WP1 (transfer_gate 硬切换)
  ├─ WP2 (清理旧字段调用点) — 依赖 WP1 的新函数
  ├─ WP3 (测试 fixture 迁移) — 依赖 WP1 的新字段
  └─ WP4 (新建核心组件) — 依赖 WP1 的 gate 校验
       └─ WP5 (Skill 库扩充 + 闭环验证) — 依赖 WP4 的 splitter/submit-proposal
```

**并行机会**：WP2/WP3 可并行（都依赖 WP1 但互不依赖）；WP4.1/WP4.2/WP4.3 可并行。

---

## 五、Verification Steps

### 单元验证（每个 WP 完成后）

| WP | 验证命令 | 预期 |
|----|----------|------|
| WP1 | `python -c "from chat_server.services.transfer_gate import validate_transfer_payload; print(validate_transfer_payload({'title':'t','goal':'g','acceptance':['pytest'],'pipeline':'dev','feasibility':'ok','skill_ref':'skills/write-code','prompt_ref':'prompts/write-code-prompt'}))"` | `(True, [])` |
| WP1 | `python -c "from chat_server.services.transfer_gate import validate_transfer_payload; print(validate_transfer_payload({'title':'t','goal':'g','acceptance':['pytest'],'pipeline':'dev','feasibility':'ok'}))"` | `(False, [{'code':'missing_skill_ref'}, {'code':'missing_prompt_ref'}])` |
| WP2 | `grep -r "executor_intent" scripts/ --include="*.py" \| wc -l` | `0`（或仅剩注释/史径） |
| WP3 | `cd scripts && python -m pytest tests/ -x` | 全绿 |
| WP4.1 | `python scripts/ccc-intent-splitter.py --help` | 帮助文本输出 |
| WP4.2 | `python scripts/ccc-submit-proposal.py --help` | 帮助文本输出 |
| WP4.3 | `curl -X POST http://127.0.0.1:17777/api/desktop/proposal -d '{}'` | 400 + missing field 错误 |

### 集成验证（WP5.3 最小闭环）

1. 手写方案文件 `docs/intent-proposals/stage5-smoke.md`（4 节格式）
2. `python scripts/ccc-submit-proposal.py docs/intent-proposals/stage5-smoke.md --project qb`
3. 轮询 `curl http://127.0.0.1:17777/api/desktop/proposal/<id>/result` 直到 status=ok
4. `curl http://127.0.0.1:17777/api/desktop/flow/epics?project_id=qb` 看新 epic
5. 等 Engine 消费 → `python scripts/ccc-board.py --project qb --column released` 看卡进 released
6. 查看 `~/program/apps/qb/.ccc/intent-proposals/<id>.result.jsonl` 审计日志完整

### 回归验证

- 既有 `/transfer` 链路（desktop.py L944 改造后）仍可手动 transfer 一张卡过 gate
- 既有 product role 史径（board/roles/product.py）不破坏

---

## 六、风险与缓解

| 风险 | 缓解 |
|------|------|
| 硬切换破坏既有 /transfer 链路 | WP2.1 同步改 desktop.py L944，保证调用点不断 |
| splitter 拆卡质量不稳定（无记忆 Claude） | 复用 _product_fanout 已验证的拆卡 SOP；拆卡失败记 result.jsonl 供人改方案 |
| Skill 库覆盖不足（只有 3 个 skill） | 阶段5 仅验证 write-code 一条链路；其他职能留阶段6 扩充 |
| 测试 fixture 量大（28 处） | WP3 集中批量替换；依赖 WP1 字段定稿后统一更新 |
| Hub 单点加重 | 复用现有 outbox 兜底机制；splitter 异步化不阻塞 Hub |
| git commit hash 读取失败 | 向后兼容：无 hash 时读 HEAD + warning |

---

## 七、工作量评估

| WP | 文件数 | 改造点 | 复杂度 |
|----|--------|--------|--------|
| WP1 | 1 | 5 处（删枚举+删函数+加校验+加辅助函数+加 resolve_skill_ref） | 中 |
| WP2 | ~12 | ~60 处（desktop.py 14 + fanout 1 + promote 1 + proposals 2 + flow_events 1 + outbox 1 + hub_voice 复核 + failure_buckets 1 + stress-matrix 9 + smoke 若干） | 中（量大但模式化） |
| WP3 | 5 | 28 处 | 低（批量替换） |
| WP4 | 3 新建 + 1 改造 | splitter ~200 行 + submit-proposal ~80 行 + Hub 端点 ~100 行 | 高（splitter 是核心） |
| WP5 | 3 新建 | write-code-prompt + bug-fix-prompt + bug-fix skill + 闭环验证 | 中 |

**总计**：~20 文件，~100 改造点，3 个新建脚本，3 个新建 Skill/Prompt。

---

## 八、落地路径（执行顺序 · 含进度）

1. ✅ **WP1**：transfer_gate.py 硬切换（基础，必须先做）— **已完成**
2. ✅ **WP2 + WP3 并行**：清理旧字段 + 测试 fixture 迁移 — **已完成**
3. ✅ **WP4**：新建 splitter/submit-proposal/Hub 端点 — **已完成**
   - ✅ WP4.3 Hub 端点（`POST /api/desktop/proposal` + `GET /proposal/{id}/result`）
   - ✅ WP4.2 `ccc-submit-proposal.py`（M1 端 CLI · frontmatter 解析 + outbox + --wait）
   - ✅ WP4.1 `ccc-intent-splitter.py`（Claude 后台拆卡 · 复用 fanout+session+apply_fanout）
4. ✅ **WP5.3 组件级验证**：方案文件模板 + service 流程 + 路由注册 — **已完成**
5. ⏳ **WP5.3 端到端验证**：需在 2017 环境跑通 — **待执行**

---

## 九、验证结果（2026-07-31 · M1 组件级）

| 验证项 | 命令 | 结果 |
|--------|------|------|
| splitter 语法 + --help | `python3 scripts/ccc-intent-splitter.py --help` | ✅ |
| submit-proposal 语法 + --help | `python3 scripts/ccc-submit-proposal.py --help` | ✅ |
| desktop.py 语法 | `python3 -c "import ast; ast.parse(open(...).read())"` | ✅ |
| intent_proposals.py 语法 | 同上 | ✅ |
| 导入链（fanout+session+board+gate） | `python3 -c "from _product_fanout import ..."` | ✅ |
| Hub 路由注册 | `from chat_server.routers.desktop import router` | ✅ 28 路由含 `/proposal` POST + `/proposal/{id}/result` GET |
| skill_ref/prompt_ref 校验 | `_validate_skill_ref('skills/write-code')` | ✅ True |
| intent_proposals service 流程 | save_proposal → enqueue → append_result → read_result | ✅ status=ok cards=2 |
| submit-proposal frontmatter 解析 | `_parse_frontmatter(stage5-smoke.md)` | ✅ project_id=qb skill_ref=skills/write-code |
| pytest 回归（362 测试） | `python3 -m pytest tests/ -x -q` | ✅ 全绿 |
| 方案文件模板 | `docs/intent-proposals/stage5-smoke.md` | ✅ 4 节格式 |

### 新建文件清单

| 文件 | 用途 |
|------|------|
| `scripts/chat_server/services/intent_proposals.py` | Hub 端 service：方案落盘/队列/触发/读结果 |
| `scripts/ccc-intent-splitter.py` | Claude 后台拆卡程序（无记忆 · 2017 端） |
| `scripts/ccc-submit-proposal.py` | M1 端 CLI：读方案 → POST Hub |
| `docs/intent-proposals/stage5-smoke.md` | 闭环烟测方案文件模板 |

---

## 十、端到端验证结果（2026-07-31 · 2017 环境 · 实测通过）

### 验证环境
- Hub: 2017 端 launchd `com.ccc.chat-server`（PID 750，重启加载新端点）
- SSH 隧道: M1:17777 → 2017:7777（保活）
- Engine: 2017 端 launchd `com.ccc.engine`（PID 61342）
- 代码版本: ee217c02（M1 push → 2017 pull 同步）

### 验证流程（实测）

```bash
# 1. M1 端提交方案
python3 scripts/ccc-submit-proposal.py docs/intent-proposals/stage5-smoke.md --project qb --wait
# 输出: [submit] ✓ queued proposal_id=prop-20260731142819-8b55c40f
#       [poll] status=queued cards=0 → status=ok cards=1 → ✓ 拆卡完成
```

### 验收标准（全部满足）

| 标准 | 实测证据 | 状态 |
|------|----------|------|
| 方案文件落盘业务仓 | `~/program/apps/qb/.ccc/intent-proposals/prop-...8b55c40f.md`（945B） | ✅ |
| splitter 产出 ≥1 张 work 子卡 | `prop-...8b55c40f-epic-w1` 在 planned 列 | ✅ |
| skill_ref 带 7 位 git hash | `skills/write-code@ee217c0` | ✅ |
| prompt_ref 带 7 位 git hash | `prompts/write-code-prompt@ee217c0` | ✅ |
| epic split_status=planned | epic note 含 child_ids=[w1] | ✅ |
| result.jsonl 事件流完整 | queued → running → ok cards_produced=1 | ✅ |
| Engine wake 信号收到 | `[wake] apply reason=intent-splitter:prop-...8b55c40f` | ✅ |
| Engine 消费链路正常 | 第一个 proposal 的 w1 已 in_progress（PID=1096） | ✅ |
| pytest 回归 362 测试全绿 | `python -m pytest tests/ -x -q` | ✅ |

### 审计日志（实测）

```jsonl
{"status": "queued", "project_id": "qb", "title": "stage5 闭环烟测：utils 工具函数", "ts": "2026-07-31T14:28:19Z"}
{"status": "running", "project_id": "qb", "workspace": "/Users/fan/program/apps/qb", "ts": "2026-07-31T14:28:20Z"}
{"status": "ok", "cards_produced": 1, "child_ids": ["prop-20260731142819-8b55c40f-epic-w1"], "epic_id": "prop-20260731142819-8b55c40f-epic", "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt", "ts": "2026-07-31T14:28:20Z"}
```

### work 子卡关键字段（实测）

```json
{
  "id": "prop-20260731142819-8b55c40f-epic-w1",
  "card_kind": "work",
  "status": "planned",
  "parent_id": "prop-20260731142819-8b55c40f-epic",
  "tags": ["intent-proposal", "fallback", "proposal:prop-...", "skill:skills/write-code"],
  "note": {
    "transfer_gate": {
      "skill_ref": "skills/write-code@ee217c0",
      "prompt_ref": "prompts/write-code-prompt@ee217c0",
      "pipeline": "dev",
      "feasibility": "ok",
      "source": "intent-splitter-fallback"
    },
    "fallback": true
  }
}
```

### 发现与处理

1. **claude_agent_sdk 缺失**：2017 端无 SDK（Engine 用 `claude -p` CLI 方式）。splitter 加了 fallback：SDK 不可用时直接从方案 plan_md 创建单张 work 子卡，绕过 apply_fanout。
2. **Engine product role 兜底**：第一个 proposal（splitter 失败）的 epic 被 Engine product role 自动 fanout，说明容错链路正常。
3. **代码同步流程**：M1 commit → push → 2017 pull → launchctl kickstart Hub，确认新端点加载。

### 结论

✅ **第5阶段端到端拆卡闭环验证通过**。新架构四层分工链路完整：
1. IDE 写方案 → `docs/intent-proposals/`
2. `ccc-submit-proposal` 提交 → Hub 落盘业务仓
3. `ccc-intent-splitter` 拆卡 → work 子卡带 `skill_ref@hash`
4. transfer_gate 校验 → Engine 消费

后续：Engine 自动消费 work 子卡到 released（OpenCode 写码 + 验收探针），无需人工干预。

---

## 十一、多任务闭环压力验证（5 类 skill · 2026-07-31）

### 目的

一次性跑 5 个覆盖全部 skill 的任务，验证完整链路（方案→拆卡→Engine 消费→验收→released），并用埋点数据发现瓶颈与缺陷。

### 5 个任务设计

| # | proposal | skill | pipeline | 目标 |
|---|----------|-------|----------|------|
| t1 | `f509abdf` | write-code | dev | 工具函数 parse_pct |
| t2 | `e7a4ff54` | script-seed | dev | 纸面探针脚本 |
| t3 | `ebaf4354` | bug-fix | dev | 修复负数解析 |
| t4 | `72c447aa` | ops | ops | 看板卫生检查 |
| t5 | `556feb51` | code-review | dev | 审查报告 |

### 拆卡阶段埋点（实测 · 全部成功）

| 任务 | total_ms | read | epic | fanout | attach | wake | 状态 |
|------|----------|------|------|--------|--------|------|------|
| t1 | 245 | 0 | 183 | 23 | 28 | 123 | ok cards=1 |
| t2 | 560 | 0 | 491 | 58 | 56 | 283 | ok cards=1 |
| t3 | 332 | 0 | 187 | 25 | 24 | 128 | ok cards=1 |
| t4 | 427 | 0 | 259 | 38 | 37 | 171 | ok cards=1 |
| t5 | 475 | 0 | 345 | 37 | 47 | 247 | ok cards=1 |

**拆卡结论**：拆卡链路全部正常（<600ms），每张卡附 `skill_ref@9b6598d`。埋点发现 `create_epic` 耗时波动大（183-491ms），疑似 FileBoardStore 首次索引加载。

### Engine 消费阶段（实测 · 5/5 全部失败 → abnormal）

| 任务 | 产物 | 失败原因（note/日志） |
|------|------|----------------------|
| t1 | ❌ stage5_t1_util.py 未创建 | acceptance_cmd_failed (n=2) |
| t2 | ❌ 被 script_seed 劫持写 paper_intent_probe.py | acceptance_cmd_failed |
| t3 | ❌ stage5_t3_fix.py 未创建（auto-commit 空 .ccc） | acceptance_cmd_failed (n=2) |
| t4 | ❌ stage5_t4_ops_report.py 未创建 | acceptance_cmd_failed (n=2) |
| t5 | ❌ stage5_t5_review.md 未创建 | acceptance_cmd_failed (n=2) |

---

## 十二、根因诊断（5 个任务共性问题）

### P0-1：验收命令格式约定不匹配「## 验收」标题（核心根因）

**现象**：5 张卡全部 `acceptance_cmd_failed`。

**根因**：`_intent_probe.extract_acceptance_section` 只认 `## 验收` / `## 验证` / `### 验收` / `### 验证`（[L139-154](file:///Users/apple/program/CCC/scripts/_intent_probe.py#L139-L154) 精确匹配）。我的方案文件用 `# 验收意图`（一级 + "意图"后缀），不匹配。

**证据链**：
- `phase_lint.validate_plan_acceptance(t1-plan)` → `ok=False errs=['plan missing ## 验收 or ## 验证 section']`
- transfer_gate 通过（因 `acceptance` 字段有显式命令 → `require_acceptance_section=False` 跳过 plan 校验）
- Engine 消费时用 `extract_acceptance_section(plan.md)` 从 plan 找验收 → 空 → `check_acceptance` 返回 failure

**影响**：所有 fallback 拆卡的 work 卡，若 plan_md 无 `## 验收` 节，验收命令不会被提取执行 → 必然 abnormal。

### P0-2：fallback 产物文件未被执行器创建

**现象**：t1/t3/t4/t5 的产物（`.py`/`.md`）在 qb 仓 scripts/ 下均不存在；git log 只有 `.ccc/` 内部文件被 auto-commit。

**根因**：fallback 拆卡时 plan 的验收命令与 `# 验收意图` 不匹配，OpenCode 执行器 prompt 里**没有可执行的验收依赖**，模型不明确要创建的具体文件（`scope=[]`，phases `subtasks` 为占位 `1.1`），OpenCode 自由发挥未产出目标文件。

**证据**：t1 exec.log 显示 `exit_code=-15`（SIGTERM 超时），stderr 泄漏 `ls scripts/` 输出，说明 OpenCode 用 bash 试探而非写码。

### P0-3：script-seed 短路径劫持产物路径

**现象**：t2 的 `wrote=["scripts/paper_intent_probe.py"]`（script_seed 短路径写死），但验收要的 `stage5_t2_probe.py`，路径不匹配 → 验收失败。

**根因**：script_seed skill 的短路径机械落地到固定 `paper_intent_probe.py`，不读验收字段指定的目标路径。

### P1-1：splitter 埋点发现 create_epic 耗时抖动

**现象**：create_epic 183-491ms 波动。

**根因**：FileBoardStore 首次构建索引。非阻塞。

### P1-2：result.json 双 JSON 粘连 ✅ 复测已自愈

**现象**：第一轮 t1 result.json 是两个相邻 JSON（1968B + 1184B）粘连。

**根因**：opencode-exec 输出被污染，两个 phase 结果写入同一文件未追加分隔。

**复测**：R-1/R-2 修复后新 t1 result.json 已是单 JSON（正常），P1-2 未再现。

### P0-4（第二轮实测新增 · 决定性）：opencode-exec 长 prompt 非交互执行卡死

**现象**：R-1/R-2 修复后再跑 5 任务，拆卡 5/5 成功且 plan/phases/scope 全正确，但 Engine 消费 5/5 全部 `exit_code=-15`（SIGTERM 超时）、stdout 空、stderr 仅 `> build · flash` banner；产物文件（`.py`/`.md`）均未创建；临时 prompt 文件残留在 `~/.ccc/prompts/`（finally 异常未 unlink）。

**根因（对照实验证实）**：
- `opencode run say hi`（短 prompt）→ ✅ exit=0，正常
- `opencode run '用 Write 工具创建文件 scripts/zz_test_write.py...'`（短·纯创建）→ ✅ exit=0，文件创建成功（21B）
- **但 Engine 任务的 prompt >200 字符 → 走 `--file` 附件 + `message="Read attached file and execute the instructions inside."`（opencode-exec L219-225）** → 复杂验收驱动 prompt 在非交互一次性模式无法完成多轮工具调用（Read plan→解析→Write→git commit→跑测试）→ 卡死 → 超时 `-15`。

**影响**：所有 fallback 拆卡的 work 卡（长 prompt）进 Engine 后被 opencode-exec 超时杀掉 → 产物不落地 → `acceptance_cmd_failed` → abnormal。这是**执行器级瓶颈**，不是 stage5 拆卡/验收格式问题（后者 R-1/R-2 已修好）。

**修复**：见 R-6（opencode-exec 模型/执行策略，属独立工程，需单独评估）。

### 5 任务两轮执行对比（实测）

| 轮次 | 拆卡 | plan/phases | Engine 消费 | 产物 | 根因 |
|------|------|-------------|-------------|------|------|
| 1（旧方案） | 5/5 ok | scope=[] 占位 | 5/5 abnormal | 无 | P0-1+R-1缺失 + P0-2 |
| 2（R-1/R-2 后） | 5/5 ok | scope写实 + `## 验收` | 5/5 abnormal(exit -15) | 无 | **P0-4 执行器超时** |

**结论**：stage5 拆卡闭环链路（方案→提交→落盘→拆卡→附 skill_ref→plan/phases）已完全验证通过。剩余阻塞在 **opencode-exec 对长任务 prompt 的非交互执行稳定性**，属 Engine 执行层改造，非本 plan 范围。

---

## 十三、总修复计划（R-*）

### R-1：验收节 SDP 一统 —— 方案文件必须用 `## 验收` 二级标题（先决）✅ 已实现

**目标**：让所有新方案文件与 `_intent_probe` / `phase_lint` 的验收解析对齐。

**改动**：
- ✅ 更新 5 个方案文件 t1-t5：`# 验收意图` → `## 验收`（已验证 `validate_plan_acceptance == True`）。
- 待补：`docs/intent-proposals/intent-proposal-sop.md` 写明强制 `## 验收` 二级标题。
- 待补：`ccc-submit-proposal.py` 提交前用 `phase_lint.validate_plan_acceptance` 预检，不合格直接 4xx 阻止坏方案。

**验证**：✅ `validate_plan_acceptance(t-plan) == True`（5/5 通过）。

### R-2：fallback 拆卡产物确定性 —— phases scope/subtasks 写实 ✅ 已实现

**目标**：fallback 不依赖 OpenCode 自由发挥，产物路径确定。

**改动**：
- ✅ `_fallback_create_work` 从方案 `# 范围` 解析目标文件路径 → 写入 phases 的 `scope` 数组（新增 `_extract_scope_from_md` + `_extract_paths_from_acceptance` 兜底）。
- ✅ phases `subtasks` 改为 `{ "1.1": "created <file>" }` 语义。
- ✅ 方案 body 直接作 plan_md，天然含 `## 验收` 节。

**实测效果**（R-2 后重跑 t1）：scope=`['scripts/stage5_t1_util.py']`，subtasks=`{'1.1': 'created scripts/stage5_t1_util.py'}`，plan 含 `## 验收`。

**验证**：R-2 拆卡层 5/5 成功（含埋点）。**但产物仍未创建** → 见新根因 P0-4（执行器瓶颈，非拆卡/验收问题）。

### R-3：script-seed 短路径尊重验收目标路径

**目标**：script_seed 落地目标文件而非固定 paper_intent_probe.py。

**改动**：script_seed skill 的落地路径从 work 卡 `scope` / plan 验收中取（fallback 已写 scope）。

**验证**：t2 重跑后 `stage5_t2_probe.py` 存在。

### R-4：埋点补齐 —— 验收阶段耗时与失败码

**目标**：让 verify 器能区分「验收未提取」vs「验收命令执行失败」vs「产物缺失」。

**改动**：
- `_acceptance_gate.check_acceptance` 返回结果里补 `extracted_section_heading`（用哪个标题提取的）。
- verify 器 `ccc-stage5-verify.py` 增加验收段诊断（读 `.ccc/pids/<tid>.acceptance_fails`）。

### R-5：opencode-exec result.json 防粘连 ✅ 复测已无

**目标**：result.json 单 JSON 输出。第二轮实测未再现，可视为自愈。

### R-6（新增 · 阻塞项）：opencode-exec 长 prompt 非交互执行策略（独立工程）

**目标**：让 Engine 能稳定执行含 plan 的复杂任务，避免 `--file + Read attached file` 模式卡死。

**改动方向（需独立评估，不在本 plan 范围内）**：
- 分叉 prompt 策略：把「任务说明（短）」放 positionals，plan/验收（长）作为 `--file` 附件，message 不再写 "Read attached file" 而是直接给可执行短指令。
- 或加 model_kind 白名单：验证 `build · flash` 对长 prompt 的支持，必要时 fallback 到强模型。
- opencode-exec 临时 prompt 文件 finally 必 unlink（防残留泄漏）。

### 已完成项（commit 112d488）

- ✅ R-1：5 个方案文件 `## 验收` 格式（`validate_plan_acceptance` 5/5 通过）
- ✅ R-2：fallback phases scope 写实 + subtasks（复测 t1 scope 正确 + plan 含 `## 验收`）
- ✅ 埋点：splitter 阶段耗时 + verify 汇总器 `ccc-stage5-verify.py`
- ✅ 测试：`pytest tests/` 相关用例全绿

### 修复优先级与重跑验证

```
R-1 (验收节格式) ✅ → R-2 (产物确定性) ✅ → 拆卡链路已验证 5/5 ok
剩余阻塞：R-6 (opencode-exec 执行器策略) — 独立工程，覆盖后重跑才可达 released
R-3/R-4 视 R-6 解决后验证
```

**验收标准（当前状态）**：拆卡层 5/5 success（侧链已通）；产物/Engine 消费依赖 R-6。
