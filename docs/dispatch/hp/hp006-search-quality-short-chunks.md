# 任务卡 hp006 · 搜索质量：短chunk清理与检索相关性调优（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-07

## 目标

提升 HP 知识库搜索质量：① 清理/合并短 chunk（现状 <50 字符 chunk 约 16.4%，目标 <15%）；② 修复检索相关性失真（实测搜「HermesPet」命中无关 RSS 文章）。

## 红线（先看）

1. **只动数据质量与检索逻辑**：hp@ `/data/knowledge/bin/kb-search.py`（检索）、DB 中 chunks/documents 的**短 chunk 数据操作**、相关解析/分块逻辑（如 md_parser）。**禁止**动采集链路（kb-collect/ingest 归 hp004）、前端（dashboard 归 hp005）。
2. 数据操作安全：清理短 chunk 前先备份（PG dump 或导出受影响行），只处理 content < 50 字符的 chunk；**禁止删除文档主体**（document 级数据不动，只处理 chunk 级）。
3. 相关性调优不得改变 kb-search CLI 的既有接口（search/ask/stats 三命令签名不变）。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- hp@：`/data/knowledge/bin/kb-search.py`、PG（chunks 短 chunk 数据）、解析/分块相关代码（如 `md_parser`）
- Mac2017：`local/scripts/kb-search.py`（仅只读确认转发兼容，不改）
- 回写区：短 chunk 清理前后对照、相关性调优前后对比样例

## 步骤

1. 摸底（只读）：
   - `SELECT count(*) FILTER (WHERE char_length(content) < 50), count(*) FROM chunks` 确认短 chunk 当前占比（基线 16.4%）
   - 抽查短 chunk 内容分布：是截断产物、噪音还是真实短内容（如标题/链接残留）
   - 读 `kb-search.py`（hp@ 真身）检索逻辑：向量相似度参数（top_k、阈值）、是否混用 keyword、embedding 模型（bge-m3 1024 维）
2. 短 chunk 治理：
   - 按摸底结论选择策略：合并到相邻 chunk（保留语义）或清洗删除（噪音类）；策略与执行方式写清
   - 操作前备份受影响行；操作后 `SELECT count(*) FILTER (WHERE char_length(content) < 50) FROM chunks` 复核占比 <15%
3. 相关性调优：
   - 用失败样例（如「HermesPet」）复现：记录当前返回结果
   - 排查方向（按实际）：embedding 维度/模型一致性、ivfflat 索引参数（lists=466 对 74k 行是否合理）、检索阈值、RSS 源噪音权重、query 预处理
   - 调优后同查询复测：相关性明显改善（回写区附前后对比）
4. 回归：`kb-search.py search/ask/stats` 三命令全部可用；随机抽 3 个正常查询无回归。
5. commit+push 到卡内分支 `codex/hp006-search-quality-short-chunks`（勿直推 main；业务改动走 hp 仓同名分支——注意跨仓交付规则：hp 仓也要建独立分支并 push 证据给真实 hash）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 短 chunk 占比从基线降到 <15%（前后 `SELECT` 对照证据，含备份说明）。
2. 「HermesPet」类失败样例相关性改善（前后 Top5 对比，回写区可见）。
3. kb-search 三命令回归通过（实测输出）。
4. 文档主体零删除（documents 计数不变，chunk 计数变动有策略说明）。
5. 跨仓交付：hp 仓独立分支存在、commit hash 真实（机审将独立验证）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
