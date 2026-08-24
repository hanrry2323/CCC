# 任务卡 ccc076 · observer 测试隔离修复——全量 pytest 不再污染检出（DSH 执行）

> 关联：无方案（2026-08-24 地基加固 · 总调度直派） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

> 状态校正（2026-08-24 · 受老板一次性授权，总调度执行）：工程已交付且分支就绪，磁盘卡由「待分派」如实校正为「已回写」以终结重派循环；合入归环节②。

## 目标

server/tests/test_observer.py::test_run_observer_output 隔离不全：只 mock 三个 loader，
run_observer 内部 scan_findings(cfg, PROJECT_ROOT) 吃真实仓库根、write_roadmap_draft 未被
mock → 任何检出跑全量 pytest 都会向所在仓 docs/projects/mx/roadmap.md 追加巡查行
（ccc068 三次污染实证；ccc074 调查报告主链结论）。

## 实现

白名单：server/tests/test_observer.py。

1. 为 write_roadmap_draft 补 mock（patch 到测试内 tmp 路径或 MagicMock），并断言其被调用参数落在 tmp 内；
2. scan_findings 的仓库根注入 tmp 根（消除对真实 PROJECT_ROOT 的读依赖亦可，但写路径必须隔离）；
3. 新增守护断言：用例结束后 git status --porcelain docs/projects/mx/roadmap.md 为空（在仓内运行时）。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 只改测试文件的 mock/断言；禁改 observer.py 与 roadmap.py 生产逻辑（行为治理另卡 ccc077）。
3. 禁写机审区/验收区/置已关闭。

## 步骤

1. Read 本卡全文与相关代码现状。
2. 按实现节修改；自测运行下方门禁命令，退出码必须=0。
3. commit+push 到本分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。职责终点=已回写，合入归环节②。

## 验收标准

1. 门禁命令真实退出码=0（wrapper 证据日志为准）。
2. 白名单外零触碰。
3. 卡头=已回写；维护区四问非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/ccc076 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_observer.py -q

## 回写区

**回写时间**：2026-08-24 · 执行体：DSH（ox-alpha）

**实现说明**：
- 白名单内仅 `server/tests/test_observer.py`（62+/6-），生产代码零改动。
- 卡实现节三点全落地：① `test_run_observer_output` 为 `write_roadmap_draft` 补 tmp 绑定替身
 （外层 patch `server.board.roadmap._repo_root`→tmp，替身内断言每次调用写目标
  `is_relative_to(tmp_path)`）；② `observer.PROJECT_ROOT/REPO_ROOT` 注入 tmp 根，
  `scan_findings(cfg, PROJECT_ROOT)`/`_auto_fix_deterministic`/docs-notes 落点全部随迁，
  并加隔离断言 `summary['findings'] == []`；③ 用例末新增守护断言：
  `git status --porcelain -- docs/projects/mx/roadmap.md` 为空（在仓内运行时生效，非 git 环境自动跳过）。
- **自测中发现同文件第二污染点并一并加固**：`test_run_observer_writes_draft_for_consistency`
  已 mock write_roadmap_draft 但未注根，run_observer 尾段 `notes_dir = PROJECT_ROOT/'docs'/'notes'`
  把巡查报告写进真实仓（实证：报告 mtime 2026-08-24 14:33:57 变更、内容即该测试两个 mock findings；
  该路径被 `.gitignore:178` 覆盖、porcelain 沉默，属隐形污染）→ 同样注入 tmp 根后指纹不再变化。

**自测结果**：
- 门禁：`python3 -m pytest server/tests/test_observer.py -q` → **26 passed，退出码 0**（多次复跑一致）。
- 全量回归（历史污染触发场景）：`python3 -m pytest server/tests -q` → 1175 条跑毕后指纹对照：
  `docs/projects/mx/roadmap.md` mtime 不变、该路径 porcelain 0 行；
  `docs/notes/2026-08-24-ccc-patrol.md` mtime 不变（第二污染点修复实证）；
  全仓 porcelain 除本测试文件改动外零新增。
- 套件存量失败与本案无关：test_brain_kb/test_brain_stream/test_http_api 会话流测试失败，
  stash 掉本次改动后复跑同样失败（502≠503，中继环境问题）——pre-existing，非本卡引入。

**push 证据**：
- 分支 `codex/ccc076-observer-test-isolation`（基点=origin/main@54de3ce0，push 前 fetch 复核无需 rebase）。
- commit：`efd02cc5e` test(ccc076): observer 测试隔离修复——run_observer 全链路注入 tmp 根。
- push 后核验：`git ls-remote origin refs/heads/codex/ccc076-observer-test-isolation`
  → `efd02cc5e191fce93f5674febf2d83e2c303d4b3` 与本地 HEAD 一致。

**白名单外附带发现（未触碰，供后续卡参考）**：
全量 pytest 会生成未跟踪文件 `docs/archive/legacy-t-cards/cards.index.jsonl`
（pytest 下 `get_index_path(dispatch_dir)` 返回 `<dir>/cards.index.jsonl`，
刷新者指向 test_board_loader.py 等针对真实归档目录跑 loader 的用例）。
本卡测试不触它（单文件门禁前后 mtime 对照不变）；该文件在 HEAD 与主仓均未跟踪。建议另开卡治理。

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：[否]。地基加固直派卡无关联方案。
2. **教训沉淀**：[无]
   - 说明：[无]。机制教训随卡记录即可。
3. **档案/README**：[否]
   - 说明：[否]。
4. **线路图**：[否]
   - 说明：[否]。
