# M2 — 编排仓与业务仓角色分离（v0.51.0）

> **对内里程碑**：CCC 升为编排底座；Engine 只消费业务仓；平台改动只改 CCC 一次全局生效。  
> 验收以本文件 DoD + doctor + Hub 拒投为准。

## 目标角色

| 谁 | 干什么 | 不干什么 |
|----|--------|----------|
| **你 + Cursor** | 开发/修复 **CCC 本体**；全局卫生计划 | 不替业务仓写业务功能（除非卫生计划明示） |
| **Hub** | 选**业务项目**对话→定稿→下达；运维观察窗 | 不把 CCC 核心开发投到 CCC backlog |
| **Engine** | 只消费 `role=app` / `engine=true` 登记仓 | **不**对 orch 跑 product/dev/review/test/kb |
| **业务仓** | 业务代码与项目级验收 | 不承载 CCC 平台补丁 |

## DoD

| # | 门槛 |
|---|------|
| D1 | CCC `role=orch`；`ccc-workspace-doctor` 显示 `engine=False` |
| D2 | Engine 日志跳过 CCC；对业务仓仍正常取卡 |
| D3 | Hub 对 CCC 下达 → 4xx / 前端拒绝 |
| D4 | Hub 默认项目 ≠ ccc（有业务仓时） |
| D5 | 空 registry / 仅 orch → Engine idle，不单跑 CCC |
| D6 | 文档 + CHANGELOG v0.51.0；测试覆盖 registry skip + Hub reject |

## 舰队计数

- **≤10** 指 **engine-eligible apps**
- **orch（CCC）额外 1**：仍登记、Hub 可见运维，不占 app 名额

## 操作

```bash
# 迁移现有 registry（CCC→orch）
python3 scripts/ccc-workspace-doctor.py migrate

# 卫生检查
python3 scripts/ccc-workspace-doctor.py
# 期望：CCC role=orch eng=False；apps ≤10；errors=0
```

全局卫生（Cursor，非 Engine）：见 [`../hygiene/PLAN-TEMPLATE.md`](../hygiene/PLAN-TEMPLATE.md)。  
Cursor 改平台规则：见 [`../cursor-ccc-core.md`](../cursor-ccc-core.md)。

## 明确不做

- 不技术锁死 Cursor 只能改 CCC（靠流程 + Hub 拒投 + 文档）
- 不删除 CCC `.ccc/board`（可空置；历史保留）
- 不恢复 invent / auto-inject

## 相关

- 发布说明：[`../releases/v0.51.0.md`](../releases/v0.51.0.md)
- 绑定规则：[`../workspace-binding.md`](../workspace-binding.md)
- 红线 **R-15**
