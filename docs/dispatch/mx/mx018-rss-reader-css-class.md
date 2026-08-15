# 任务卡 mx018 · RSS 阅读器 CSS 类绑定修复（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-08

## 目标

RSS 阅读器 CSS 类绑定修复（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/frontend/src 下 RssReader.tsx 及 RSS 相关样式文件`
- `前端测试文件（如渲染用例）`

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读 `src/frontend/src` 下 RssReader.tsx 外层容器 className（当前 `rss-pane` + `active`）与 `index.css` 中 `.rss-reader` 类定义的样式。
2. 为外层容器补绑 `rss-reader` 类（保留既有类）；核对内联样式与 `.rss-reader` 规则冲突点，移除冗余内联样式。
3. 验证：桌面/平板/手机三档渲染正常（回写区记录浏览器实测：三档各一条 + 有无视觉回归）；`.rss-reader` 响应式样式生效。
4. `npm run test` / lint / build 通过。
5. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. RssReader 外层容器补绑 rss-reader CSS 类，页面级响应式样式生效；内联样式与 CSS 冲突消除
2. 自测记录：阅读器在桌面/平板/手机三档渲染正常，无视觉回归（回写区截图或描述）
3. npm run test / lint / build 通过；只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
