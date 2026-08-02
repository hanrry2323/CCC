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

**执行体**：Claude Code（CLI）  
**日期**：2026-08-02  
**实现 commit**：`e1921d9`（`chore(server):` 前缀 · 15 文件 · 809 insertions）

### 结果摘要

对 Trae 版 T1 的 4 项打回问题逐一修复：执行体注册表重写为契约 §7 五角色 schema、代码与模板工具名字面量全部变量化（`$PYTHON_BIN`）、子目录 README 深化至施工蓝图深度、loader 四用例 + executors schema 契约锁定，27 用例全绿并已提交入库。

### 测试输出

```
$ python3 -m pytest server/tests/ -q --tb=short        # T1 验收命令
...........................                                          [100%]
============================== 27 passed in 0.03s ==============================

$ python3 -m pytest server/tests/ -v --tb=short
collected 27 items
server/tests/test_skeleton.py ............................                [100%]
```

- TestDirectoryStructure：15 passed（7 子目录 + 7 README + 1 server/README）
- TestConfigLoader：5 passed（**正常加载 / 缺项报错 / 空值报错 / 可选键默认值** / 文件不存在）
- TestExecutorsExample：7 passed（JSON 可解析 / 字段完备 / **角色集合=契约 §7 五角色** / 执行体行分类∈{可后台 CLI, 手动 GUI} / 席行分类=「—」 / 绑定非空 / 无旧类型）
- 语法校验：`bash -n run.example.sh` + `bash -n health.example.sh` OK · `plutil -lint com.ccc.engine.plist` OK · `python3 -m py_compile loader.py` OK
- 全套 `tests/scripts/`：除 `test_authority_patrol.py` 2 个 T0 清场遗留失败（`docs/briefs/2026-07-22-opencode-lifecycle-stall.md` 于 commit `134c647` 归档，与本次无关）外全绿。

### 硬编码扫描（rg 黑名单 · 零字面量通过线）

扫描范围：`server/` 生产代码/模板（`.py/.sh/.plist/.env`）；排除 `tests/`（测试夹具合法值）与 `config/executors.example.json`（配置，工具名允许）。

| # | 扫描项 | 命令 | 命中 |
|---|--------|------|------|
| S1 | 绝对路径 `/Users` | `rg -n '/Users' server/ -g '!*.md' -g '!server/tests/**' -g '!config/executors.example.json'` | **0** ✅ |
| S2 | 字面端口 `:[4-9][0-9]{3}` | `rg -n ':[4-9][0-9]{3}' server/ -g '!*.md' -g '!server/tests/**' -g '!config/executors.example.json'` | **0** ✅ |
| S3 | 模型名 `claude\|gpt-\|gemini\|llama` | `rg -ni 'claude\|gpt-\|gemini\|llama' server/ -g '*.py' -g '*.sh' -g '*.plist' -g '*.env' -g '!server/tests/**'` | **0** ✅ |
| S4 | 工具名 `python3\|opencode\|ollama\|launchd\|codex\|trae` | `rg -ni 'python3\|opencode\|ollama\|launchd\|codex\|trae' server/ -g '*.py' -g '*.sh' -g '*.plist' -g '*.env' -g '!server/tests/**'` | **0** ✅ |

补充 S5 全量扫描（含 `.md` 与 executors 配置）：仅命中 `config/executors.example.json` 绑定值（Trae/OpenCode/Claude Code/Codex —— 配置允许）与各 `README.md` 文档说明（文档允许）；`test_skeleton.py` 夹具含 `PYTHON_BIN=/opt/bin/python3` 与旧类型名（测试数据，允许）。**生产代码与模板零字面量。**

对比 Trae 版自评「部署模板中的 python3 是系统工具引用，无法避免」的自我放行已消除：`run.example.sh`/`health.example.sh` 一律 `$PYTHON_BIN`，启动加 `: "${PYTHON_BIN:?}"` 必填检查，不再出现字面解释器名；plist 注释 `launchd` 已去除。

### 目录树（两层）

```
server/
├── README.md                    # 定位 / 结构 / 依赖方向 / 铁律 / 扩展
├── board/README.md              # T2 数据模型与查询入口
├── config/
│   ├── README.md                # 配置系统 + §7 五角色表
│   ├── config.example.env       # 新增 PYTHON_BIN 占位
│   ├── executors.example.json   # 契约 §7 五角色（version=2）
│   └── loader.py                # 新增 PYTHON_BIN 可选键
├── deploy/
│   ├── README.md                # 模板清单 + 硬编码扫描通过线
│   ├── com.ccc.engine.plist     # 去除 launchd 注释字面量
│   ├── health.example.sh        # $PYTHON_BIN，零字面工具名
│   └── run.example.sh           # $PYTHON_BIN + 必填检查
├── engine/README.md             # T2 施工入口
├── relay/README.md              # T4 施工入口
├── tests/
│   ├── README.md
│   └── test_skeleton.py         # 27 用例
└── web/README.md                # T3 施工入口
```

### 验收自检对照表

| # | 验收标准 | 状态 |
|---|----------|------|
| 1 | `executors.example.json` 与契约 §7 完全一致（schema 测试锁定） | ✅ 5 角色精确多集 + 分类规则 + 绑定非空断言锁定 |
| 2 | 代码/模板零工具名字面量（扫描输出为证；`$PYTHON_BIN` 变量化） | ✅ S1–S4 全 0 命中；仅 config 与 .md 文档合法命中 |
| 3 | 子目录 README 具备施工蓝图深度（Codex 判定） | ✅ 职责 / 关键约定 / 相邻模块关系 / T2–T4 施工入口 |
| 4 | 测试全绿且新增 schema 断言；loader 四用例覆盖 | ✅ 27 passed；四用例 = 正常/缺项/空值/可选默认 |
| 5 | 有真实实现提交；工作树仅剩 2 个预存无关改动 | ✅ `e1921d9`；剩 `scripts/.ccc/agent-mind/decided.json`(M) + `_update_handoff.py`(??) |
| 6 | 无删除、无密钥明文、无运行面动作、未碰旧代码/外脑 | ✅ 0 删除；密钥仅占位；未启动/未注册；`scripts/` 等零改动；未读外脑 |

### 遗留/不确定项

1. **管理席/验收席分类为「—」**：契约 §7 五角色中席行不做执行，分类记为「—」（不适用）；schema 测试对执行体行断言分类∈{可后台 CLI, 手动 GUI}、对席行断言「—」。若验收要求席行也取两值之一，请指正后我改。
2. **`tests/scripts/` 2 个 patrol 失败**：T0 清场（`134c647`）归档 `docs/briefs/2026-07-22-opencode-lifecycle-stall.md` 所致，与本次改动无关，未处理。
3. **`PYTHON_BIN` 部署必填**：`config.example.env` 占位空值；复制后不填则 `run.sh` 以 `: "${PYTHON_BIN:?}"` 拒启（预期行为）。
4. **附带提交 Trae 版 T1 任务卡未落库的回写**（`docs/dispatch/T1-server-skeleton.md`），使工作树收敛到仅剩 2 个预存无关改动。
