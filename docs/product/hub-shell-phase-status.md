# Hub-Shell 分阶段状态板

> 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) · Wave1–4  
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
| Phase7 v0.52.0 发布卫生 | green | VERSION + 双机对齐 + §9 | 349038e |
| Phase8 第二真实仓 | green | hp（xianyu 脏跳过）→ released | cb3bbf5 |
| Phase9 abnormal 止损可见 | green | 右栏/toast + snapshot failed | d7f98a0 |
| Phase10 xianyu 仓卫生 | green | 空板 + 陈旧 .ccc 清理（xianyu `625e317`） | b1f80d7 |
| Phase11 第三真实仓 xianyu | green | xianyu flow-smoke → released | 11053bf |
| Phase12 业务向意图 | green | qb README 双机路径（非 flow-smoke） | a1268e0 |
| Phase13 编排可靠性门禁 | green | reliability tier + hang/slot/orphan 探针（28 单元测）；终验修探活/board/sys；未 bump VERSION | a0c8b4c…5ce89de |
| v0.52.1 稳定性门禁 | green | gitignore 假绿 + transfer 空响应重试 + smoke gate；qb-biz-small PASS；`full` 本机绿（outage 因无本机 sidecar 跳过） | fd65284 |
