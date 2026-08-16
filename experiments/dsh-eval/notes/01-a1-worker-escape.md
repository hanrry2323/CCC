# 实验 A1 · worker 逃逸触达面枚举

- **状态**：✅ 完成
- **批次**：B1 安全
- **环境**：测试实例（headless code 模式，一次性）
- **日期**：2026-08-16

## 结论

**run_code 的 code 执行环境逃逸面很宽**：任意路径文件读 + 子进程 spawn + 完整网络（本地含生产 web、外网全通）全部可达，`getBuiltinModule('node:fs'/'node:child_process'/'node:net')` 无拦截。**唯一加固痕迹是 env 清空**。`tools.*` 沙箱（Seatbelt/fs 栅栏/审批）对 code 层一律无效——code 直接走 Node 内置能力，根本不经过 tools。

## 方法

headless code 模式跑一段探测程序（原样执行），逐项探测：env / 内置模块 / 跨工作区读 / spawn / 网络 / 全局对象。会话 `session-4262b8da-c4ba-4b28-9662-dd63412e37cf`。

## 结果（程序 return 原文）

```
ENV_KEYS=
MODULES fs=true cp=true net=true
READ_HOME=.CFUserTextEncoding,.DS_Store,.Trash,.agents,.ai_completion,.bashrc
SPAWN=SPAWN-OK
NET_LOCALHOST=200
NET_WAN=200
HAS_PARENTPORT=false
HAS_REQUIRE=false
HAS_PROCESS=true
GLOBALS_DSH=
GLOBAL_COUNT=15
```

## 证据与解读

| 探测项 | 结果 | 含义 |
|---|---|---|
| ENV_KEYS 空 | env 被清空 | 唯一加固；但 node:process 本身还在 |
| fs/cp/net 内置模块 | 全 true | `process.getBuiltinModule` 是 Node≥20.16 能力，code 层可用 |
| READ_HOME | 读到 home 目录 `.bashrc/.Trash` 等 | **工作区外任意读，fs 栅栏不拦 code 层** |
| SPAWN | SPAWN-OK | **子进程可执行**（Seatbelt 只套 bash 工具，不套 code） |
| NET_LOCALHOST=200 | 本地 3080 可达 | **code 层可直连生产 web 的 HTTP 面**（跨实例触达，非套接字/内存态，但网络面已开） |
| NET_WAN=200 | baidu 200 | 外网全通（可外传数据） |
| HAS_PARENTPORT=false | globalThis 无 parentPort | 注：源码是 `new Worker` 每 run 一线程（dsh-code-runtime-worker-thread），parentPort 是模块作用域 import 非 global，此值不能证「非 worker」；worker 判定以源码为准 |
| GLOBAL_COUNT=15 | 全局瘦身 | 无 dsh/session/host 全局对象 → **未触达宿主内存态对象**（本轮未见，需更深探测） |

## 未覆盖/后续

- **宿主内存态触达**（服务器 socket、pending 审批、其他 worker 句柄）：本轮仅见 globalThis 干净，未做 `process._linkedBinding` / `process.mainModule` / `getBuiltinModule('node:worker_threads')` 深挖——可作 A1 延伸或单独实验。
- worker 判定（threadId / isMainThread）未在程序内确认，以源码 `new Worker` 为准。

## 风险 / 对 CCC 借鉴的影响

- **最高风险实证升级**：run_code code 层 = 免沙箱、免审批、任意代码（读写/执行/联网）。不只是「读文件」，是**完整逃逸**。
- **跨实例触达**：code 可访问生产 web 的 3080 网络面 → 若 web 面有写接口且无认证，code 层可驱动。内网可信假设是当前唯一护栏（CCC 决策档已确认内网无可信设备风险）。
- CCC 若吸收 code-run：**进程/容器级隔离是硬前置**，临时目录隔离（ccc-run-inline 现状）远不够。
