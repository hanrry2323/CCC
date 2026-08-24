# 任务卡 docs/dispatch/ccc/ccc074 · ccc074 · mx/roadmap 周期写入者定位调查（DSH 执行）

> 关联：无方案（2026-08-24 债务清偿 · 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

多个 worktree 反复出现 docs/projects/mx/roadmap.md 未提交改动（22 行 Loop 巡查行样式），三次污染出卡现场（patch 留档 /tmp/ccc068-stray-mx-roadmap.patch*）。定位写入者并产出治理建议，不实施修复。

## 实现

白名单：docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md（新建调查报告）。

线索起点：server/engine/observer.py 与 server/board/roadmap.py 含「巡查」字样；嫌疑面=engine observer 巡查、board-scheduler、patrol 脚本。方法建议：mtime 轮询+lsof 交叉、launchd 任务表、patrol 日志时间戳比对。

报告必填：写入进程命令行与父链、触发周期、写入内容生成点（file:line）、是否属预期设计、治理建议（停止/改道/加锁）三选一及理由。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 只读取证；报告文件为唯一产出。
3. 禁写机审区/验收区/置已关闭。

## 步骤

1. Read 本卡全文与相关代码/文件现状。
2. 按实现节修改；自测运行下方门禁命令，退出码必须=0。
3. commit+push 到本分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。

## 验收标准

1. 门禁命令真实退出码=0（wrapper 证据日志为准）。
2. 白名单外零触碰。
3. 卡头=已回写；维护区四问非占位。

## 门禁

测试：test -s docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md && grep -qE "写入者|结论" docs/notes/2026-08-24-ccc-mx-roadmap-writer-findings.md && echo OK

## 回写区

（执行体回写）

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：[否]。债务清偿直派卡无关联方案。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：[无]。机制性教训已在同期 notes 记录。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：[否]。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：[否]。
