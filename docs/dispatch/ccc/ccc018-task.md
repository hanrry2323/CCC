# 任务卡 ccc018 · 知识库条目自动同步脚本（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

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
