# Layer2 qb 开程（2026-07-28）

> **选轨**：Layer2 qb（业务意图样板）  
> **冻结本开程**：飞轮 T1–T4 自动 · invent · Ops UI 抛光  
> **平台前置**：Relay Flash 封印 + R1–R4 交付封印（`fcd7c0f`）  
> **域清单 SSOT**：[`2026-07-27-qb-domain-ship-gate.md`](./2026-07-27-qb-domain-ship-gate.md)  
> **脑包**：权威仓 `/Users/fan/program/apps/qb` · `CLAUDE.md` + `docs/DEV_PLAN_v1.1.md` + `.ccc/agent-mind/`

---

## 目标

在 qb 证明：少而硬的产品意图可走 LPSN **L → P → 人点 S**，且域 KPI 表有独立证据。  
**禁止**用 `released` / VERSION 冒充能盈利或可无人值守实盘。

---

## 禁止项

- 飞轮 T1–T2 自动 seed/probed 代码  
- invent / 卫生 epic 当主业  
- M1 业务第二树  
- 自动 `intent_stable`（S 必须人/Cursor 代人点）

---

## 首笔意图候选

| 候选 | 说明 |
|------|------|
| **主** | VIP-V5 / paper DRY_RUN 意图探针可重放（已有 `scripts/paper_intent_probe.py`） |
| **辅** | Layer2 开程戳记 epic：落 `docs/reports/layer2-open-lpsn-evidence.md` + 探针命令进验收 |

退出条件示例：

```bash
cd /Users/fan/program/apps/qb
DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper
# → exit 0 + docs/reports/paper-intent-probe-latest.md
```

---

## 勾选进度（本开程维护）

### A — CCC 侧

- [ ] A1 register / 无 M1 第二树 / engine=true@2017  
- [ ] A2 规划 SSOT = `docs/DEV_PLAN_v1.1.md`  
- [ ] A3 业务 epic 验收含可重放探针  
- [ ] A4 一笔 L → P → 人点 S  
- [ ] A5 空闲不投卫生主业（本开程遵守）

### B — qb 域

| # | 状态 | 证据指针 |
|---|------|----------|
| B1.1–B1.3 | 待填 | decided.goals / DEV_PLAN / 板面 |
| B2.1–B2.3 | 待填 | gatekeeper/risk 测 + 演练 |
| B3.1–B3.3 | 待填 | plist 保活 / 告警 / 纸面窗口 |
| B4.1–B4.3 | 待填 | 纸面门槛；实盘须人确认 |

---

## 证据附录（执行中追加）

（Phase 1+ 写入 epic id、commit、goal id、探针输出路径。）
