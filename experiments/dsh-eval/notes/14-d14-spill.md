# 实验 D14 · spill 在 web profile 是否生效

- **状态**：✅ 完成（当前部署未启用）
- **批次**：B4 会话
- **环境**：配置 + 源码
- **日期**：2026-08-16

## 结论

**spill 在当前部署（web profile）未启用**——`settings.yaml`、`web/cordis.patch.yml`、`web/cordis.yml` 均无 `maxInlineBytes`，而 `dsh-spill-policy` 未配置 `maxInlineBytes` 即注册 no-op。工具超长结果仍内联进上下文，不会外置到私有文件。

## 证据

- 三处配置 grep `maxInlineBytes`/`spill` 均 False
- `dsh-spill-policy/lib/index.js:23`：「Omitted `maxInlineBytes` ⇒ the plugin registers nothing (a no-op)」
- Config schema：`z.object({ maxInlineBytes: z.number() })`（:52，配了才生效）

## 结论细节

- spill 是「可选项」：配 `maxInlineBytes` 才把超长工具结果外置（私有文件 + 头尾预览 + 路径提示）。
- 当前 web 部署未配 → 所有工具结果内联。长输出工具（grep 大量匹配）会占上下文。
- 与 pruner/compaction 的关系：spill 是第三道防线，当前未启用 → 实际只有 pruner + compaction 两道。

## 风险 / 对 CCC 借鉴的影响

- 若 DSH 跑长输出任务（审计扫描/大文件 grep），建议启用 spill（配 maxInlineBytes）防上下文膨胀。
- 「可选防线默认关」是部署注意点——评测结论要区分「机制有」与「部署开了」。
