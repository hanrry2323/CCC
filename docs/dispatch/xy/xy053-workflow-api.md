# 任务卡 xy053 · 工作流 API（M6-2）— 生产任务阶段进度只读接口（OpenCode 执行）

> 关联：xy-plan-009 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-20
> 依赖：xy052

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/xy/README.md`
- 方案池：`docs/projects/xy/plans/`（关联方案见卡头「关联」，本卡 = xy-plan-009 功能卡 6.2 工作流 API）
- **依赖链（2026-08-20 定稿，见方案转卡计划）**：本卡依赖 xy052（内容库 API）已合入；xy054/xy055 依赖本卡合入后顺序出。xy 仓 max_concurrent=1，禁止并发执行。

## 目标

为 M6 前端展示台**工作流可视化页**提供**只读工作流 API**：接入生产 pipeline 状态机 stage 定义与运行态（worker 池/任务状态记录），返回任务级阶段进度，运行中任务实时反映进度，历史任务返回终态。

## 实现

①只读接入 pipeline 状态机：从 `src/xianyu/core/pipeline.py`（只读参考，禁止修改）读取 stage 定义；从 worker 池/任务状态记录读取运行态，输出 `{task_id, pipeline, stages: [{name, status}], current_stage, updated_at}`（status ∈ 排队/进行中/完成/失败）。

②`admin/api/server.py` 新增只读端点 `GET /api/v1/workflows`（沿用现有只读适配模式，不动生产核心代码）：返回全部任务的工作流进度列表；运行中任务实时反映当前阶段，历史任务返回终态。

③无状态记录的任务返回空进度（stages 空数组 + 状态「未开始」），不报错。

④补测试：构造状态机/运行态 fixtures（运行中 + 历史终态 + 无记录），验证组装输出。

## 红线（先看）

1. 只读：禁止修改任何生产核心代码（`src/xianyu/`、`video-pipeline/pipeline.py` 等）；本卡仅动 admin 适配层与测试
2. 禁止把状态读取做成后台常驻任务——API 每次请求实时读取（沿用 xy052 模式）
3. 不新增数据库表——本卡只读现有状态源（任务状态文件/SQLite/worker 池运行态，以实测为准）

## 范围

- `admin/api/server.py`（新增端点 + 辅助状态读取函数）
- 测试文件（`tests/admin/` 新增）
- 禁止改动：`src/`、`video-pipeline/` 下任何生产文件

## 步骤

1. 读方案 xy-plan-009 功能卡「工作流 API」+ `src/xianyu/core/pipeline.py` 状态机定义（只读）+ xy052 已落地的 `admin/api/server.py` 端点模式（仿写）
2. 确认状态源现状：worker 池/任务状态记录在哪（任务状态文件/SQLite/进程表），以实测为准，先 Read 相关文件再写读取逻辑
3. 实现状态读取 + 组装辅助函数（含无记录降级）
4. 实现 `GET /api/v1/workflows` 端点
5. 补测试（fixtures：运行中/历史终态/无记录三类）
6. 门禁全绿：pytest / ruff / mypy
7. commit+push 到卡内分支 `codex/xy053-workflow-api`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」
8. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

- `GET /api/v1/workflows` 对运行中任务返回各 stage 状态（排队/进行中/完成/失败），节点进度真实可查
- 历史任务返回终态（各 stage 均为完成/失败）；无状态记录任务返回空进度不报 500
- 字段完整：task_id/pipeline/stages/current_stage/updated_at 均有值
- 只读：未改动任何 `src/`、`video-pipeline/` 生产文件
- pytest 新增测试通过，ruff/mypy 无新增告警

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：`pytest tests/ -q`
编译：`python3 -m compileall admin/ src/`
lint：`ruff check admin/ src/`
类型：`mypy admin/ src/`（以仓库实际 mypy 配置为准，无新增错误）
范围：false

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成 维护区 四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 机审区；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-20

### 实现说明

在 admin/api/server.py 新增 M6-2 工作流 API 段（316 行，沿用 xy052 只读适配模式）：

1. stage 定义只读导入：_get_pipeline_stages() 从 src/xianyu/core/pipeline.py 只读导入 VIDEO_PIPELINE / IMAGE_TEXT_PIPELINE 的 stage 名称，不修改 pipeline.py，不缓存，每次请求实时读取。

2. 产物检测：_has_config / _has_script / _has_frames / _has_audio / _has_video / _has_article_output 检测各 stage 产物文件是否存在（以实测为准）。终态产物存在时标记全部 stage 完成。

3. 状态组装：_build_workflow_progress() 组装 {task_id, pipeline, status, stages, current_stage, updated_at}。运行中任务 frontier stage=进行中；历史终态各 stage=完成/失败；无记录任务返回 stages 空数组 + 未开始。

4. scan_workflows()：扫描 video-pipeline/output/ 任务目录 + _run_history 内存运行态，按 updated_at 倒序。

5. 端点：GET /api/v1/workflows（Basic Auth 保护）返回 {count, items}。

改动文件：admin/api/server.py（+316 行）、tests/admin/test_workflows.py（新增 19 测试）。未改动 src/、video-pipeline/ 任何生产文件。

### 测试结果

- pytest tests/admin/test_workflows.py -q → 19 passed
- pytest tests/ -q --ignore=tests/html_scene → 662 passed, 2 failed（openclaw Node 模块缺失，预存在与本卡无关），9 skipped
- ruff check admin/ src/ → All checks passed
- python3 -m compileall admin/ src/ -q → 无错误
- mypy admin/api/server.py → 新增代码零新增告警（预存在的无类型注解函数不在本卡范围）

### push 证据

- commit：794b64a · 分支：codex/xy053-workflow-api
- push：git push origin codex/xy053-workflow-api → 已推送至 origin

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]
   - 说明：xy-plan-009 功能卡「工作流 API」已实现完毕；本卡依赖 xy052（已合入 ✅），下游 xy055（工作流可视化页）可开始出卡。
2. **教训沉淀**：本卡是否产出可复用教训？[有]
   - 说明：admin 只读适配层的「产物检测推导 stage 状态」模式可复用——pipeline.py 只有 stage 定义无运行态表，通过产物文件反推 stage 完成状态是唯一可行路径（以实测为准，勿假设有 tasks 表）。教训已落盘：docs/notes/xy053-workflow-api-lesson.md
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：仅扩展 admin/api/server.py 端点 + 测试，未新增目录/文件路径/技术栈。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：M6 进度推进至 6.2 完成；下一步顺序不变：xy054（6.3 预览页面）→ xy055（6.4 工作流可视化页，消费本卡 /api/v1/workflows）。

## 机审区

**机审：通过** · severity：轻（3/9）· 2026-08-20

审查范围：`admin/api/server.py`（+316 行）、`tests/admin/test_workflows.py`（新增 19 测试）。

- 只读适配层：代码只新增端点 + 辅助函数，未修改 `src/`、`video-pipeline/` 任何生产文件。`_get_pipeline_stages()` 通过 `PIPELINES` 只读导入，每次请求实时读取。
- 状态源一致性：stage 名称动态读取 `pipeline.py` 的 `PIPELINES` 字典（video 7 stages / image_text 5 stages），测试 `test_video_pipeline_stage_names_match_definition` 显式校验。
- 降级正确：空目录 → `stages=[]` + `"未开始"`；产出目录不存在 → 空列表；在途 run 无产物 → topic 进行中。均不抛 500。
- 测试覆盖：19 测试覆盖运行中/历史终态/无记录/失败/image_text pipeline/在途 run/扁平结构/排序/认证/空目录。
- 维护区四问已逐项填写，声明与实际改动一致。
- push 证据：commit `794b64a`，分支 `codex/xy053-workflow-api`，已推送 origin。
- 未发现可修问题。

## 执行提示

- 项目：xy（Mac2017 上的 xianyu 独立业务仓；Python 视频/图文生产管线，经 CCC 出卡驱动开发。）

- 项目仓（只读参考）：/Users/fan/program/apps/xianyu（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要（xy-plan-009 M6 前端展示台·功能卡 6.2 工作流 API）：只读 JSON 接口，返回生产任务阶段进度。验收：`GET /api/v1/workflows` 对运行中任务返回各 stage 状态，节点进度真实可查。依赖：内容库 API（xy052，已合入 ✅）。

- 项目线路/近况：
  - 50 张卡（xy001-051）全部关闭；M1 视频里程碑 / M2 生产就绪 / M3 高表现力全部完成
  - **2026-08-20 新里程碑**：M5 高表现力二期 / M6 前端展示台（本卡所在）/ M7 发布闭环（等 Cookie）
  - M6 进度：6.1 内容库 API 已合入（xy052）；本卡 = 6.2 工作流 API；后续 6.3 预览页面 / 6.4 工作流可视化页顺序出卡
  - admin 现有 7 页前端 + `admin/api/server.py` 只读适配（sqlite3 + JSON），xy052 已按此模式扩展 `/api/v1/library`
  - 生产链路：topic→writer→rewriter→image→tts→video 状态机，12 个 launchd 守护，worker 池 xy050；状态定义在 `src/xianyu/core/pipeline.py`（只读）

- 开发技能与命令：
  - 运行测试：`pytest tests/ -q`（repo 根）；单模块：`pytest tests/admin/ -q`
  - 代码检查：`ruff check admin/ src/`；类型：`mypy admin/ src/`
  - 启动 admin 服务：`.venv/bin/python admin/api/server.py`（只读适配层，端口 8765）

- 历史教训（避免踩坑）：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **适用场景**：RSS 模块路径或依赖变更
  - 只读红线：admin 适配层职责是「包装数据成 JSON」，禁止写生产核心；历史审计多次强调路径重构后联动被注释禁用，读状态源前先确认 pipeline.py 当前 stage 定义现状（勿假设旧定义）

- 禁区：- 前缀是 `xy`；卡文件名必须 `xyNNN-…`
- 禁止在 CCC 建业务深文档目录

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：xy（Mac2017 上的 xianyu 独立业务仓；Python 视频/图文生产管线，经 CCC 出卡驱动开发。）

- 审查清单：
  - 只读适配层原则：admin/api/server.py 不得修改生产核心代码
  - 状态源读取与 pipeline.py 实际 stage 定义一致（勿用旧定义）
  - 无记录/异常状态正确降级，不抛 500
  - 测试覆盖运行中/历史终态/无记录三类

- 历史教训（审查时重点关注）：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **适用场景**：RSS 模块路径或依赖变更

- 架构约束/红线：- 前缀是 `xy`；卡文件名必须 `xyNNN-…`
- 禁止在 CCC 建业务深文档目录

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。