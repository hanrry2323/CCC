# 北星竖切（plan → 入队 → 静默质量 → 合入批准）

> **现行 · 2026-08-07** · 权威：[`../INDEX.md`](../INDEX.md) §0 北星双核心。  
> 本页是竖切入口，不是又一篇 Agent 心智补丁。

## 一句话

主 IDE 谈方案 → 确认 `ccc-plan` → `plan-to-cards` 入队 → Engine+机审静默 → phase2 默认自动 **审核→合入→部署**；老板保留否决/打回（可人工兜底触发 `approve-merge`）。

## 老板口令（只留两个）

| 口令 | 动作 |
|------|------|
| 确认方案 / 拆卡入队 | `scripts/plan-to-cards.sh <plan>` → 多卡一次 push |
| **合入批准** `[卡号…]` | `scripts/approve-merge.sh <id>`（可批处理 ready 队列；默认由 phase2 自动执行，此为人工兜底/否决通道） |

「验收看板」及旧同义句 = **合入批准** 的文档别名（见 [`accept-board-sop.md`](accept-board-sop.md)）。质量过不过看机审/门禁 exit code，不看口头流程。

## `ccc-plan` 形态

````markdown
```ccc-plan
title: 短标题
project: ccc
slices:
  - title: 切片一
    slug: slice-one
    acceptance:
      - "pytest server/tests/test_foo.py -q 绿"
    whitelist: ["server/foo.py"]
    executor: 执行会话
```
````

也可用同一字段的 JSON 对象（整块 `{...}`）。非法前缀 / 空验收点 → 脚本非 0。

## 命令

```bash
# 拆卡（方案确认后唯一出卡路径；禁止一张张聊着出；老板/外脑逐张拟卡指令=合法单卡通道）
scripts/plan-to-cards.sh docs/notes/my.plan.md
# 或 stdin：cat plan.md | scripts/plan-to-cards.sh -

# 进度真值（只认 2017）
curl -s http://192.168.3.116:7788/board/ready_for_merge

# 分支取证（禁 /tmp merge 考古）
scripts/card-evidence.sh ccc123

# 合入批准（ff-only → 关卡 → push）
scripts/approve-merge.sh ccc123
```

## 度量（竖切不过则砍 scope，不写 SOP）

| 指标 | 门槛 |
|------|------|
| 老板调度次数 | ≤2（确认方案 + 合入批准） |
| 因「流程不懂」找人 | 0 |
| 质量门红找人 | 允许（打回自动再跑） |

## 分支卫生（减分叉 · 少用 --close-only）

回写 push 后、合入前：在卡内分支定期 `git fetch origin && git rebase origin/main`（或 merge main），保持可 ff。  
`approve-merge` 遇分叉会提示 `--close-only`——那是兜底，不是常态。

## 冻结

见 [`../roadmap.md`](../roadmap.md)「冻结清单」。缺口挂账，禁止新增席位表/同义句/AGENTS 长禁令。
