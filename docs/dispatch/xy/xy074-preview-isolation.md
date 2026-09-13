# 任务卡 xy074 · preview 测试数据依赖隔离修复

> 关联：xy-plan-009 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy074 · 状态版本：5
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标
修 `tests/admin/test_preview.py` 的**测试数据依赖缺陷**：fixture 只 patch 视频扫描目录 `LIBRARY_OUTPUT_DIR`（test_preview.py:31-40），未 patch 图文扫描目录 `LIBRARY_ARTICLE_OUTPUT_DIR`——在有生产数据的工作树（`workspace/outputs/image_text/` 存在）上跑，真实图文产物泄漏进 items 致 `items[0]["type"]=="article"`，8 项稳定红（与功能无关，属测试隔离债；bdcb71a~5544e25 间引入，非 xy073 所致）。

## 实现要求
1. `admin_client` fixture 补 patch `server.LIBRARY_ARTICLE_OUTPUT_DIR` → tmp 空目录（默认无图文产出）。
2. 需图文项的用例（如 `test_article_item_has_all_preview_fields`、`_make_article_task` 相关）在 tmp 目录构造自有数据，不依赖工作区。
3. 两态验证：在当前 main 工作树（有生产数据）与干净临时 worktree（无数据）都跑 `pytest tests/admin/test_preview.py -q` → 均应 13 passed。
4. 若发现真实功能缺陷（非测试隔离问题）→ 停下如实进回执，不硬改行为。

## 红线
1. 只动 `/Users/fan/program/apps/xianyu/tests/admin/test_preview.py`；禁碰 `admin/api/server.py` 运行行为（判定逻辑是正确的，脏的是测试）；禁碰 workspace/ 真实产出、禁删文件。
2. 不启动 M7/Cookie、不发布。
3. diff 最小（仅 fixture+必要用例，≤15 行）。

## 范围
- /Users/fan/program/apps/xianyu/tests/admin/test_preview.py

## 步骤
1. 当前 main 树复现 8 failed（贴输出）。
2. 修 fixture（补 patch 图文目录）。
3. 同树复跑 → 13 passed；另建干净 worktree 跑 → 13 passed（两输出贴回执）。
4. 全目录回归 `pytest tests/admin/ -q` 无新失败。
5. 写 .ccc-result.md（五段）交回写。

## 验收标准
1. 有数据树、无数据树两态 `pytest tests/admin/test_preview.py -q` 均 13 passed（输出在回执）。
2. `pytest tests/admin/ -q` ≥104 等效（无新失败）。
3. diff 仅 test_preview.py、≤15 行。

## 门禁
- card_gate 五项校验（必填字段齐全、状态=待分派、项目前缀 xy 在 registry、验收=DSH、范围路径在仓内存在）——本卡满足。

## 回写要求
- 回写区四问逐项填；教训沉淀引用 docs/notes 具体文件（判例=对照跑必须同树同数据态，账本 `839b08f`/`0d00e38` 已录）。

## 人工批注
无批注。

## 回写区

## 0. 卡标题复述

任务卡 xy074 ·「preview 测试数据依赖隔离修复」（关联 xy-plan-009 · 执行体 DSH · 验收 DSH · 状态 待分派 · 版本 xy074 · 状态版本 4）：修 `tests/admin/test_preview.py` 的**测试数据依赖缺陷**——`admin_client` fixture 只 patch 视频扫描目录 `LIBRARY_OUTPUT_DIR`，未 patch 图文扫描目录 `LIBRARY_ARTICLE_OUTPUT_DIR`，导致在有生产数据的工作树（`workspace/outputs/image_text/` 存在）上跑 `pytest tests/admin/test_preview.py -q` 时真实图文产物泄漏进 items，`items[0]["type"]=="article"`，8 项稳定红（与功能无关，属测试隔离债；bdcb71a~5544e25 间引入，非 xy073 所致）。要求：① fixture 补 patch `LIBRARY_ARTICLE_OUTPUT_DIR` → tmp 空目录；② 需图文项用例在 tmp 构造自有数据、不依赖工作区；③ 两态（有数据 main 树 / 干净 worktree）均 13 passed；④ 全目录回归 `pytest tests/admin/ -q` 无新失败；⑤ diff 最小（仅 test_preview.py，≤15 行）。红线：只动 `tests/admin/test_preview.py`，禁碰 `admin/api/server.py` 运行行为、禁碰 workspace/ 真实产出、禁删文件，不启动 M7/Cookie、不发布。

