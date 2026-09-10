# 任务卡 xy066 · 图文配图语义选图增强（开发线 Build）

> 关联：xy-plan-008「视频高表现力二期」 · 执行体：DSH · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-10 · 版本：xy066 · 状态版本：1
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

xy062 遗留「配图占位」缺口：文章配图曾为 `[MOCK IMAGES]` 占位。`src/xianyu/content/image.py` 已具备 Pexels→picsum 真实图降级链（xy063 已实修），但缺「按文案段落语义选图」。本卡补齐：

1. **按段落语义选图**：从文案正文按段落提取关键词（优先取标题/每段首句核心名词；xy065 的四段结构可复用：钩子/痛点/干货/号召），为每段选 1 张语义匹配真图。
2. **每段一图产出**：图文产物 `index.html` 每段落配对应图；`image_paths` 指向真实图片文件（JPEG，≥5KB 校验沿用）。
3. **降级兜底**：Pexels 无凭据/失败 → picsum；仍失败 → 真实占位（本地生成的设计化文字卡图，**不得再输出 `[MOCK IMAGES]` 文本占位**）。
4. **测试**：段落关键词提取、每段一图映射、降级链单测（mock 网络）；全部真实通过。

## 实现要求

1. 改动限于 `src/xianyu/content/image.py`、`src/xianyu/content/writer.py`（如需传入段落结构）、对应 `tests/`。
2. 关键词提取为确定性函数（纯文本→关键词列表），可单测；不得依赖外部模型。
3. 降级路径必须产出真实图片文件（哪怕本地生成文字卡），不得输出占位文本。
4. 凭据读取沿用 `_pexels_key()`（env/共享凭据，运行时读取，日志不输出值）。

## 红线

1. 只改 xianyu 业务仓；不发布、不触碰 Cookie/外部账号、不启动 M7。
2. 禁止把任何凭据值写入文件、测试、日志或提交。
3. 不得伪造图片文件或虚报来源；每张图如实记录 source（pexels/picsum/local）。
4. 不得删除既有产物/数据库；所有改动业务分支 commit；测试真实通过。

## 范围

- `/Users/fan/program/apps/xianyu/src/xianyu/content/image.py`
- `/Users/fan/program/apps/xianyu/src/xianyu/content/writer.py`
- `/Users/fan/program/apps/xianyu/tests/content/test_image.py`

## 步骤

1. 读 image.py 现状与 `_fetch_image`/`_download_picsum`；跑 `tests/content/test_image.py` 确认基线。
2. 实现段落关键词提取（确定性）与每段一图映射。
3. 实现降级链：Pexels→picsum→本地文字卡图（真实文件）。
4. 补单测（mock 网络）：关键词提取、映射、三级降级。
5. 全量相关测试真实通过；业务分支 commit；`.ccc-result.md` 如实记录（含取样图片 source/大小）。

## 验收标准

1. 段落关键词提取为确定性纯函数，单测覆盖（含空段/无名词段）。
2. 每段一图映射正确；`index.html` 每段引用对应真实图片文件。
3. 三级降级链（pexels→picsum→本地）各路径单测通过；无凭据/失败时产出真实图片文件（非占位文本）。
4. `tests/content/test_image.py` 及内容相关测试全部通过退出码 0；全量回归无新增失败。
5. 代码/测试/文档无任何凭据明文。
6. 业务分支 commit 存在；工作树除结果文件外干净。
7. 不虚报：降级路径与图片来源如实记录。

## 门禁

测试（content）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest tests/content/test_image.py tests/content/test_writer.py -q`

## 回写要求

结果写入 `.ccc-result.md`，含：改动 diff 摘要、关键词提取示例、每段一图映射示例（段落→图 source/大小）、测试原始输出、降级路径实测、维护区四问（标准键名）、变更证据。

## 人工批注

无

## 回写区

（待执行体回写）
