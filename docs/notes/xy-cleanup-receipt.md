# 回执 · xy 历史整理（改道令①-④）· 2026-09-13

> 主脑/执行席：CCC 只读整理执行席 · 回执落：`docs/notes/xy-cleanup-receipt.md`（2017 仓）
> 前置：改道令 09-13「xy 纳回前必须历史整理完，不得带账纳回」。本回执四步对账只读完成；分支只列清单不删。
> 命令环境：worktree `codex/xy-cleanup`（主脑已建位），动手前 `git status --short` 仅 `?? .venv-hub`（脏数=0，非本席产物）。
> 在途核对：xy062/xy063 已归档于 CCC `docs/archive/ccc-tasks/xy/`（各 10 张含这两张）→ 本节注明「已收编」，不重复动作。

## ① 卡片对账（10 张归档卡 vs 实际结局）

| 卡 | 归档状态 | 业务仓实际结局 | 判定 | 出处 |
|----|---------|---------------|------|------|
| xy060 | 已关闭 | M6.1 内容库 API 合入 main | 对得上 | merge `dac32c2` |
| xy061 | 已关闭 | M6.2 工作流 API 修复合入 main | 对得上 | merge `5b18d27` |
| xy062 | 作废（生产首跑已跑通，质量缺口转 xy063） | 4 commit 未在 main；控制字符修复在 main 等效落地 | 部分对得上（见下） | 分支 ahead 4；`llm.py:94` |
| xy063 | 作废（HyperFrames 真入口未达成） | 分支 tip 已在 main；`324a3ed`/`77ba40e` 合入 | 对得上 | `merge-base` ancestor=YES |
| xy064 | 作废 | 修复 `f2ad113` 已合入 main | 部分对得上（见下） | merge `f2ad113` 等 14 commit |
| xy065 | 已关闭 | 文案 3456 通道合入 main | 对得上 | merge `cce5340` |
| xy066 | 已关闭 | 配图语义选图合入 main | 对得上 | merge `5fc1b1e` |
| xy067 | 已关闭 | 2 commit（仅 .ccc-result.md 取证）未在 main；无业务代码改动 | 对得上 | 分支 ahead 2 |
| xy068 | 已关闭 | 生产 video 接 HyperFrames 合入 main | 对得上 | merge `2a9c438` |
| xy069 | 已关闭 | 字数自校正合入 main | 对得上 | merge `cb76fb4` |

### 差异注记

- **xy062（部分对得上）**：卡标「作废」且验收结论「不通过」（图文用占位图、视频回退 PIL）。但分支 4 个代码 commit（`7e3d511`/`0c1a080`/`22b89e4`/`dac7926`，自初始化/超时/控制字符 json）**未在 main**；main 头三个提交（`5544e25` 空响应重试、`f1b64f2` rewriter timeout 60→150s、`dc28219` WorkerRegistry.discover）为**同源生产修复翻版**，控制字符剥离逻辑 `llm.py:88-100` 已在 main。→ 卡结论「未达成」与 main 现行修复部分重叠，属「作废但其修复实质被后续卡/翻版吸收」，标注 **部分对得上**。
- **xy064（部分对得上）**：卡标「作废」但修复 commit 已在 main 合入（14 commit，`f2ad113` 等）；机审两次「不通过」后逐轮修复均落 main。卡状态与其修复实际落地相悖 → 标注 **部分对得上**（状态标作废、成果实合入）。

## ② plans 定级重核（10 篇）

| 方案 | 自标状态 | 业务仓实况 | 判定 |
|------|---------|-----------|------|
| 001 视频里程碑 | 已完成 31/31 | 31 张关联卡全部已关闭合入 | **现行** |
| 002 测试基线绿 | 已完成 4/4 | xy033-036 已合入 | **现行** |
| 003 断裂点修复 | 已完成 3/3 | xy037-039 已合入 | **现行** |
| 004 运行方式重建 | 已完成 3/3 | xy049-051 已合入 | **现行** |
| 005 视觉模板库 | 已完成 3/3 | xy040-042 已合入 | **现行** |
| 006 质量量化加固 | 已完成 3/3 | xy043-045 已合入 | **现行** |
| 007 渲染引擎升级 | 已完成 3/3 | xy046-048 已合入 | **现行** |
| 008 视频高表现力二期 | 部分执行 2/2 | xy059/064/067/065/066/068/069 均在 main | **史实**（M5 已落地） |
| 009 前端展示台 | 部分执行 5/5 | xy060/061 合入，6.2-6.4 页面未出 | **现行**（剩余 6.3/6.4） |
| 010 发布闭环 | 待排期 | 无产出（M7 Cookie 前置） | **现行**（冻结，未动） |

