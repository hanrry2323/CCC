# 实验 C10 · python flavor 实测

- **状态**：✅ 完成（源码级：不可用）
- **批次**：B3 模式
- **环境**：源码
- **日期**：2026-08-16

## 结论

**python flavor 在已发布的 worker-thread 后端不可用**——`WorkerThreadCodeRuntime.language` 硬编码 `"typescript"`，config schema 无 language 项，python 后端未实现。python flavor 只存在于 schema/SDK 提示层（`RUN_CODE_FLAVORS.python`、`renderToolsSdkPy`），属「设计意图 vs 已实现」的缺口。

## 证据

- `dsh-code-runtime-worker-thread/lib/index.js:655`：`language = "typescript";`（硬编码字段）
- `isolation = "worker-thread";`（:656）
- Config schema（:652-657）：仅 `computeMs`/`maxWallMs`/`maxOutputBytes`/`maxOldGenerationSizeMb`，**无 language**
- `dsh-code-runtime/lib/index.js:59-65`：语言可移植 seam 注释——「Extending the seam with a new language means widening...」= 有扩展设计，但 shipped 后端只有 TS

## 结论细节

- 想切 python：schemas() 侧 `resolveFlavor(peekRuntime)` 会按 runtime.language 选 flavor；但 worker-thread runtime 恒为 typescript → 模型永远看到 TS flavor，python 永远到不了。
- 若硬切 language=python，`resolveFlavor` 对无 flavor 条目会显式 throw（fail-closed）——同样到不了 python 执行。

## 未覆盖

- 未来 python 后端出现时（源码注释说「第二个后端出现时再处理」），本结论需重测。当前为定论。

## 风险 / 对 CCC 借鉴的影响

- DSH 当前 code-run 实际只支持 TypeScript；CCC 若要用 Python 编排，不能靠 DSH 内置，得另配（ccc-run-inline 已支持 node/py 内存脚本，可作补充）。
- flavor 层与后端不一致是「半成品能力」案例：schema 说有、运行没有，评测要落到执行层看。
