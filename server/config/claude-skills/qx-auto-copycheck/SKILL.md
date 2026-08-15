---
name: "qx-auto-copycheck"
description: "自动文案检查 v2：中英文文案/文档错别字/术语不一致/表述歧义/事实冲突（扩到 QuantHive/CCC 交接文档）。触发词「文案检查」「检查文案」「挑毛病」。"
---

# qx-auto-copycheck v2 — 自动文案检查

## 用途
对指定文档/界面文案做检查：错别字、术语不统一、表述歧义、与事实冲突（路径/端口/版本/机器归属）。

## 触发词（准确匹配）
「文案检查」「检查文案」「挑毛病」「措辞」

## 执行流程（硬）

### 1. 范围（v2 扩大，硬）
- **默认范围**：qx-map 文档（AGENTS.md / CLAUDE.md / cluster/ / command-post/ / ide/ / sync/）
- **v2 扩大**：QuantHive 当日交接文档（`/Users/apple/ZCodeProject/QuantHive/docs/notes/2026-08-0X-*`）
- **v2 扩大**：CCC 当日交接文档（`/Users/apple/program/CCC/docs/dispatch/` 当日文件）
- 或老板指定文件

### 2. 检查项
- 错别字 / 语病 / 标点
- 术语不统一（如「意图卡」vs「任务卡」）
- 表述歧义 / 可读性差（长句、被动、黑话）
- **与事实冲突（硬）**：
  - 路径/端口/版本/状态 → 对照 `cluster/path-authority.md` 与当日 `projects/manifest.md`
  - **机器归属（v2 新增）**：服务跑在哪台机器 → 必须对照 `cluster/path-authority.md`，禁止凭记忆

### 3. 每条带证据
文件 + 行 + 原文 + 建议改法

### 4. 回写
`command-post/auto-reviews/YYYY-MM-DD-copycheck.md`

## 输出模板
```
文案结论：X 处问题（🔴 事实冲突 n / 🟡 措辞 n / ⚪ 风格 n）
| # | 文件:行 | 原文 | 问题 | 建议 |
```

## 红线
- 🔴 事实冲突（路径/端口/状态/机器归属）最高优先，先报
- 机器归属必须对照 `cluster/path-authority.md`，不许凭记忆
- 只报不擅自改文档；改文档需老板确认
- 不评价文风偏好（除非老板要求）
