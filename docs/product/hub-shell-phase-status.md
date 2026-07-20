# Hub-Shell 分阶段状态板

> 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) · 计划 `hub-shell-phases`  
> 更新规则：每阶段验收绿后改状态并随该阶段 commit。

| 阶段 | 状态 | 说明 | Commit |
|------|------|------|--------|
| Phase1 P0 契约+demo 绿通 | green | 单测+smoke-hub-api-v1；epic 进 backlog，product 异步启动 | f81d451 |
| Phase2 浸泡 N=3 | green | smoke-ccc-demo-soak N=3；orphan_delta=0；hang 测绿 | （本提交） |
| Phase3 promote/skill | green | product skill 反过拆；fanout prompt 含 complexity；oversplit 测绿 | （本提交） |
| Phase4 inbox 采纳 | green | inbox/ + proposals API + Ops 采纳入口；smoke-inbox-adopt | 5b6eba4 |
| Phase5a demo→released | green | smoke-ccc-demo-released；无人值守至 user_stage=done | c307d9d |
| Phase5b Hub 断线/outbox | green | smoke-hub-outage-outbox；sidecar 仍活；outbox flush | 19739a1 |
| Phase6 真实业务仓 | green | qb `phase6-qb-1784559818` → released；见 phase6-qb.md | （本提交） |
