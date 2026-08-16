# 实验 E19 · patch `-id: dsh-web-app` 静默 no-op 终判

- **状态**：✅ 完成（确认 no-op）
- **批次**：B5 多代理
- **环境**：配置 + 源码
- **日期**：2026-08-16

## 结论

**`cordis.patch.yml` 里 `- id: dsh-web-app` 的 trustedHosts 加固块是死配置（静默 no-op）**。真实 entry id 是 `web-runtime`（dsh-web-app 自带 bundle 的 patch 里），patch 系统对不存在的 entry id 只 warn 不报错（dsh-app-boot applyEntryPatches）。**实际 trustedHosts 来自 `web-runtime` 的 `ctx.webStartup.trustedHosts`（plist `--trusted-host 192.168.3.116`）**——这就是为什么局域网能访问，但加固块的 trustedHosts 声明没生效。

## 证据

- dsh-web-app/cordis.patch.yml:130：`- id: web-runtime` `name: '@deepseek-ai/dsh-web-app'`
- `:136`：`trustedHosts: !!js ctx.webStartup.trustedHosts`（真实来源）
- user cordis.patch.yml:20：`- id: dsh-web-app`（不存在 → 静默跳过）
- dsh-app-boot/lib/index.js:57-95：applyEntryPatches 对 unknown id 只 warn + continue

## 结论细节

- 死配置无害但误导（以为加固了实未生效）；真实信任链是 plist。
- 修复方向：user patch 的 id 改为 `web-runtime`（或删除该块，保留 plist 真源）。

## 风险 / 对 CCC 借鉴的影响

- **patch 系统静默跳过死配置 = 配置假象**：CCC 若用 DSH 类 patch 机制，需「配置生效自检」（如 dump-config 校验）防「以为配了、实际没生效」。
