# DSH 实验环境说明（已部署 2026-08-16）

> 环境 = headless code 模式 one-shot runner，不需要独立 profile。生产 web（PID 48580 :3080）不受影响。

## 一句话
`DSH_TOOLS_MODE=code` + 从 web plist 借环境变量 + `dsh --profile headless "<任务>"` = 隔离的 code 模式实验实例。

## 运行方式
```bash
# 在 2017 上（脚本已提交在 branch，跑实验时 scp 过去或用 ssh 直接调）
bash run-headless-code.sh "<任务文本>"            # cwd 默认 /Users/fan/qx-map
bash run-headless-code.sh "<任务文本>" "/某/工作区" # 指定 cwd
```

## 关键机制
| 项 | 值 | 出处 |
|---|---|---|
| code 模式开关 | `DSH_TOOLS_MODE=code`（native/code/both） | dsh-web-app/cordis.patch.yml 注释 |
| code preset | 内置 `dsh/config/agent-presets/code/agent.cordis.yml`（mode: code） | dsh 包 |
| code-runtime | headless bundle 自带挂载 `dsh-code-runtime-worker-thread` | dsh-headless/cordis.patch.yml |
| 凭据来源 | web plist `~/Library/LaunchAgents/com.deepseek.dsh-web.plist` 的 EnvironmentVariables（OPENCODE_GO_API_KEY 等） | launchctl |
| IPv6 防护 | `NODE_OPTIONS=--dns-result-order=ipv4first` | 决策档 DSH配置OpenCode-go直连通道 |
| 会话落盘 | `~/.dsh/sessions/<workspace>/session-<uuid>/session.jsonl.zstd` | dsh-session-persistence |

## 注意
- runner 借 env 时不打印密钥值（red line：不碰密钥明文）。
- 每次 headless 一个新会话，约 30s–4min（视任务复杂度，模型调用）。
- 任务描述要明确「用 run_code」，否则无 run_code 的 native 会话里模型可能幻觉等价实现（B0 已观察到）。

## 生产 web 隔离
- 实验用 headless，与 web 不同进程、不同会话；web 只从自己的 plist 读 env，实验 env 不落 web。
- 安全实验（A 组）跑任意代码，只用本 headless 实例，严禁碰 web。
