# program 整理清单（不自动挪目录）

> Phase 4 产出：**清单先行**。物理移动 `~/program` 需你确认后再执行，避免误伤。

## 原则

1. **有价值、要跑 CCC 流水线的仓** → 登记进 Board / Hub workspaces（看板可见）。
2. **归档 / 参考 / 一次性实验** → 移到约定归档区（例如 `~/program/archive/`），**不要**删未备份仓。
3. **HP / qx-map / 业务仓代码不并入 CCC 仓库**；Hub 运维只做探针与深链。

## 建议分类

| 类别 | 处理 | 示例（按本机习惯调整） |
|------|------|------------------------|
| CCC 本体 | 保持 `~/program/CCC`，Hub/Engine 主仓 | CCC |
| 活跃业务 | 注册 workspace，进看板 | qb、xianyu、clawmed-ccc |
| 生产部署目标 | 只在运维「部署视角」看状态；代码可在 feiniu | medio-0 on feiniu |
| 知识库 | 独立 `~/program/hp`；Hub 只 kb-health | HP proxy/store/bridge |
| 地图/想法 | qx-map 想法折进 Hub 运维，不并码 | `/Users/apple/qx-map` |
| 编译站源码 | Mac2017 同步副本，M1 为源 | Medio-0 |
| 冷归档 | 确认后移 `archive/`，从 workspaces 注销 | 长期不动的 fork |

## 注册检查清单（执行归档前）

- [ ] Board `workspaces` 是否只含仍要跑流水线的路径
- [ ] `.ccc/infrastructure.md` 端口与真实服务一致
- [ ] 运维页 `#/ops` → Diff 工作区无「幽灵路径」
- [ ] 大体积 `node_modules` / `target` / 数据集是否已在 `.gitignore`，避免日审噪声
- [ ] 确认备份（Time Machine / 远程）后再 `mv`

## 明确不做（本清单阶段）

- 未确认前批量 `mv ~/program/*`
- 把 HP / qx-map 合并进 CCC git
- 自动删除目录

## 确认后的建议步骤（人工）

1. 在本文件勾选要归档的目录列表（自行追加一行/仓）。
2. `mkdir -p ~/program/archive && mv <path> ~/program/archive/`
3. 从 Board workspace 配置移除对应项；刷新 Hub 项目列表。
4. 更新 `.ccc/infrastructure.md`「项目状态」表。
