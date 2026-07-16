# CCC Skills — 阶段能力包索引

> **不是角色超市。** 这些是 Engine 按任务调度的**默认能力包**（Skill + Prompt）。  
> 用户不选角色；Hub 可选挂「软偏好」。叙事：[`docs/VISION.md`](../docs/VISION.md)

版本提示：以根目录 `VERSION` 为准。

## 机制

```text
任务 → 路由工具（Claude / OpenCode / …）→ 注入本阶段 Skill(+可选偏好) = 本次角色
```

## 默认阶段包

| 阶段 id | 目录 | 看板 | Engine 触发 | 职责 |
|---------|------|------|-------------|------|
| product | `ccc-product/` | backlog → planned | backlog 或已挂 plan 则跳过 | 拆任务、plan、SPEC |
| dev | `ccc-dev/` | → in_progress → testing | 有可执行 phase | 执行器写代码 |
| reviewer | `ccc-reviewer/` | testing → verified | testing 门禁 | 语义审查 + verdict |
| tester | `ccc-tester/` | testing → verified | testing 门禁 | pytest + 验收 |
| ops | `ccc-ops/` | 不动 board | 可选 | 健康检查 |
| kb | `ccc-kb/` | verified → released | verified 非空 | tag + changelog |
| regress | `ccc-regress/` | released → backlog | 定时/手动 | 回测 |

`complexity=small` 时可跳过 reviewer+tester（直通 kb）。

## 生产 vs 调试

**生产**：`com.ccc.engine` → `ccc-engine.py` 串行调用。

**调试**：

```bash
python3 scripts/ccc-board.py product --promote <task_id>
python3 scripts/ccc-board.py index
```

安装 Engine + Board：

```bash
bash scripts/install-ccc-roles.sh
```

Hub：`bash scripts/install-hub-plist.sh --start`

## 共同规范

- 红线 10：读 `.ccc/state.md` 接力  
- 红线 6：同任务内阶段职责不互串  
- reviewer/tester/ops/regress：**只读不写业务代码**（dev 除外）  

看板流转见根目录 `SKILL.md` 与 `docs/STRATEGY-MAP.md`。
