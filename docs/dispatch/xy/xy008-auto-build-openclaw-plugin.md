# 任务卡 xy008 · 系统集成：自动构建openclaw-plugin与依赖补齐（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

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

**执行体**：OpenCode · 日期：
