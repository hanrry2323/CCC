# Brief F2-2 · 双机版本对齐核对

| 字段 | 值 |
|------|-----|
| brief_id | `F2-20260721-dual-host-version-check` |
| 波次 | F2 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | F2-1 已合入 |
| 模型提示 | **编排窗用 Auto**；若要改 Hub API 字段或 Desktop build 流程 → 停手升级高级并回架构 |

## 1. 目标

提供**一键核对**：M1 Desktop build 与 Mac2017 Hub/Engine commit 是否对齐，对齐 `hub-api-v1` 契约版本。让「靠人工记版本」退场。

## 2. 非目标

- 不自动同步双机版本（只核对，不部署）  
- 不改 Desktop 打包流程  
- 不改 Hub API 字段（只读 `GET /api/desktop/version` 或等价；若不存在则用现有 `/health`/`/api/desktop/projects` 推断）  
- 不接入 CI（先做本地一键命令）  
- 不动 Engine 主循环  

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| hub-api-v1 | **可能有小补** | 若 Hub 已暴露版本/commit，直接用；若无，新增只读 `GET /api/desktop/version` 返回 `{version, commit, hub_api_version}`（只读，无破坏性） |
| 其它 docs | 有 | `docs/deploy/topology.md` 或新 `docs/deploy/dual-host-version-check.md` 写明用法 |

规则：若新增端点，先改 `docs/product/hub-api-v1.md` 再改 Hub 代码。

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| `VERSION` 文件 + `CHANGELOG` | 双机无机器可读对齐口径 |
| `docs/deploy/desktop.md` 人工核对步骤 | 无一键命令 |
| Hub `/api/desktop/projects` 可达性探活 | 不返回 commit / 版本 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `scripts/ccc-dual-host-check.sh`（新）· `scripts/chat_server/routers/desktop.py`（若加 version 端点）· `scripts/chat_server/app.py`（注册路由）· `tests/scripts/test_dual_host_check.py`（新）· `docs/deploy/dual-host-version-check.md`（新）· `docs/product/hub-api-v1.md`（若加端点） | 改 Desktop、改 Engine 主循环、改 transfer/flow 契约 |
| 过桥 | 按需 | 仅当加 version 端点时碰 `chat_server/` | |
| 壳 | 否 | — | |
| 架构 | 验收 | 本 brief · `hub-api-v1` 审阅 | 代写实现 |

## 6. 行为规格

1. 新命令 `bash scripts/ccc-dual-host-check.sh`：  
   - SSH/HTTP 探 2017 Hub：取 `version` / `commit` / `hub_api_version`  
   - 读本机 `VERSION` + `git rev-parse HEAD`（或 Desktop build 元数据若易取）  
   - 输出三行：`M1: <ver> <commit>` / `2017: <ver> <commit> <hub_api>` / `aligned: yes/no` + 不一致项  
   - 非零退出当：Hub 不可达、版本不一致、`hub_api_version` 不在客户端支持集  
2. 若 Hub 无版本端点：新增 `GET /api/desktop/version` 只读端点，返回 `{version, commit, hub_api_version="v1"}`；先改 `hub-api-v1.md` 再改 Hub。  
3. 客户端支持集：本机硬编码 `["v1"]`；未来 v2 再扩。  
4. 文档 `docs/deploy/dual-host-version-check.md`：用法 + 失败处置（拉版本/重启/联系运维）。  

## 7. 验收清单

- [ ] `bash scripts/ccc-dual-host-check.sh` 在双机可达时输出三行 + aligned 判定
- [ ] Hub 不可达时非零退出 + 明确错误
- [ ] 版本不一致时非零退出 + 列出不一致项
- [ ] 若加端点：`hub-api-v1.md` 已先改；端点只读
- [ ] `pytest tests/scripts/test_dual_host_check.py` 绿
- [ ] `pytest tests/scripts/ -q` 仍绿
- [ ] 白名单外无改动

## 8. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 编排 | | | |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | （待填） |
| 缺口 | |
| 验收日 | |
