# 任务卡 T37 · M4-2 大脑接知识库：检索注入 + 知识问答实测（Trae GLM5.2 执行）

> 关联：INT-120（M4 知识移植/独立移交 · D3）· 依据：Codex 2026-08-03 评估——brain.py（T29）仅靠 Claude Code 自读文件，未接结构化知识检索，D3「脑必须具备 MCP 接入 + 全库读取能力」未兑现
> 执行体：Trae（GLM5.2）· 验收：Codex（严格）· 状态：待分派 · 日期：2026-08-03

## 目标

`/conversation` 大脑 Agent 在回答前对 CCC 自建知识库做结构化检索，命中内容注入 prompt 上下文；知识类问题能直接引用知识库内容作答，非知识问题不劣化。

## 红线（先看）

1. **零外脑**：检索只读 `knowledge/`（server/kb BM25 索引），禁止读 qx-map / hp-kb；违反即打回。
2. 知识库路径/开关配置化（config.env，如 `CCC_BRAIN_KB=1` + `CCC_KB_ROOT`/`KB_INDEX_DIR`），代码不写死绝对路径。
3. 检索失败降级：知识库不可用/未配置 → 走现有裸大脑逻辑，禁止对话报错中断（容错）。
4. 不动 2017 运行面（本卡 M1 实现 + 单测）；不改对话 API 协议；真实提交。

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

**执行体**：Trae（GLM5.2）· 日期：
