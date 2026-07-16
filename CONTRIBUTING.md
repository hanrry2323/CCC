# Contributing to CCC

感谢贡献。请先读产品叙事：[`docs/VISION.md`](docs/VISION.md)。

## 原则

1. **Hub 是入口**；不要把「再接一个第三方 IDE 壳」当成默认方向，除非有明确执行器需求。  
2. **不要做成角色超市**；新能力优先「任务路由 + Skill/Prompt」，而不是「再加一个用户必选角色」。  
3. **红线不可破**：尤其红线 11（verdict 文件）、12（禁止擅自启用 CCC）。见 `references/red-lines.md`。  
4. **控制面默认安全**：改安装脚本时勿默认 `invent` 或静默拉起 Engine。

## 开发流程（摘要）

```text
意图清晰 → plan + phases（或 Hub 定稿）→ 改代码 → pytest → commit
```

详细工程流程仍可参考 [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)（历史详尽版）；**对外口径以 VISION + 本文为准**。

## 本地命令

```bash
pytest tests/scripts/ -q --tb=short
bash scripts/ccc-self-check.sh
bash scripts/ccc-hub-dev.sh          # 前端
ruff check scripts/ tests/           # 若已安装
```

## PR 建议

- 说明 **为什么**（对 Loop / Hub / 路由的影响），不只列文件  
- 用户可见行为变更：更新 `CHANGELOG.md`；若动定位：同步 `docs/VISION.md` / `README.md`  
- 勿提交：密钥、`.env`、`.ccc/board/*.lock`、本机绝对路径隐私  

## 行为准则

- 善意、具体、可复现的 issue  
- 安全问题请按 [`SECURITY.md`](SECURITY.md) 私下披露  

## License

贡献代码默认同意以 **MIT** 许可纳入本项目（见 `LICENSE`）。