## 1. 探针输出

**环境**：worktree `/Users/fan/program/apps/.ccc-wt/xy/xy074`（branch `codex/xy074-preview-isolation`，base `1a65c3b`=main）；`.venv` 为指向主仓的既有符号链接（`lrwxr-xr-x 1 fan staff 36 Sep 13 20:09 .venv -> /Users/fan/program/apps/xianyu/.venv`），Python 3.12.0；业务主仓 `/Users/fan/program/apps/xianyu`（branch `main`，`git status --short` 空）。

**两树数据态实测**：

| 树 | `workspace/outputs/image_text/` | 态 |
|---|---|---|
| 主仓 `/Users/fan/program/apps/xianyu` | 10 个真实图文任务目录 | 脏态 |
| worktree `/Users/fan/program/apps/.ccc-wt/xy/xy074` | 目录不存在（`ls` 仅 audio/images/video） | 干净态 |

**server 数据流取证**（`admin/api/server.py`，只读未改）：
- `server.py:52` `LIBRARY_ARTICLE_OUTPUT_DIR = ROOT / "workspace" / "outputs" / "image_text"`
- `/api/v1/library` → `scan_library()`（无参）→ `output_dir is None` 分支 `items.extend(_scan_article_library())` → 读全局 `LIBRARY_ARTICLE_OUTPUT_DIR`
- 结论：fixture 未 patch 图文目录时，真实图文经全局路径泄漏进 items（判定逻辑正确，脏的是测试）。

**复现（主仓 · 脏态 · 未修复）**：`cd /Users/fan/program/apps/xianyu && .venv/bin/python -m pytest tests/admin/test_preview.py -q`

```
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_video_item_has_all_preview_fields
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_article_item_has_all_preview_fields
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_video_path_ends_with_mp4
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_items_separable_by_type
FAILED tests/admin/test_preview.py::TestPreviewDataContract::test_empty_response_structure
FAILED tests/admin/test_preview.py::TestPreviewHelper::test_separate_videos_and_articles
FAILED tests/admin/test_preview.py::TestPreviewHelper::test_empty_items_list_safe
FAILED tests/admin/test_preview.py::TestPreviewHelper::test_duration_format_contract
==================== 8 failed, 5 passed, 1 warning in 2.37s ====================
```

**失败断言取证**（根因直接命中卡描述）：

```
assert item["type"] == "video"
E   AssertionError: assert 'article' == 'video'        # items[0] 被真实图文占据
assert item["title"] == "展示图文"
E   AssertionError: assert '3000收的影楼摄影灯，...手赚1500，捡漏全程复盘' == '展示图文'
assert item["path"].endswith(".mp4")
E   AssertionError: assert False
E    +  where 'workspace/outputs/image_text/20260910-201411/index.html'.endswith
assert len(articles) == 1
E   AssertionError: assert 11 == 1                     # 10 真实图文 + 1 自构
assert body["count"] == 0
E   assert 10 == 0                                     # 10 个真实图文任务泄漏进空态断言
```

## 2. 自测输出

**修复内容**：`admin_client` fixture 补 3 行——`article_dir = tmp_path / "outputs" / "image_text"` + `mkdir(parents=True, exist_ok=True)` + `monkeypatch.setattr(server, "LIBRARY_ARTICLE_OUTPUT_DIR", article_dir)`。需图文项用例（`_make_article_task` 系列）本就把自有数据写入 tmp 的 video output_dir（`_scan_library_task` 的 `.md` 分支收录），不依赖工作区，无需改动。未触 `server.py`、未触 workspace/、未删文件。

