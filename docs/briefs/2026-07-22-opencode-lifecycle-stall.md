# Brief: OpenCode 生命周期卡死 — 综合方案（已落地）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-22-opencode-lifecycle-stall` |
| 状态 | **方案已定 / 实施中→已合平台**（P0 止损 + P1–P5 代码） |
| 权威 | [`../product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「OpenCode 生命周期」 |
| 计划指针 | Cursor plan `产线提效综合方案`（本地 `.cursor/plans/`，勿改计划文件本身） |
| 触发 | stress-matrix 10×2 + 清槽续跑（2026-07-22） |
| 负责人 | Cursor（平台） |

## 一句话

同仓 1 路 OpenCode 是设计；**真堵的是「任务结束了槽不放 / done 没收口 / reviewer 挂死堵 Engine / FAIL 半截 revert」**——已按 ROI 落地闸门修复，不加盲目并发。

## 已观测症状（A–F）→ 落地映射

| # | 症状 | 落地 |
|---|------|------|
| A | 幽灵同仓互斥 | P1：`workspace_blocks_new_opencode` + slot 释幽灵；终态 `_release_dev_slot` |
| B | 脏 result.json | P2：`result.json` 纯 JSON + `*.exec.log`；`_result_json` 防御解析 |
| C | 卫生卡进 opencode | P5：短路径硬失败，禁止 silent fallback；`dev_path` 埋点 |
| D | testing 堵 tick | P4：每 tick 限张/限时；**先 launch 再门禁**；单次门禁超时杀 pytest/claude |
| E | FAIL revert 脏仓 | P3：冲突必 `revert --abort`；skip + failures |
| F | 加并行无据 | P5：host 忙时 ≥30 点后再谈 `MAX_CONCURRENT`；默认 4 |

## 验收勾选（对照方案）

- [x] P0 止损：qb `revert --abort`；FAIL testing→planned；清槽；效率 post-p0 快照
- [x] P1 槽生命周期 + 单测
- [x] P2 产物契约 + 单测
- [x] P3 安全 revert + 单测
- [x] P4 门禁预算/交错
- [x] P5 短路径硬门 + path 埋点 + concurrency note
- [ ] 缩小版压测复跑（部署 2017 后）→ 终稿 `stress-*-efficiency.md`

## 非目标（仍成立）

- 取消同仓 1 路互斥
- 用加大 `MAX_CONCURRENT` 代替修闸门
- Agent 工作流画布当写码主控
