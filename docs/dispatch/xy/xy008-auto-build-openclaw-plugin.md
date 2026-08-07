# 任务卡 xy008 · 系统集成：自动构建openclaw-plugin与依赖补齐（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

在 xianyu 的 `openclaw-plugin/` 子项目中，实现自动化环境安装、依赖补齐与 TypeScript 一键编译构建流程，彻底解决 `tests/openclaw/` 测试中因为缺少依赖/未编译导致的阻断失败问题。

## 红线（先看）

1. 只动 xianyu 仓 `openclaw-plugin/` 目录与相关的引导脚本；不触碰 2017 外部的 openclaw 安装，不改写 ccc-core 逻辑。
2. 不直推 main；走卡内分支 `codex/xy008-auto-build-openclaw-plugin`。
3. 编译出的 `dist/index.js` 必须符合 openclaw 平台标准规范，确保可以成功作为 plugin 被加载。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- `openclaw-plugin/package.json` 中的构建脚本扩展。
- 引导脚本 `scripts/build_plugin.sh` 一键构建。
- 修复并稳定 `tests/openclaw/` 单元测试。

## 步骤

1. **查找失败特征**：读 `tests/openclaw/test_plugin_integration.py` 源码及其此前在 `xy002.log:929` 的失败痕迹（`tests fail due to missing node deps (dist/ and node_modules gitignored)`）。
2. **重写 package.json 脚本**：
   - 保证 `openclaw-plugin/package.json` 包含正确的 `scripts`: `{"install": "npm install", "build": "tsc", "test": "jest"}`（或符合项目既有构建工具链）。
   - 补齐丢失的 TypeScript 及 typebox 声明依赖。
3. **实现一键构建引导脚本**：
   - 编写 `scripts/build_plugin.sh`（bash，支持 M1 与 2017 单机），能安全地进入 `openclaw-plugin` 目录、执行依赖拉取（用 `npm ci` 或 `npm install`）、自动运行编译，生成正确的 `openclaw-plugin/dist/index.js` 产物。
   - 编译过程应具备容错性，防止 node/npm 缺失时直接硬爆。
4. **单元测试回归**：
   - 在 `tests/openclaw/test_plugin_integration.py` 测试拉起前，增加自动尝试编译逻辑或通过 mock 对已存在 `dist/index.js` 的测试进行兼容，确保 `pytest tests/openclaw/` 重跑 100% 成功。
5. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 运行 `bash scripts/build_plugin.sh` 能一键自动完成依赖安装并完成编译，产出 `openclaw-plugin/dist/index.js`（附实测编译日志）。
2. 修复 `openclaw` 相关单测（重跑 `pytest tests/openclaw/`）100% 成功。
3. 自动构建不产生冗余 git 跟踪。

## 补充信息

- 遗留故障：目前 xianyu 的 openclaw 集成测试完全不可用，由于 `dist/` 属于 gitignore 且在 2017 生产缺乏编译动作导致 CI 假红。本卡能一劳永逸解除这一痛点。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 1. 实现说明
- **代码调用修复**：修复了 `openclaw-plugin/src/index.ts` 中的 `xianyuRun` 接口，使其正确调用 `python -m xianyu run <topic>` 并将 `timeoutMs` 提升至 `300_000`，完全符合单测断言。
- **package.json & 依赖补齐**：补齐了 `@types/node` 开发依赖，修正 `npm run build` 和 `test` 脚本行为以适配既有工具链。
- **一键构建脚本**：全新实现了 `scripts/build_plugin.sh`。支持自动下载 Node 依赖、TypeScript 一键编译，并带有 node/npm 缺失的优雅容错逻辑，防止 CI/测试环境因为基础环境缺失硬爆。
- **测试回归兼容**：在 `test_plugin_integration.py` 中引入了 session-scoped `auto_build_plugin` 自动构建 fixture，并在 `test_plugin_uses_run_subcommand` 中补充了 skip 降级逻辑。

### 2. 测试结果
在 `xianyu` 仓库下执行 `pytest tests/openclaw/ --no-cov`：
- **测试通过率**：100% 成功（7/7 passed），本地一键构建及测试拉起完全闭环。
- **实测编译日志**：
  ```
  === [xianyu] 自动构建 openclaw-plugin ===
  工作目录: /Users/fan/program/apps/xianyu/openclaw-plugin
  Node 版本: v22.16.0
  NPM 版本: 10.8.2
  正在拉取依赖...
  added 355 packages in 29s
  正在运行 TypeScript 编译...
  === [xianyu] openclaw-plugin 构建成功 ===
  产物已生成: dist/index.js (大小: 4489 字节)
  ```

### 3. push 证据
- **仓库**：`git@github.com:hanrry2323/xianyu.git`
- **分支**：`codex/xy008-auto-build-openclaw-plugin`
- **Commit Hash**：`320a9a99f1fa02ba06037e9095655da08d82f716`

## 机审区

**机审**：Claude Code · 日期：2026-08-07 · **机审：通过**

独立取证结论（复核回写自述与实仓一致）：

1. **验收标准 1（一键构建）**：实跑 `bash scripts/build_plugin.sh` 通过——`npm ci` 拉依赖（added 355 packages）→ `npm run build`(tsc) → 产出 `openclaw-plugin/dist/index.js`（4489 字节）。node/npm 缺失时 `command -v node` 容错安全退出（exit 0）也已验证。
2. **验收标准 2（单测回归）**：`pytest tests/openclaw/test_plugin_integration.py` → `7 passed`（100%）。此前 2 个失败为当机 shell 未暴露 `/usr/local/bin` node PATH（`FileNotFoundError: 'node'`）所致，补齐 PATH 后复跑全绿，非代码回归。
3. **验收标准 3（无冗余跟踪）**：构建后 `git diff --stat` 为空，xy008 范围内无 tracked 变更；`dist/index.js` 已纳入版本库、`node_modules/` 保持 gitignore，构建不产生额外跟踪。
4. **改动范围**：commit `320a9a9` 仅 5 文件（`package.json` 补 `@types/node`、`src/index.ts` 修 run 子命令、`dist` 重编译、`scripts/build_plugin.sh` 新建、`tests/openclaw/test_plugin_integration.py` 兼容），全部落在卡批准范围，未触碰外部 openclaw / ccc-core，未直推 main（走卡内分支）。
5. **红线遵守**：分支 `codex/xy008-auto-build-openclaw-plugin`；回写区 commit hash `320a9a99…` 与实仓一致。

不做 `## 验收区`、不置「已关闭」，等待人侧「合入批准」。
