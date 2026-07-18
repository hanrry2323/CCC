# Plan: adv-ccc-f19

来源: adversarial-2026-07-09.json

## 目标
[CWE-522] 代码 grep 未见 keychain/secret 命令; 若用户用环境变量 (export ANTHROPIC_API_KEY=...), 会被 subprocess 继承 (F9); macOS 推荐用 security find-generic-password -s 'opencode' -w 读 keychain, 但 CCC 未实现; env 暴露给子进程 → l

## 文件
scripts/_executor.py:1

## 验收
- [ ] 修复完成
