# ⚠️ 已退役 / DEPRECATED

> **本文件是 CCC 框架自身的旧 AGENTS.md，已合并进 [`CLAUDE.md`](./CLAUDE.md)，请改读那个。**
>
> **新项目模板**：见 [`templates/AGENTS.md`](./templates/AGENTS.md)（`ccc init` 生成新项目时使用的模板）

归档原因：
- 早期版本架构（Codex = 两 Agent 同名，概念混淆），已过时。当前名称 "Codex Claude Collaboration" 指 Planner(任意LLM) + Executor(Claude) + Verifier(Claude) 三角色协作。
- 内容已被新版 `CLAUDE.md` 完全覆盖（三阶段管线、目录布局、红线、文件桥接）
- 新增了项目隔离规范、verifier 角色、执行方式术语统一、验收口径修正等

历史保留：2026-06-30 由 qxo-CC 合并归档

---

## 历史内容（仅供查阅，不再生效）

> Codex 规划 → Codex 长任务自主执行 → Codex 验收。全文件桥接，零对话回合。

<details>
<summary>点击展开历史内容</summary>

三阶段管线、目录布局、Codex 核心命令、文件桥接协议（Plan/Phases/Report/Verdict）、参考来源、红线。

完整历史版本见 git history。
</details>