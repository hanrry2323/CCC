# 教训 · 2026-08-24 · C locale 下 BSD sed 字节级截断多字节字符类（ccc068）

## 现象

validate-plans.sh 的卡头状态抽取在部署机（launchd，locale=C）把「已关闭」截成单字节
0xE5，导致 8.2「方案关联卡已全部关闭但状态未推进」漏判；pytest 子进程继承 UTF-8 故
开发仓一直绿，形成「本仓绿、部署红」的双面证据。

## 根因

BSD sed 在 C locale 按字节处理。字符类 `[^ ·\t\r\n]+` 中全角「·」（U+00B7）被编译为两个
独立字节成员 C2、B7；「已」(E5 B7 B2) 的第二字节恰为 B7 → 类在该字节处停止匹配。
非通用 multibyte 问题，而是分隔符字节与数据字节的碰撞，因此只在特定汉字上触发。

## 规则沉淀

1. 部署侧入口脚本凡用 sed/awk/grep 字符类处理中文，顶部必须显式
   `export LC_ALL="${LC_ALL:-en_US.UTF-8}"`；不能依赖调用方环境。
2. 「本仓绿 ≠ 语义对」：与 launchd/C locale 环境相关的脚本，验证必须包含一次
   `env -u LANG -u LC_ALL LC_CTYPE=C <复跑>` 的对照（本次即靠它复现）。
3. 引擎同口径红线：改任何校验语义前先读 `server/board/plans.py::sync_plan_progress`
   等权威实现——缺失关联卡两侧都按「活跃」计，不得单边改为「已关闭」。

## 关联

- 修复卡：docs/dispatch/ccc/ccc068-validate-plans-utf8-gate.md（commit ed1a863c3）
- 实证：pytest 子进程 LC_CTYPE=UTF-8 与外层 LC_CTYPE=C 双环境对照，字节 xxd 差异
  e5 vs e5b7b2e585b3e997ad。
