# 方案文件 SOP（IDE → CCC 意图链入口）

> 谁用：任意 IDE 工具（会谈方案 + 会跑命令）
> 权威：docs/product/ccc-new-architecture-overview.md
> 配套：intent-card-sop.md · transfer-gate.md

## 一句话

人 + IDE 聊透方案 → IDE 写方案文件（M1 临时工作文件）→ 跑 `ccc-submit-proposal <file>` → Hub API → 业务仓 `.ccc/intent-proposals/`（权威落盘）→ Claude 后台程序拆卡 → gate → backlog → Engine 闭环。

## 两阶段路径（重要）

方案文件有**两个阶段**，命名相似但语义不同：

| 阶段 | 位置 | 用途 | 生命周期 |
|------|------|------|----------|
| **阶段一：IDE 临时工作文件** | M1 任意可访问位置（建议项目内 `docs/intent-proposals/`，但不强制） | IDE 写方案草稿 | 提交后即删（用完即弃） |
| **阶段二：Hub 权威落盘** | 业务仓（2017）`.ccc/intent-proposals/<proposal_id>.md` | Claude 后台程序读取 + 审计 | 永久保留（与 backlog 历史一致） |

**关键**：阶段一路径不强制（IDE 可写到任何位置），阶段二路径固定（Hub 权威落盘）。`ccc-submit-proposal` 命令负责把阶段一文件传到阶段二。

## 方案文件标准格式（4 节）

方案文件 = Markdown，必须包含以下 4 节：

### 1. 目标
做什么。一句话说清大目标。

### 2. 范围
涉及哪些文件/模块。列出关键路径。

### 3. 步骤概要
怎么做的思路。写清楚实现方向，但**不拆卡**（那是 Claude 后台程序的活）。

### 4. 验收意图
成功长什么样。写可重放的验收命令（pytest / python3 -c / DRY_RUN=…）。

## 文件命名

`<方案名>.md`，放项目内 `docs/intent-proposals/` 目录。

## 激活命令

```bash
ccc-submit-proposal <方案文件路径>
```

命令读方案文件 → POST Hub API → 落盘业务仓 `.ccc/intent-proposals/` → 激活 Claude 后台程序拆卡。

## 流程

1. 人 + IDE 聊方案（不拆卡）
2. IDE 按上述 4 节格式写方案文件
3. IDE 跑 `ccc-submit-proposal <file>`
4. Hub 落盘方案到业务仓 → 激活 Claude 后台程序
5. Claude 后台程序消费方案 → 从 Skill/Prompt 库组装软链接 → 产出意图卡链
6. transfer_gate 验证 → 绿：入 backlog → Engine 闭环
7. M1 通过 Hub API 查看拆卡结果（Phase A 需确认才入 backlog）

## 禁止

- 方案文件里直接写意图卡 JSON（那是 Claude 后台程序的活）
- 方案文件里写 `ccc-transfer` 块（那是后台程序产出的）
- 方案文件里指定 `executor_intent`（已废弃，改用 skill_ref/prompt_ref）
- 方案文件不写验收意图（gate 会拒）
