# 任务卡 ccc082 · 并发机审风暴防线跨 DATA_DIR 验证与加固（DSH 执行）

> 关联：环节②交接指令(S116-01)卡1 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

核验防双审机制 `_audit_marker_alive`（server/engine/main.py）在双 engine 使用不同 DATA_DIR（即不同 log_dir）时是否仍能挡住并发机审风暴（复现 ccc078 33 实例场景的等价小规模模型）；有缺口即加固，无缺口则补探针断言固化防线。

## 红线

- 白名单：server/engine/main.py（marker 机制相关函数）、server/tests/ 新增或修改测试。
- 实验只用临时目录 DATA_DIR（tmp_path），禁止触碰生产 ~/.ccc/data 与生产 engine.lock；禁止启动第二个生产 engine 进程。
- 禁改 OPENCODE_GO_API_KEY。

## 范围

- 复现模型：同机两个进程各自 DATA_DIR_A/B 对同一 work_id 各自 claim/alive 判定——分析共享面（log_dir 不同则标记互不可见是否导致双审并行）。
- 若确认穿透：给出最小加固（如全局锁文件/注册表级 in-flight 登记），保持向后兼容。
- 若无穿透：补一条「跨 DATA_DIR 双 claim」探针单测固化当前行为语义并文档化边界。

## 步骤

1. 读 _audit_marker_alive/_claim_running_marker/_write_running_marker 与 audit_pool.alive_ids 防线，画共享面。
2. tmp 双目录实验（pytest 形态），记录双审与否及证据。
3. 按结论实施加固或固化断言。

## 验收标准

- [ ] 结论明确（穿透/不穿透）且附实验命令与输出
- [ ] 新增至少一条回归单测覆盖该场景
- [ ] 生产文件零触碰（git status 干净除白名单）

## 回写要求

- 回写区写明实验设计、结果、diff 要旨；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）
