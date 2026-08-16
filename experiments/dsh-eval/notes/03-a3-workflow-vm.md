# 实验 A3 · workflow vm 逃逸范围

- **状态**：✅ 完成
- **批次**：B1 安全
- **环境**：测试实例（headless code 模式，一次性）
- **日期**：2026-08-16

## 结论

**workflow 编排脚本可逃逸 vm 沙箱，触达宿主 Node 进程的 `process` 对象（pid/env）**。`globalThis.constructor.constructor`（经典 Function 构造器链）拿到宿主上下文的原生 `Function`，用它执行代码即运行在宿主进程上下文。印证报告警告：「the vm is not a security boundary. The worker provides host-loop isolation and forced termination, not hostile-value containment.」

## 方法

run_code 程序调用 `tools.workflow({script, meta})`，脚本为逃逸探针：
1. 探测直接环境（process/require/fetch/Buffer/globalKeys）。
2. 经典逃逸：`globalThis.constructor.constructor('return typeof process')()`。
3. 逃逸成功后读 `process.pid` / `process.env`。

会话：`session-86b37341-08e4-4aa6-ba67-49e283c16b99`，workflow runId `d9cb7561`。

## 结果（workflow 返回原文）

```
process=false | require=false | fetch=false | Buffer=false |
globalKeys=agent,parallel,pipeline,phase,log,args |
FN_CTOR=function Function() { [native code] } |
FN_CTOR_REQUIRE=undefined |
ESCAPED_PID=45456 | ESCAPED_ENV=
```

## 证据与解读

| 观察 | 含义 |
|---|---|
| 直接环境 process/require/fetch/Buffer 全 false | vm 沙箱面干净，只暴露 6 钩子 |
| `globalThis.constructor.constructor` 拿到原生 Function | **构造器链逃逸成功**——Function 运行在宿主上下文 |
| `ESCAPED_PID=45456` | 真实拿到宿主 headless 进程 PID（只读证实逃逸到宿主） |
| `ESCAPED_ENV=` 空 | process.env 仍被清空（与 A1 一致，env 清空是全局加固） |
| `FN_CTOR_REQUIRE=undefined` | 逃逸上下文无 require（模块系统未暴露） |

## 未覆盖/延伸

- 逃逸后能否用 `process.getBuiltinModule('node:fs')` 做完整文件/进程操作：A1 已证 `getBuiltinModule` 在宿主上下文可用，逃逸上下文（同宿主 process）大概率同样可用 → **workflow 脚本可等同 run_code code 的完整逃逸**。建议后续用逃逸上下文直接调用 getBuiltinModule 证实（本轮只探了 pid/env）。
- `process.env` 键值详情未完全枚举（前 5 键有空串，说明 env 非全空但有被清空痕迹）。

## 风险 / 对 CCC 借鉴的影响

- **模型可写的 workflow 编排脚本 = 宿主进程逃逸通道**（至少读 pid/env，延伸可及 fs/spawn/网络）。这与 A1（run_code code 全逃逸）叠加：**DSH 的两条"代码执行"路径（run_code、workflow 脚本）都没有有效沙箱**。
- 隔离只靠 worker 线程 + 超时 terminate——`worker provides host-loop isolation... not hostile-value containment`。
- CCC 若让 DSH 跑模型可控脚本，必须**进程/容器级隔离**（如单独容器跑 DSH），不能信任其内置 vm/worker 隔离。
- workflow 的 fail-closed（坏参数/超时 terminate）是好的防御默认，但挡不住有意逃逸。
