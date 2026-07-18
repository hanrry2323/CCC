# Plan: adv-ccc-f1

来源: adversarial-2026-07-09.json

## 目标
[CWE-284/306/200] install-ccc-roles.sh plist 硬编码 0.0.0.0, ccc-board-server.py 无 auth 头/token/cookie/来源 IP 限制, CORS * + GET/POST/OPTIONS, POST /api/tasks 接受任意 tid/title/description, POST /api/tasks/mov

## 文件
scripts/install-ccc-roles.sh:158

## 验收
- [ ] 修复完成
