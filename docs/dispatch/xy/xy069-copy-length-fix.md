# 任务卡 xy069 · 文案字数自校正（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy069 · 状态版本：1
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

生产实测 3456 生成的文案字数偏长（437/415 字，阈值 300-400），writer 结构校验只记录不重写。本卡实现**字数自校正**：

1. **超标自动重生成**：`src/xianyu/content/writer.py` 在结构校验通过但字数超标时，自动触发一次 3456 重生成（prompt 附加「控制在 350 字左右」），再校验；仍超标则截段降级（保留钩子/痛点，裁干货细节）。
2. **字数达标优先**：重生成后按 350±50 目标验收；最终字数如实记录在结果 data（`word_count` 字段）。
3. **失败降级**：重生成失败/仍超标 → 截段 + `engine="mock"` 或 `engine="llm"` 如实标记（不得虚报达标）。
4. **测试**：字数超标→重生成→达标链路单测（mock 3456）；截段降级单测。

## 实现要求

1. 改动限于 `src/xianyu/content/writer.py`、对应 `tests/`。
2. 重生成用现有 3456 通道（chat_json），不新增外部依赖。
3. 结果 data 增加 `word_count` 字段（正文去段落标记后字数）。
4. 结构四段（钩子/痛点/干货/号召）保持不因截段丢失。

## 红线

1. 只改 xianyu 业务仓；不发布、不触碰 Cookie/外部账号、不启动 M7。
2. 不得虚报字数达标（截段/mock 如实标记）。
3. 不读取或输出凭据值。
4. 所有改动业务分支 commit；测试真实通过。

## 范围

- `/Users/fan/program/apps/xianyu/src/xianyu/content/writer.py`
- `/Users/fan/program/apps/xianyu/tests/content/test_writer.py`

## 步骤

1. 读 writer.py 现状（校验/重生成点）；跑 `tests/content/test_writer.py` 确认基线。
2. 实现字数超标→重生成→再校验链路；补单测。
3. 实现截段降级（保留四段骨架）；补单测。
4. 结果 data 加 `word_count`。
5. 全量相关测试真实通过；业务分支 commit；`.ccc-result.md` 如实记录（含重生成/截段实测字数）。

## 验收标准

1. 字数超标时自动重生成，最终字数落入 300-400（如重生成仍超则截段，如实标记）。
2. 四段结构（钩子/痛点/干货/号召）在最终产物中保留。
3. 结果 data 含 `word_count` 字段，值为真实字数。
4. 重生成/截段降级路径单测通过；`tests/content/test_writer.py` 全部通过退出码 0。
5. 业务分支 commit 存在；工作树除结果文件外干净。
6. 不虚报：截段/mock 如实标记，字数如实记录。

## 门禁

测试（content）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest tests/content/test_writer.py -q`

## 回写要求

结果写入 `.ccc-result.md`，含：自校正链路 diff、重生成/截段实测字数、单测输出、维护区四问（标准键名）、变更证据。

## 人工批注

无

## 回写区

（待执行体回写）
