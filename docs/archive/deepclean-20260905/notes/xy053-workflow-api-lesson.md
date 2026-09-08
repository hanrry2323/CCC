# 教训：admin 只读适配层——产物检测推导 stage 状态（xy053）

> 2026-08-20 · 来源：xy053 工作流 API 卡 · 适用：xy admin 只读适配层扩展

## 背景

M6-2 工作流 API 需要返回生产任务各 stage 状态，但 pipeline.py 只有 stage 定义、无运行态表。

## 结论

**以实测为准，勿假设有 tasks 表**——通过产物文件反推 stage 完成状态是唯一可行路径：

- stage 定义：从 `src/xianyu/core/pipeline.py` 的 `PIPELINES` 字典只读导入（实时读取，不缓存）
- 运行态：`_run_history` 内存运行态 + `video-pipeline/output/` 任务目录产物文件（final.mp4/script.json 等）反推
- 终态判定：产物存在 → 对应 stage 完成；无产物 → 未开始；在途 run 无产物 → 首 stage 进行中

## 复用要点

1. 扩展只读 API 前先确认状态源现状（文件/SQLite/内存），再写读取逻辑
2. 产物检测函数（`_has_config/_has_script/_has_frames/...`）模式可复制到其他只读端点
3. 每次请求实时读取，禁止后台常驻轮询