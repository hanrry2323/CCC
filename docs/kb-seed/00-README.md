# CCC 知识种子包 · T9

> **状态：史 / 废弃手维（2026-08-06）。** 运行时项目清单以 [`../projects/registry.yaml`](../projects/registry.yaml) 为唯一事实源；live seed 在仓根 [`../../knowledge/seed/`](../../knowledge/seed/)。  
> **勿**继续手改本目录当作第二份真值。见 [`../DOC-PROTOCOL.md`](../DOC-PROTOCOL.md)。
>
> 用途（历史）：供 T10（CCC 知识库初始化）一次性移植进 CCC 自建知识库。
> 来源：外脑权威源（qx-map）提炼，只读不修改。
> 移植后 CCC 独立运行，零外脑依赖（D3 契约）。
> 日期：2026-08-02 · 关联：INT-120（CCC 重构）· P5 知识移植

## 结构

| 文件 | 内容 | 权威源 |
|------|------|--------|
| `01-nodes-paths.json` | 机器节点、IP、SSH、路径、服务 | `cluster/path-authority.md` + `cluster/cluster.json` |
| `02-project-metadata.json` | 项目元数据（位置、性质、访问方式） | `cluster/path-authority.md` + `cluster/cluster.json` + `projects/manifest.md` |
| `03-key-decisions.json` | 关键决策摘要 | `__archive__/decisions/` + hp-kb `/codex/topics/` |
| `04-lessons.json` | 教训清单 | `__archive__/lessons/` + CCC `docs/lessons.md` + hp-kb `/codex/topics/` |

## 来源追溯

所有数据均来自 qx-map 权威源（`/Users/apple/qx-map/`），只读提炼，零修改。

## 安全声明

本种子包不含：
- 密钥 / API token / 密码
- 运行面敏感信息（端口仅含服务名，不含实时状态）
- 运行面配置（env / .env 内容）