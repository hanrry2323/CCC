# 任务卡 xy069 · 文案字数自校正（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy069 · 状态版本：2
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

## 0. 卡标题复述

任务卡「xy069 · 文案字数自校正（开发线 Build）」：生产实测 3456 生成的文案字数偏长（437/415 字，阈值 300-400），writer 结构校验只记录不重写。本卡实现字数自校正：① 结构校验通过但字数超标时自动触发一次 3456 重生成（prompt 附加「控制在 350 字左右」）并再校验，仍超标则截段降级（保留钩子/痛点，裁干货细节）；② 重生成后按 350±50 验收，最终字数如实记录在结果 data 的 `word_count` 字段；③ 重生成失败/仍超标 → 截段 + engine 如实标记（不得虚报达标）；④ 单测覆盖超标→重生成→达标链路（mock 3456）与截段降级。

## 1. 探针输出

探针脚本（mock 3456，三链路实测，输出原始复制）：

```
[探针1] 超标版字数=438 (实测437场景)
[探针1] 截段后字数=364, 四段齐全=True, <=400=True
[探针2-重生成] calls=2 字数=353 regenerated=True truncated=False engine=llm 达标=True
[探针2-截段] calls=2 字数=342 regenerated=True truncated=True engine=llm 四段=True
[探针2-异常截段] calls=2 字数=364 truncated=True engine=llm
[探针3] 全部探针通过
exit=0
[stderr] 2026-09-10 19:11:46.941 | INFO | xianyu.content.writer:_gen_article:279 - [writer] 字数超标 438 字（>400）→ 重生成一次
2026-09-10 19:11:46.941 | INFO | xianyu.content.writer:_gen_article:287 - [writer] 重生成达标: 353 字（300-400）
2026-09-10 19:11:46.943 | INFO | xianyu.content.writer:_gen_article:279 - [writer] 字数超标 438 字（>400）→ 重生成一次
2026-09-10 19:11:46.943 | INFO | xianyu.content.writer:_gen_article:296 - [writer] 重生成仍超标 416 字 → 截段降级
2026-09-10 19:11:46.944 | INFO | xianyu.content.writer:_gen_article:305 - [writer] 截段降级: 416 → 342 字（四段骨架保留，字数如实记录）
2026-09-10 19:11:46.945 | INFO | xianyu.content.writer:_gen_article:279 - [writer] 字数超标 438 字（>400）→ 重生成一次
2026-09-10 19:11:46.946 | WARNING | xianyu.content.writer:_gen_article:301 - [writer] 重生成失败 → 截段降级第一版: net
2026-09-10 19:11:46.946 | INFO | xianyu.content.writer:_gen_article:305 - [writer] 截段降级: 438 → 364 字（四段骨架保留，字数如实记录）
```

实测字数：重生成达标 438→353（落入 300-400）；重生成仍超 416→截段 342；重生成异常→截段第一版 438→364；截段产物四段标记（钩子/痛点/干货/行动号召）全部保留，`truncated=True`/`engine="llm"` 如实标记。

自校正链路 diff 核心（`src/xianyu/content/writer.py`，+205/-30）：
- 新增 `count_words()`（去段落标记字数，word_count/重生成/截段统一口径）、`structural_problems()`（结构校验与字数解耦，保证「结构完整但字数超标」判定精确）；
- 新增 `truncate_to_fit()`（截段降级：保留四段标记，从干货段尾部逐句丢细节至 ≤400）；
- 新增 `REGEN_PROMPT_APPEND`（重生成附加指令，含「正文字数控制在 350 字左右」）；
- `_gen_article` 重构：主生成 → 字数超标重生成一次（prompt 附加指令）→ 再校验；重生成达标/仍超/失败三态分别处理，抽出 `_generate_once` / `_finalize_article`；
- `execute` 各分支 data 增加 `word_count`，llm 分支透传 `regenerated`/`truncated`。

## 2. 自测输出

门禁命令（卡「## 门禁」原样）：`.venv/bin/pytest tests/content/test_writer.py -q`

```
============================== 29 passed in 1.76s ==============================
```
退出码 0（原 17 例 + 新增 12 例：重生成达标/仍超截段/失败截段/不重生成分支×2/word_count 字段×2/截段单测×3/字数结构拆分×2）。

补充自测：
- content 全目录：`.venv/bin/pytest tests/content/ -q` → `94 passed in 3.45s`，退出码 0（confirm ab_writer/rewriter 等不受影响）。
- lint：`.venv/bin/ruff check src/xianyu/content/writer.py tests/content/test_writer.py` → `All checks passed!`。

## 维护区

1. **方案同步**：[是] `[是]` —— 本卡隶属 xy-plan-008「视频高表现力二期」，仅按卡实现 writer 字数自校正：改动只落在白名单 `src/xianyu/content/writer.py` + `tests/content/test_writer.py`（git diff 仅此两文件），未越范围、未顺带推进其他规划项。
2. **教训沉淀**：[无] `[否]` —— 本卡白名单限制 xianyu 业务仓两文件 + `.ccc-result.md`，未向 CCC 仓 `docs/notes/` 写入新 lesson 文档；可复用教训（字数判定与校验判定共用同一 `count_words` 口径、测试用 `count_words(skeleton)` 精确控字数避免手算漂移）以代码注释与单测形式落在业务仓内（writer.py:85-98 注释、test_writer.py `_pad_copy` helper）。
3. **档案/README**：[否] `[否]` —— 未改变项目结构、技术栈、路径或对外接口；未触碰 README/档案/生产核心。
4. **线路图**：[否] `[否]` —— 字数自校正不影响 xianyu 下一步规划；未修改 GOAL/roadmap，未推进规划外事项。