**① 干净态（worktree 无 image_text 目录）· 修复后**：
`cd /Users/fan/program/apps/.ccc-wt/xy/xy074 && .venv/bin/python -m pytest tests/admin/test_preview.py -q`

```
======================== 13 passed, 1 warning in 2.10s =========================
```

**② 脏态（主仓 10 个真实图文任务）· 修复后**：白名单文件临时同步主仓（卡「范围」同一文件 `tests/admin/test_preview.py`），跑完即还原（备份 `/tmp/xy074_orig_test_preview.py` + `cmp` 字节级验证）：

```
======================== 13 passed, 1 warning in 2.12s =========================
```

还原核验：`cmp -s` → `RESTORE-OK byte-identical`；主仓 `git status --short` → 空（无 tracked 变更）。

**③ 全目录回归 `pytest tests/admin/ -q`**（三组同法对比）：

| 组 | 状态 | 结果 |
|---|---|---|
| A 基线·脏态·未修复 | 1 | `8 failed, 98 passed, 30 warnings in 4.94s` |
| B 脏态·已修复 | 0 | `106 passed, 30 warnings in 4.62s` |
| C 干净态·已修复 | 0 | `106 passed, 30 warnings in 4.58s` |

- A 的 8 个失败全部为本次修正的 preview 泄漏测试，B/C 零失败、零新增 → **106 ≥ 104 达标**。
- C 组 `EXIT=0`（`pytest tests/admin/ -q` 退出码 0）。
- 每轮脏态跑完后主仓文件均 `cmp` 字节级还原，`git status --short` 空；worktree `.venv` 为既有未跟踪符号链接，未纳入提交。

## 维护区

1. **方案同步**：[是] [有] 本卡为 xy-plan-009 附属测试债修复（纯测试隔离，无功能/行为变更）。方案 `009-frontend-showcase.md` 第 6 行「关联卡」列表**已含 xy074**：`xy052、xy053、xy054、xy055、xy060、xy061、xy062、xy064、xy073、xy074`（实测 `grep -n "关联卡" /Users/fan/program/CCC/docs/projects/xy/plans/009-frontend-showcase.md` → 第 6 行命中含 xy074），方案文档无需改动；本卡即本次回执。
2. **教训沉淀**：[无] [无] 受红线「只动 `tests/admin/test_preview.py`、diff ≤15 行」约束，本次未向 `docs/` 落笔；判例（**对照跑必须同树同数据态**——脏态未修 8 红 ↔ 修复后双态 13 绿、全目录 106 绿）已完整记录于本回执 §1-§2，建议合入时补录。实测两点供人审校准（与卡「回写要求」所引路径不符）：① 业务仓 `docs/notes/` 目录**不存在**（`ls` → `docs/notes 不存在于业务仓`）；② 账本 hash `839b08f`/`0d00e38` 在业务仓 `docs/` 与 CCC 仓 `docs/` 下 grep **均无落地文件**（唯一命中为卡自身 `xy074-preview-isolation.md:39` 与上一轮回写区第 114 行），即卡「回写要求」引用的 `docs/notes` 判例账本路径需人审补正后方可引用。
3. **档案/README**：[否] [无] 无新增对外接口/行为变化（`server.py` 未动、API 契约未变），README 无需更新。
4. **线路图**：[否] [无] 无架构/数据流变更（仅测试 fixture 补一个 monkeypatch 隔离点，不触及 `scan_library()` 判定逻辑），不进线路图。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：Q1 方案同步校验失败。方案关联卡「xy052、xy053、xy054、xy055、xy060、xy061、xy062、xy064、xy073」中不包含本卡 ID「xy074」
