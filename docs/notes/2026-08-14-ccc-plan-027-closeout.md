# ccc-plan-027 核心流程改造实施收口（2026-08-14）

> 临时笔记：7 天内并入权威（027 方案已含模型定义）。

## 完成内容

027「里程碑 × 方案 × 功能卡(Step) 四级模型」全 8 阶段实施完成（M1 直接开发）：
- 后端：方案↔里程碑双向关联、`## 功能卡` 段解析+convert、自动完成、去旧 Step
- 前端：计划页功能卡清单+节点②确认弹层+里程碑下拉/标签、线路图里程碑写入口、apiPut
- 门禁：validate-plans 状态机（去草案）+ 功能卡段校验
- 测试：8 个新用例，全量 pytest 绿；validate-plans 全绿（存量债收口后）

## 踩坑与结论

1. **`re.sub(r'状态：[^\n]*', ...)` 会吃掉同行的其它字段**（作者/工具等）。
   方案头部是多字段一行（`状态：A · 作者：X · 工具：Y`），用 `[^\n]*` 贪婪到行尾。
   → 改方案状态字段必须用 `re.sub(r'(状态：)([^\s·]+)'`（只匹配状态词，不含分隔符 `·`），
   或用 plans.py 的 `update_plan` / `sync_plan_progress`（内部已是安全正则）。

2. **loader 过滤 platform 卡 → `sync_plan_progress` 对 ccc 方案自动完成失效**。
   `loader` 扫描跳过 `category=platform`（ccc）目录，`cards.index.jsonl` 无 ccc 卡，
   `sync_plan_progress` 查不到 → `closed=0` 不触发自动完成。
   而 `validate-plans.sh` 的卡全关检查是直接 find dispatch 文件（不经 loader），两处数据源不一致。
   → ccc 平台方案的自动完成需手动（或改 loader 对 ccc 卡保留索引）。

3. **自动完成修复存量"卡全关未推进"的正确姿势**：走 `sync_plan_progress`（自动置已完成），
   再 `sync_milestone_progress` 同步里程碑；clw/mx 项目直接生效。

## 存量债收口结果（19 → 0）

- 卡全关未推进 10 方案 → 已完成（clw/mx 自动完成；ccc 手动）
- 已完成但验收未勾 11 方案 → 验收清单勾选
- ccc/020 状态脏值 → 已完成；clearing-report 移出 plans → docs/archive/
- 里程碑状态同步：ccc 交付闸门/集群Worker池/治理门禁/架构扩展 → 已完成
