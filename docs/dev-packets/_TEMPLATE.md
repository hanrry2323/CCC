# DEV-PACKET: \<id\>

> 复制本文件全文发给**个人 Claude Code CLI**（非 Desktop Agent）。  
> 合入权威 = Cursor。做完只提交到指定分支，**不要 push main**。

## 1. 目标（用户可见）

一句话：做完后用户能看到什么。

## 2. 分支与提交

- 从最新 `main` 拉分支：`draft/<id>`
- 提交信息风格：`feat(scope): …` / `fix(scope): …`（英文 why 优先）
- **禁止** `git push origin main`；可不 push，或 `git push -u origin draft/<id>`
- **禁止** `git add -A` / `git add .`；只 add 白名单文件

## 3. 白名单（只许改这些）

- `path/one`
- `path/two`

## 4. 黑名单（碰了就停）

- `docs/product/loop-engineer-authority.md`
- `references/red-lines.md`
- `~/.ccc/**` 生产密钥 / plist
- `relay/upstreams.json`（真钥）
- 其它未列路径

## 5. 现状锚点

- 文件：`…` 函数/符号：`…`
- 相关 brief：`…`

## 6. 实现步骤

1. …
2. …
3. …

## 7. 验收（必须跑）

```bash
# 命令与期望
```

## 8. 做完回报（固定格式）

```
BRANCH: draft/<id>
FILES:
- …
TESTS:
- … → pass/fail
RESIDUAL:
- …
```