**判定口径（G4）**：旧 plans（001-007）自标「已完成」与业务仓合入实况一致，且 Build/Produce 双线、M7 冻结演进已在 README「线路/近况」更新，未改 plans 文件本身 → 保留「现行」，不标史实。008 自标「部分执行」但 7 张关联卡全部已合入 main → **史实**（M5 已落地）。009 关联卡 xy060/061 合入、6.2 已有修复，仅 6.3/6.4 展示页面未出 → **现行**。010 无产出、M7 冻结 → **现行（冻结）**。全部无「待核」。

## ③ 分支清理清单（xianyu 业务仓 8 条远端 codex/xy*）

判定依据：`merge-base --is-ancestor 分支tip main`；ahead 数；与 main 头比对。

| 远端分支 | 状态 | ahead | 建议 |
|---------|------|------|------|
| codex/xy062-real-content-video | 作废；tip 非 main 祖先 | 4（未合入） | **删除**（作废且成果已被翻版/后续卡吸收） |
| codex/xy063-build-image-hyperframes | tip=main 祖先 | 0 | **删除** |
| codex/xy064-video-hyperframes-real | tip=main 祖先 | 0 | **删除** |
| codex/xy065-copywriting-3456 | tip=main 祖先 | 0 | **删除** |
| codex/xy066-image-semantic | tip=main 祖先 | 0 | **删除** |
| codex/xy067-hyperframes-acceptance | 已关闭；tip 非 main 祖先 | 2（仅 .ccc-result.md，无业务代码） | **删除**（无代码价值） |
| codex/xy068-video-hyperframes | tip=main 祖先 | 0 | **删除** |
| codex/xy069-copy-length-fix | tip=main 祖先 | 0 | **删除** |

**保留/归档**：无。本地同名分支 8 条（`codex/xy062-…` 至 `codex/xy069-…`，`git branch` 显示 062/063 无 `+`，其余已附有内容）→ 远端删除后可顺手清本地，报主脑核。

**CCC 仓远端 codex/xy***：0 条（已清，无异常）。

## ④ registry/README 对表

**registry xy 行（`docs/projects/registry.yaml`）**：

```yaml
- prefix: xy
  id: xianyu
  name: xianyu
  display: xianyu
  location: mac2017-apps
  paths:
    m1: null
    mac2017: /Users/fan/program/apps/xianyu
  isolation: { max_concurrent: 1 }
  taskable: true
  forbidden: false
  status: active
  dossier: docs/projects/xy/README.md
  role: 独立业务仓（经 CCC 出卡）
```

**结论：一致，无需变更。**
- `paths.mac2017`（`registry.yaml:81`）`/Users/fan/program/apps/xianyu` 存在且为 git 仓库（origin=github.com:hanrry2323/xianyu.git）。
- `taskable: true` / `status: active` / `isolation.max_concurrent: 1` 均符合现状。

**README（`docs/projects/xy/README.md`）**：路径表「Mac2017 `/Users/fan/program/apps/xianyu`」、前缀 `xy`、taskable「是」均与 registry 一致；「线路/近况」Build/Produce 双线、M7 Cookie 前置冻结的描述与业务仓 main 头（video 生产真动效、rewriter timeout 150s）吻合。**无版本落差。**

## 结论

xy 旧账对清：10 张归档卡全部已收编（含 xy062/xy063 作废卡），plans 10 篇定级完成（8 现行 / 1 史实 / 0 待核），业务仓 8 条远端 codex/xy* 分支全部建议删除（1 条作废分支 commit 未合入但成果已翻版吸收），registry/README 与实况一致。**可进入 L1-E 纳回。**

> 待主脑核点：xy062（作废但修复翻版吸收）与 xy064（状态作废但修复实合入）两卡状态张力，纳回时以「作废、成果已合入」口径标注。
