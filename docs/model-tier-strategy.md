# 三层模型分级开发策略

> 2026-07-12 定稿。Cheap Draft, Premium Polish。
> **一句话**：便宜模型搭骨架，高级模型做精修。

---

## 核心理念

```
你 (方向) → 我 (架构+拆解) → CCC 自动化 (DeepSeek/讯飞写代码)
         ↘ Cursor Pro (Claude Sonnet 精修)
```

不过度依赖单一模型，不浪费任何一层的能力。

---

## 三层架构

| 层级 | 模型 | 月费 | 用途 | 调用方式 |
|------|------|------|------|---------|
| **L1 架构** | MiniMax-M3（当前 flash 路由） | ¥119 | 方案讨论、任务拆解、上下文准备、结果 Review | 主会话 |
| **L2 执行** | 讯飞 astron-code / DeepSeek-v4-flash | ¥20 | 按 spec 写代码、日常搭建、骨架生成 | CCC 自动化 (dev_role → opencode) |
| **L3 精修** | Claude Sonnet (Cursor Pro) | ¥140 | 收官重构、质量冲刺、跨文件一致性 | Cursor 终端 Claude Code |
| **免费备援** | 智谱 GLM-4.7-Flash | ¥0 | CCC 自动化扩容 | 同一套 proxy 路由 |

**总预算：~¥279/月**

---

## 工作流

### 日常开发（L1 + L2）

```
1. 我（主会话）与用户讨论方案 → 出架构定案
2. 我拆分为精确 task → CCC task 格式
3. 投递到 CCC 自动化看板
4. CCC Engine 调度 dev_role → opencode → L2 模型（讯飞/DeepSeek）按 spec 写代码
5. 验收通过 → 产出版本
```

### 质量冲刺（L3）

```
1. 项目到达 70-80% 完成度
2. 我出一份 "收官冲刺任务清单"——精确到每个任务需要几次 Cursor 调用
3. 用户在 Cursor 中打开 Claude Code 终端
4. 我提供精确的执行上下文 + 指令
5. 用户粘贴到 Cursor Claude Code 执行（1-3 条消息/任务）
6. 项目从 80% → 95%+
```

**关键**：我在主会话做全部脑力劳动（拆问题、整理上下文、写精确指令），用户到 Cursor 只做"执行"这一步。每条 Cursor 消息的产出最大化。

---

## Cursor Pro 配额管理（500 次/月）

**每次调用的典型场景：**

| 场景 | 预估调用次数 |
|------|-------------|
| 跨文件重构（一处） | 3-8 |
| 修复边界情况（一处） | 1-3 |
| 补测试用例（一个模块） | 2-5 |
| 代码审查（整个项目） | 5-10 |
| 文档/整理（一次） | 2-5 |

**收官冲刺总量预估：95-160 次**。500 次月度配额充足。

---

## 为什么这是最优解

- **L2 用国产模型做 bulk work**——¥20 不限量，性价比极高
- **L3 用高级模型做 spike work**——¥140 包月 500 次，不用按 token 提心吊胆
- **我（L1）做架构和拆解**——固定成本 ¥119，一个会话处理多个任务
- **免费备援已有**——智谱 GLM-4.7-Flash 在 upstreams.json 中已配置，无额外成本

---

## 购买时机

1. 当前：L1 + L2 运行中，继续推 CCC 到 70-80%
2. 到达里程碑：我出收官清单，确认总调用在 500 次以内
3. 购买 Cursor Pro（¥140/月）
4. 集中一个月执行收官冲刺
5. 项目达到 95%+ 完成度

---

## 相关链接

- [上游配置](/Users/apple/program/ai-loop-router/upstreams.json)
- [proxy 入口](/Users/apple/program/ai-loop-router/proxy.mjs)
- [CCC 项目总纲](../CLAUDE.md)
- [CCC 工程红线](/Users/apple/program/CCC/references/red-lines.md)
