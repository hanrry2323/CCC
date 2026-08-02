# 任务卡 T1-R · 服务端骨架修复与深化（Claude Code 执行）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1 · 管理席：Codex
> 执行体：Claude Code（CLI）· 验收：Codex · 状态：待分派 · 日期：2026-08-02
> 前序：T1（Trae）验收未通过，问题清单见下；本卡在既有 `server/` 上修复深化，不推倒重来。

## 打回问题清单（Trae 版 T1 未通过的原因）

1. **执行体注册表 schema 偏离契约 §7**：用了旧 CCC 的工具类型（opencode/python/ollama/cli/auto）当角色，缺 Trae / 管理席 / 验收席，没有「手动 GUI」分类——角色与工具再次焊死，违背 D10 角色化原则。
2. **硬编码扫描自我放行**：`run.example.sh` / `health.example.sh` 出现字面 `python3`，执行体自行判定「合理技术选型」放行——验收标准被执行体改写，纪律不成立。
3. **工作未提交**：回写填的 commit 是任务卡提交，`server/` 全部 untracked，没有实现提交。
4. **子目录 README 深度不足**：engine/board/web/relay 仅一句话，撑不起 T2/T3 施工蓝图。

## 目标

在既有 `server/` 上修复上述 4 项并深化文档，使 T1 达到契约级质量，并提交入库。

## 红线（先看）

1. **不删除任何文件**；不推倒重来（保留已有结构、loader、tests 的可用部分）。
2. 不碰旧代码：`scripts/`、`app/`、`desktop/`、`lib/`、`db/` 零改动。
3. 不落密钥；不碰运行面；不读不写 qx-map / 外脑。
4. **验收标准不可自行解释**：本卡验收标准由 Codex 判定，执行体只提供证据，不做裁决。
5. 完成必须提交（真实 commit hash 回写）；工作树只允许预存 2 个无关改动（`scripts/.ccc/agent-mind/decided.json`、`_update_handoff.py`），不得带入提交。

## 步骤

1. **重写执行体注册表** `server/config/executors.example.json` 为契约 §7 五角色 schema：
   - 开发执行体 · 手动 GUI · Trae
   - 开发执行体 · 可后台 CLI · OpenCode
   - 维护执行体 · 可后台 CLI · Claude Code
   - 管理席 · — · Codex
   - 验收席 · — · Codex
   - 删除旧类型（opencode/python/ollama/cli/auto）；分类只允许 `可后台 CLI` / `手动 GUI`。
2. **消灭代码/模板工具名字面量**：`config.example.env` 增加 `PYTHON_BIN` 占位；`run.example.sh` / `health.example.sh` 改用 `$PYTHON_BIN` 等变量；复核 plist 无字面工具名 / 绝对路径 / 端口。
3. **硬编码扫描**（rg 黑名单：`/Users`、字面端口、模型名、工具名）以**零字面量**为通过线；完整扫描命令与输出写入回写区。
4. **子目录 README 深化**（engine/board/web/relay/deploy/config/tests）：职责、关键约定、与相邻模块关系、T2/T3 施工入口；`server/README.md` 同步更新。
5. **测试补强**：
   - loader：正常 / 缺项 / 空值 / 可选默认四用例；
   - executors schema：角色集合 = 契约 §7 五角色、分类 ∈ {可后台 CLI, 手动 GUI}、绑定非空。
6. **提交**：`git add server/` + 本卡修改；commit message 前缀 `chore(server):`；回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. `executors.example.json` 与契约 §7 完全一致（schema 测试锁定）。
2. 代码 / 模板零工具名字面量（扫描输出为证；`$PYTHON_BIN` 等变量化）。
3. 子目录 README 具备施工蓝图深度（Codex 判定）。
4. 测试全绿且新增 schema 断言；loader 四用例覆盖。
5. 有真实实现提交；工作树仅剩 2 个预存无关改动。
6. 无删除、无密钥明文、无运行面动作、未碰旧代码 / 外脑。

## 回写要求

结果摘要（人话一句）、测试输出、完整硬编码扫描输出、commit hash、验收自检对照表。

## 回写区

（Claude Code 回写）
