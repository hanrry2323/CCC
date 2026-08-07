# 任务卡 mx017 · RSS 图片防盗链代理端点（OpenCode 执行）

> 关联：ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-08

## 目标

RSS 图片防盗链代理端点（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/src/ 下新增/修改代理路由与图片获取模块`
- `前端图片组件 onError 降级逻辑（Rss 相关）`
- `相关测试文件`

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读现有图片组件与 RSS 正文图片渲染路径（RssReader 内 <img>、前端 fetch 客户端）。
2. 后端新增图片代理端点（如 `GET /api/v1/media/proxy?url=...`）：fetch 目标图片并转发（正确 Content-Type / 长度）；**SSRF 防护**：仅 http/https、拒绝内网/回环/保留地址（DNS 解析后校验），非法返回 4xx；可带简单内存缓存（可选）。
3. 前端：图片加载 `onError` 时降级走代理端点；或对已知防盗链 host 直接走代理（按实现取舍，回写区说明）。
4. 补后端测试：代理正常转发（mock/本地测试图）、非 http(s) 拒绝、内网地址拒绝；前端 vitest（降级逻辑）如有则补。
5. `cargo test` / `cargo check` 通过；`npm run test` / lint / build 通过。
6. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 后端新增图片代理端点（如 GET /api/v1/media/proxy?url=...），可代理获取图片并返回正确 MIME；前端图片加载失败时经代理降级获取
2. SSRF 防护：仅允许 http/https；拒绝内网/本地/回环地址；非法协议与非法 URL 返回 4xx
3. cargo test（含 SSRF 防护用例）/前端验证通过；只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
