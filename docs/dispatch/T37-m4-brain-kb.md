# 任务卡 T37 · M4-2 大脑接知识库：检索注入 + 知识问答实测（Trae GLM5.2 执行）

> 关联：INT-120（M4 知识移植/独立移交 · D3）· 依据：Codex 2026-08-03 评估——brain.py（T29）仅靠 Claude Code 自读文件，未接结构化知识检索，D3「脑必须具备 MCP 接入 + 全库读取能力」未兑现
> 执行体：Trae（GLM5.2）· 验收：Codex（严格）· 状态：已回写 · 日期：2026-08-03

## 目标

`/conversation` 大脑 Agent 在回答前对 CCC 自建知识库做结构化检索，命中内容注入 prompt 上下文；知识类问题能直接引用知识库内容作答，非知识问题不劣化。

## 红线（先看）

1. **零外脑**：检索只读 `knowledge/`（server/kb BM25 索引），禁止读 qx-map / hp-kb；违反即打回。
2. 知识库路径/开关配置化（config.env，如 `CCC_BRAIN_KB=1` + `CCC_KB_ROOT`/`KB_INDEX_DIR`），代码不写死绝对路径。
3. 检索失败降级：知识库不可用/未配置 → 走现有裸大脑逻辑，禁止对话报错中断（容错）。
4. 不动 2017 运行面（本卡 M1 实现 + 单测）；不改对话 API 协议；真实提交。
5. **回写前必须 push 成功并在回写区附证据**（T36 教训 P2-4：交付时未推送）。

## 范围

server/web/brain.py、server/kb/（search.py 如缺查询入口则补最小查询函数）、server/config/（config.example.env + loader）、server/web/server.py（如需传 config 给 brain）、server/tests/（test_brain_kb 新用例）。

## 步骤

1. 复用 server/kb/search.py 的索引检索能力，新增最小查询函数（load index → 对问题做 BM25 检索 → 返回 top-k 命中文档片段与域）。
2. brain.py：`_build_prompt` 前调检索（配置开关 CCC_BRAIN_KB=1 时启用；top-k 默认 3，可配置）；命中注入「【知识库参考】域：标题：片段…」段落，置于系统人格与历史之间；未命中/未配置/异常 → 静默降级。
3. 配置：config.example.env 补 CCC_BRAIN_KB / CCC_KB_ROOT（或复用 KB_INDEX_DIR）；loader 加可选键。
4. 单测：命中注入（构造小索引 → 断言 prompt 含知识片段）、未命中降级、未配置降级、检索异常降级、非知识问题不注入；现有 brain 测试不回归。
5. 本地实测知识问答 5 题（节点/路径、项目元数据、决策、教训、服务端口各 1）：断言回答引用知识库内容（人工判读 + 记录）。
6. 提交（message 含 T37）。

## 验收标准

1. 命中注入有单测覆盖且通过；降级路径（未配置/未命中/异常）均不报错，对话照常。
2. 5 题知识问答实测：回答与知识库内容一致（引用命中），非知识问题回答不劣化（对照开关关闭基线）。
3. `pytest server/tests -q` 全绿；三扫描零命中（硬编码/密钥/外脑引用）。
4. 真实提交；工作树仅剩许可预存项。

## 回写要求

卡头状态更新为「已回写」；回写区填：检索注入实现要点、5 题问答实测记录（问/答/命中域）、降级路径验证、pytest 结果、commit hash。

## 回写区

**执行体**：Trae（GLM5.2）· 日期：2026-08-03 · commit：`468c260`（已 push origin/main）

### 检索注入实现要点

- `server/web/brain.py` 新增 `_retrieve_kb_context(message)`：调 `server.kb.search.search`（BM25）检索 `knowledge/` 索引，命中返回「【知识库参考】\n{section}：{title}：{snippet}」段落（title 取 doc_id `::` 之后部分）。
- `_build_prompt` 在系统人格与历史之间注入参考段落；未命中/未配置/异常 → 静默降级返回空串，对话照常走裸大脑（红线 #3）。
- 配置化（零硬编码）：`CCC_BRAIN_KB`（开关 1/true/yes/on）· `CCC_KB_INDEX_DIR`（索引目录，复用 server/kb/search 读取的同名变量）· `CCC_BRAIN_KB_TOP_K`（默认 3）。
- `config.example.env` 补三键 + 清理死键 `KB_INDEX_DIR`（代码实际读 `CCC_KB_INDEX_DIR`，原模板键名不一致）；`loader.py` OPTIONAL_KEYS 加三键。
- 红线 #1：只 `from server.kb.search import search`，零 qx-map / hp-kb 引用。

### 5 题知识问答实测（经 2017:6100 真实大脑，KB 开启）

| # | 类别 | 问 | 命中域 | status | 回答（节选） | 引用 KB |
|---|------|----|--------|--------|-------------|---------|
| 1 | 节点/路径 | Mac2017 的 IP 地址是多少 | 03-key-decisions / decisions | 200 | `192.168.3.116`（2017 生产端 :7788） | ✓ 引用 CLAUDE.md 健康检查 + nodes-paths |
| 2 | 项目元数据 | CCC 主仓在本机的路径 | projects / 03-key-decisions / decisions | 200 | `/Users/apple/program/CCC` | ✓ 引用 working directory + projects |
| 3 | 决策 | CCC 重构方案的核心 | lessons / 03-key-decisions | 200 | 薄驱动 Engine + 文档流转 + 看板/HTTP | ✓ 显式引用「知识库 D1-D10」 |
| 4 | 教训 | Plan 写法有什么教训 | 04-lessons / lessons | 200 | Plan 必须用自然语言，禁止裸命令 | ✓ 显式引用「教训 L1」 |
| 5 | 服务端口 | CCC Web Server 用什么端口 | 03-key-decisions / nodes-paths / 01-nodes-paths | 200 | `7788`（2017 单端） | ✓ 引用 nodes-paths :7788 |

### 非知识问题不劣化对照

- 数学题「计算 23 乘以 47」KB 开启 → 回答 `1081`（正确，未因 KB 噪声注入劣化）。
- 纯数学「1+1=?」无中英 token → BM25 无命中 → 不注入（与开关关闭基线一致）。

### 降级路径验证（单测覆盖）

| 路径 | 触发 | 行为 | 单测 |
|------|------|------|------|
| 未配置 | `CCC_BRAIN_KB` 未设/=0 | 不检索不注入 | TestNotConfiguredDegrade（3 例） |
| 未命中 | 查询有 token 无匹配 | 返回空串不注入 | TestNoHitDegrade（2 例） |
| 检索异常 | search 抛 OSError/RuntimeError | 静默返回空串不报错 | TestRetrievalExceptionDegrade（2 例） |
| 命中注入 | BM25 有命中 | 注入参考段落 | TestHitInjection（4 例） |
| 非知识问题 | 无 token（1+1=?） | 不注入 | TestNonKnowledgeNoInjection（2 例） |
| 不回归 | 开关关闭 | prompt = 系统人格+历史+当前问题 | TestNoRegressionWhenDisabled（2 例） |

### pytest 结果

`pytest server/tests/ --tb=short` → **295 passed**（含 T37 新增 15 例）；`ruff check` 零告警。

### 三扫描

- 硬编码：brain.py 可执行代码零字面量（IP/端口/路径全走 env）；docstring 中 `127.0.0.1:6100` 为 T29 既有示例。
- 密钥：零（仅 env 变量名引用）。
- 外脑引用：零（仅 `from server.kb.search import search`；qx-map/hp-kb 仅出现在红线禁止语句中）。

### 工作树

仅许可预存项，无残留。
