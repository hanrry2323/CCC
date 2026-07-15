# CCC Skills 索引 (v0.31.0)

7 角色看板自动化系统，由 **CCC Engine 串行驱动**（v0.20.1 起取消 7 plist 定时轮询）。

启动必读：`STARTUP-BRIEF.md` → 按需读各角色 `SKILL.md`。

## 7 角色

| 角色 | 技能目录 | 看板列 | Engine 触发 | 职责 |
|------|---------|--------|-------------|------|
| product | `skills/ccc-product/SKILL.md` | backlog → planned | backlog 非空自动拆分（v0.28 F-1）或 `--promote` | 拆任务、写 plan、SPEC 门禁、推断 complexity |
| dev | `skills/ccc-dev/SKILL.md` | planned → in_progress → testing | 有 task 即串行 | 调 opencode 写代码、phase 推进 |
| reviewer | `skills/ccc-reviewer/SKILL.md` | testing → verified | dev 完成后立即 | LLM 语义审查 + plan 验收清单；small 跳过 |
| tester | `skills/ccc-tester/SKILL.md` | testing → verified | dev 完成后立即 | pytest + plan 逐条验收；small 跳过 |
| ops | `skills/ccc-ops/SKILL.md` | 不动 board | Engine 空闲时 | 健康检查 + 告警 |
| kb | `skills/ccc-kb/SKILL.md` | verified → released | reviewer+tester 通过后 | git tag + push + changelog |
| regress | `skills/ccc-regress/SKILL.md` | released → backlog(回归 bug) | 23:30 定时或 Engine 空闲 | 每日回测 + 回归建 bug |

**复杂度分流（v0.28.1）**：task `complexity=small` 时 reviewer+tester 跳过，直通 kb。

## 使用方式

**生产环境**：`com.ccc.engine` launchd → `scripts/ccc-engine.py` 主循环串行调各角色函数。

**调试 / 手动**：
```bash
python3 scripts/ccc-board.py product --promote <task_id>
python3 scripts/ccc-board.py dev
python3 scripts/ccc-board.py reviewer
# … 其他角色同理
```

`scripts/roles/<role>.sh` 仍可用于单独注入 skill 环境变量（`CCC_ROLE` + `CCC_ROLE_SKILL`），但不再由 7 个 launchd plist 定时触发。

安装 Engine + board-server：
```bash
bash scripts/install-ccc-roles.sh          # 首次
bash scripts/install-ccc-roles.sh --upgrade  # 从旧 7 plist 迁移
```

## 共同规范

所有 skill 遵守：
- **红线 10**：读 `.ccc/state.md` 接力，不依赖会话级记忆
- **AGENTS.md 沉淀**：只写建议，不绕过人类审批
- **SPEC 门禁**（product 特有，但所有人应意识）
- **只读不写**（dev 除外；reviewer/tester/ops/regress 严格只读）

## 看板流转

```
backlog → planned → in_progress → testing → verified → released
                                                              ↓ (regress)
                                                         backlog(回归 bug)
```

详细见根目录 `SKILL.md` 与 `docs/STRATEGY-MAP.md`。
