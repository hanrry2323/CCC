# 任务卡 ccc018 · 知识库条目自动同步脚本（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-09

## 目标

编写知识库条目自动同步脚本：当 `knowledge/domains/projects/` 目录有变更时，自动重建 KB 索引并通知。

## 红线（先看）

1. **只建脚本，不改索引逻辑**：使用现有 `server.kb.mcp_server --reindex` 命令。
2. **零硬编码**：路径从配置或环境变量读取。
3. 若本卡含 `## 人工批注`，执行体必须先读批注。

## 范围

- `scripts/sync-kb-index.sh`：新建自动同步脚本
- 不动：`server/kb/`、`server/engine/`

## 步骤

1. 创建 `scripts/sync-kb-index.sh`：检测 `knowledge/` 目录变更 → 重建索引。
2. 逻辑：`find knowledge/ -newer <last_sync_marker> | head -1` → 有变更则 `python3 -m server.kb.mcp_server --reindex`。
3. 写入同步标记文件 + 日志。
4. 测试：新增知识条目 → 运行脚本 → 索引更新。
5. commit+push 到卡内分支；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `scripts/sync-kb-index.sh` 可执行，检测到变更后自动重建索引
2. 无变更时跳过重建（幂等）
3. 脚本含错误处理（索引重建失败时非零退出）

## 门禁

测试: bash scripts/sync-kb-index.sh --dry-run

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 1. 实现说明
- 编写了自动同步脚本 `scripts/sync-kb-index.sh`。
- 该脚本通过 `find "${KB_DIR}" -path "*/.index" -prune -o -path "*/.*" -prune -o -newer "${MARKER_FILE}" -print` 高效、精确地检测 `knowledge/` 目录中的变更，排除 `.index` 缓存目录及任何隐藏文件，避免了重复重建或无限循环触发。
- 在有文件变更或首次运行时，自动执行 `python3 -m server.kb.mcp_server --reindex` 重建 BM25 索引。
- 索引重建成功后，更新同步标记文件并写入日志。
- 支持 `--dry-run` 模式，仅对变更对账，不改变状态或重建索引。

### 2. 测试结果
- 运行 `bash scripts/sync-kb-index.sh --dry-run` 正确进行首次运行判定。
- 运行 `bash scripts/sync-kb-index.sh` 首次运行时全量重建索引并生成标记文件。
- 再次运行 `bash scripts/sync-kb-index.sh` 准确检测到无变更并自动跳过重建。
- `touch knowledge/domains/projects/seed.md` 后运行，能自动检测到该变动，并触发索引重建。
- 所有 KB 相关单元测试全绿通过 (`57 passed in 2.10s`)。

### 3. push 证据
- 脚本提交 Commit Hash: `e9254c04ee843d048f8610e690873bb4a3ecb344`
- 机审修复提交 Commit Hash: `a04dc39a`

## 机审区

**机审**：2017 机审席 · 日期：2026-08-09

### 机审：通过

### 审查摘要
任务卡 ccc018（知识库条目自动同步脚本）已回写，机审席独立复核。范围仅触及 `scripts/sync-kb-index.sh`（新建）+ 任务卡写回，未动 `server/kb/`、`server/engine/`，符合白名单。红线核验：①使用现有 `python3 -m server.kb.mcp_server --reindex`（`server/kb/mcp_server.py:300` 有 `--reindex` 分支）；②零硬编码——`KB_DIR/MARKER_FILE/LOG_FILE/PYTHON_BIN` 均由环境变量覆盖；③首轮跑通三验收标准 + 门禁 dry-run。

### 发现清单（机审发现 1 项 · P1 就地修复）
- **P1-01（已修复）** 原 `find ... | head -n 1` 在批量新增 KB 条目时触发 SIGPIPE(141)：find 多行输出、head 提前关闭管道，`set -euo pipefail` 下脚本在**重建索引前即中止**（实测 exit 141，索引静默不重建），且覆盖了 on-reindex-fail 的错误路径（error-path exit 1 不可达）。此即该脚本核心用途「批量自动同步」的首使用例，属真实缺陷。

### 修复记录
- 提交 `a04dc39a`（`fix(kb): ccc018 机审发现 P1-01 …`）：改为命令替换一次性收齐 find 输出 + bash 参数展开取首行，find 全程无管道读方提前关闭，杜绝 SIGPIPE。改动仅脚本一处。

### 复审结论（修复后实测，全部通过）
- 批量 500 新增文件 → 重建、exit 0（修复前 exit 141、不重建）
- 无变更 → 幂等跳过、exit 0
- 索引重建失败 → exit 1（错误处理生效）
- 门禁 `bash scripts/sync-kb-index.sh --dry-run` → exit 0
- `bash -n` → syntax OK
- 分支 commit+push 已更新（`fe7172e9..a04dc39a`）

### 机审复核（2017 机审席 · 第 2 轮独立复查）
- 独立取证：`bash -n` 语法 OK；`server/kb/mcp_server.py:300` 确含 `--reindex` 分支，命令属实；范围仅 `scripts/sync-kb-index.sh` + 卡文件，未动 `server/kb` / `server/engine`，无越界。
- 隔离实测（stub python 拦截 reindex）四条核心路径，非信任自述：
  - 首次运行 → 触发重建，exit 0
  - 无变更 → 幂等跳过，exit 0
  - 新增 newer 文件 → 正确触发重建，exit 0（证实 P1-01 修复后能从真实变更触发，非 SIGPIPE 夭折）
  - reindex 失败 → exit 1（错误处理生效）
- P1-01 修复复审：`CHANGED_ALL` 命令替换收齐 find 输出 + 参数展开取首行，无管道读方提前关闭，根治 SIGPIPE；`.index` prune 防自触发（标记在 `.index/` 下已被排除），已由连续幂等跳过实证。
- **本轮无新增发现**，机审：通过。工作区 clean，4 commit 均在卡分支，等待老板「合入批准」。


## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。


## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 禁区：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭
