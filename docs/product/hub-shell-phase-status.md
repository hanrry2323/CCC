# Hub-Shell 分阶段状态板

> 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) · Wave1–3  
> 更新规则：每阶段验收绿后改状态并随该阶段 commit。

| 阶段 | 状态 | 说明 | Commit |
|------|------|------|--------|
| Phase1 P0 契约+demo 绿通 | green | 单测+smoke-hub-api-v1；epic 进 backlog | f81d451 |
| Phase2 浸泡 N=3 | green | smoke-ccc-demo-soak；orphan_delta=0 | 9c6f387 |
| Phase3 promote/skill | green | 反过拆 + complexity；oversplit 测绿 | 7d4400c |
| Phase4 inbox 采纳 | green | inbox/ + proposals API；smoke-inbox-adopt | 5b6eba4 |
| Phase5a demo→released | green | smoke-ccc-demo-released → done | c307d9d |
| Phase5b Hub 断线/outbox | green | smoke-hub-outage-outbox | 19739a1 |
| Phase6 真实业务仓 qb | green | qb flow-smoke → released | 6f4714b |
| Phase7 v0.52.0 发布卫生 | green | VERSION + 双机对齐 + §9 | 2eef10f |
| Phase8 第二真实仓 | pending | — | — |
| Phase9 abnormal 止损可见 | pending | — | — |
