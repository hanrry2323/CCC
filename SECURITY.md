# Security Policy

## Supported versions

请针对仓库根目录 `VERSION` 所标的当前主线报告问题。历史 tag 若已修复请注明。

## Reporting a vulnerability

请**不要**在公开 Issue 中贴利用细节或密钥。

优先通过 GitHub 私信 / Security Advisory（若已开启）联系维护者 **hanrry2323**，或在仓库开一个仅含「存在安全问题、请联系」的 Issue，我们会转私聊。

请尽量包含：

- 影响组件（Hub / Board / Engine / 安装脚本）  
- 复现步骤  
- 预估影响（信息泄露 / RCE / 未授权启用控制面等）  

我们会确认收悉，并在修复后视情况致谢（除非你希望匿名）。

## 安全设计要点（给审计者）

- 控制面默认 `disabled`：不偷偷常驻 Engine、不自造任务  
- Hub Basic Auth；Board API 默认本机绑定（见 `docs/ccc-hub-ports.md`）  
- 红线 1：不改系统文件与密钥；红线 12：agent 不得擅自启用 CCC  
