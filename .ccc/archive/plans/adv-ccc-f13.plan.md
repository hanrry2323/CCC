# Plan: adv-ccc-f13

来源: adversarial-2026-07-09.json

## 目标
[CWE-200] do_GET 末尾 else: super().do_GET() → 走 SimpleHTTPRequestHandler 默认 GET, 直接 list 目录内容 (LIST 目录) 或 serve 文件; ccc-board-ui 目录里有 app.js / index.html 等, 可能含 API key / 内部 endpoint hint; 目录遍历: Simple

## 文件
scripts/ccc-board-server.py:223

## 验收
- [ ] 修复完成
