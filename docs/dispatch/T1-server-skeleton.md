# 任务卡 T1 · P2-1 服务端骨架 + 配置化基线

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1 · 管理席：Codex
> 执行体：Trae（手动）· 验收：Codex · 状态：待分派 · 日期：2026-08-02

## P2 拆解（供参考，本卡只做 T1）

| 卡 | 内容 | 依赖 | 并行性 |
|----|------|------|--------|
| T1 | 服务端骨架 + 配置化基线（本卡） | 无 | 串行起点 |
| T2 | Engine 薄驱动核心（发单/派发/收单/状态更新/注册表读取） | T1 | 主链 |
| T3 | 任务看板前端（实时/7天/项目分类 + 线路图占位） | T1 | 可与 T2 并行（目录 web/ 与 engine/ 不相交；需 Trae 双窗口） |
| T4 | CCC 自带中转站部署 + 调用方切换 | T1+T2 | 涉及运行面，最后单独做 |

## 目标

在 CCC 仓内建立新服务端合体（2017 单端）的骨架：`engine/`、`board/`、`web/`、`relay/`、`config/`、`deploy/`、`tests/`，全部配置化、零硬编码，为 P2 后续开发提供干净基座。本卡只写骨架与模板，**不部署、不碰 2017 运行面**。

## 红线（先看）

1. **不删除、不修改任何既有文件**；只新增 `server/` 目录；本任务卡的状态字段回写除外。
2. 不碰旧代码：`scripts/`、`app/`、`desktop/`、`lib/`、`db/` 零改动。
3. 不落密钥：密钥/令牌只允许占位引用（如 `$RELAY_UPSTREAM_KEY`），禁止明文。
4. 不碰运行面：不启动服务、不注册 launchd、不 ssh 改动 2017；只产模板与脚本文件。
5. 杜绝硬编码：代码与模板中不得出现工具名、绝对路径、端口号、模型名、上游地址的字面量；一律走环境变量/配置引用（端口等在 `config.example.env` 占位）。**唯一例外：执行体注册表配置文件允许出现工具名**（它是配置，不是代码）。
6. 不读不写 qx-map / HP 知识库。

## 范围

- 仓库：`/Users/apple/program/CCC/`
- 新增：`server/` 目录树（可自由设计内部结构）
- 允许修改：仅本任务卡（`docs/dispatch/T1-server-skeleton.md`）

## 步骤

1. 建立 `server/` 目录骨架：`engine/`、`board/`、`web/`、`relay/`、`config/`、`deploy/`、`tests/`，每目录放 `README.md` 一句话说明职责。
2. 配置系统：
   - `server/config/config.example.env`：全部运行参数占位——端口（engine/board/web/relay）、数据与日志路径、模型出口上游与密钥引用、执行体注册表路径。
   - `server/config/loader.py`：env 加载器，含缺失项报错；测试覆盖正常加载与缺项报错两个用例。
3. 执行体注册表：`server/config/executors.example.json`——字段与契约 §7 一致（角色/分类/当前绑定/备注），分类值只允许 `可后台 CLI` / `手动 GUI`。
4. 进程编排骨架：`server/deploy/` 提供 launchd plist 模板、`run.example.sh`（占位启动命令）、`health.example.sh`（输出 JSON 的健康检查骨架）。
5. 冒烟测试：`server/tests/test_skeleton.py`——断言目录结构存在、config 加载（正常 + 缺项报错）、executors 示例 JSON 可解析且分类合法。
6. `server/README.md`：说明结构、如何配置、如何跑测试、如何扩展。
7. 硬编码自查：用 rg 黑名单扫描（绝对路径 `/Users`、字面端口 `:4[0-9]{3}`、模型名、工具名出现在代码而非配置），把扫描命令与结果写入回写区。

## 验收标准（Codex 按此验收）

1. `server/` 骨架完整，每目录有 README 一句话职责。
2. config 加载测试通过（正常 + 缺项报错）。
3. `executors.example.json` 合法，字段与契约 §7 一致，分类值合法。
4. 代码与模板零硬编码（黑名单扫描通过；工具名只允许出现在 executors 配置与 README 文档）。
5. 旧代码目录零改动（`git status` 只有新增文件与本文档修改）。
6. 无删除；无密钥明文；无运行面动作。
7. 测试可跑通：`python3 -m pytest server/tests/ -q`。

## 回写要求

- 回写区填写：commit hash、测试输出摘要、硬编码扫描结果、目录树（两层）、遗留/不确定项。
- 状态：`执行中 → 已回写`。

## 回写区

（执行体回写）
