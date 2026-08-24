# clw 006 教训沉淀 (2026-08-10 · Packager & DMG Building)

> 来源：clw006 dmg 打包与安装验收。
> 触发：在 non-GUI 终端环境下（如 SSH、自动构建、部分开发执行体环境）运行 `cargo tauri build` 时 AppleScript 报错导致 DMG 打包失败。

## 教训

### 1. 终端自动化打包 DMG 时需要跳过 Finder 美化 (AppleScript)

- **现象**：在 macOS 2017 开发机或 CLI 执行体中运行 `cargo tauri build` 时，DMG 打包流程会在 `Running bundle_dmg.sh` 阶段报错：`Failed running AppleScript` 并退出。
- **根因**：Tauri 的 macOS DMG 打包工具底层使用了 `create-dmg` 开源库。该库在打包时会调用 AppleScript 对 Finder 中的磁盘挂载图标进行背景渲染、美化和坐标重置。这需要 Finder 图形化接口的控制权限。而在自动化构建、非 GUI 会话或无授权的 shell 环境中，AppleScript 无法调用 Finder 的自动化接口，从而直接导致 `bundle_dmg.sh` 出错。
- **解决方案**：在打包命令前，显式加入 `CI=true` 环境变量，例如运行：
  ```bash
  CI=true cargo tauri build
  ```
  这样 Tauri (及底层的 create-dmg 脚本) 会检测到当前处于 CI/CD 自动化构建环境，自动启用 `--skip-jenkins` 选项，跳过需要 Finder GUI 权限的 AppleScript 美化逻辑，仅进行纯文件的 DMG 封装，确保构建 100% 成功。
