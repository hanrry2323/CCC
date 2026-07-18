# Plan: engine-phase-parallel-dispatch — 无依赖 phase 并行执行

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

Engine 串行执行 phase1 → phase2 → phase3，即使 phase 之间无 `depends_on` 关系也顺序执行。多 phase 项目（如 cockpit-v0303 拆分）执行时间 = phase 时长之和。

## 范围

- **目标**: Engine 检测无依赖 phase 时并行执行（max_workers=2），缩短多 phase 任务总耗时
- **只改文件**: `scripts/ccc-engine.py`

## 改动

1. `_resolve_phase_dependencies()` 返回分组（可并行组），每组内 phase 无相互依赖
2. 使用 `concurrent.futures.ThreadPoolExecutor(max_workers=2)` 并行执行可并行组
3. 各组间仍串行（前一组合部完成才执行下一组）
4. 日志标记并行 phase: "[parallel] phase-2 + phase-3 running"

## 验收

- [并行] 3 phase 无依赖时，日志出现 "[parallel]" 标记
- [顺序] 有 depends_on 的 phase 不并行
- [串行] 并行组合部完成才执行下一组
- [回滚] 并行失败时 fallback 回串行模式（log warning）
