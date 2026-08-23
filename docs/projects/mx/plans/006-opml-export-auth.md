# 方案 · OPML 导出 Bearer Token 强鉴权适配

> 项目：mx · 编号：mx-plan-006 · 状态：已完成 · 作者：Claude Code W1 · 工具：ccc-plan
> 批准：老板确认转卡 · 2026-08-19
> 创建：2026-08-18 · 更新：2026-08-24
> 验收：验收席：DSH（受老板临时授权代行 · 2026-08-24） · 证据：RssSidebar.tsx 已为 fetch+Blob+createObjectURL 虚拟点击且携带 Bearer（:202/:215）；契约单测 RssSidebar.test.tsx 在位（commit 74a4f15）；前端 vitest 381 全绿（2026-08-24 实测）
> 关联卡：mx054
> 进度：1/1 (100%)
> 里程碑：M8 · 媒体库与 RSS 阅读体验优化（子项目 8.2）

## 目标

解决 `medio-0` 在强鉴权模式下点击 OPML 导出超链接因无法附加 `Authorization` 请求头而返回 401 Unauthorized 的漏洞 (P0)。支持 Bearer Token 在任意设备和浏览器下安全触发下载。

## 背景

`RssSidebar.tsx` 里的 OPML 导出按钮目前采用原生的 `<a>` 标签，直接指向后端的 `/rss/opml`。在系统开启强身份验证模式时，通过普通超链接点击无法附加 `Authorization` 头部，导致网络拦截并报 401 错误，使安全功能产生体验性漏洞。

## 方案内容

### 前端下载管道重构（Blob + 虚拟点击）
1. 重构前端 `RssSidebar.tsx` 的 OPML 导出触发事件。
2. 按钮绑定点击回调函数，不再直接渲染 `href="/rss/opml"` 的超级链接。
3. 在点击事件中，使用 `fetch` 接口异步请求 `/rss/opml`：
   - 携带 `headers: { "Authorization": `Bearer ${token}` }`（从 local-storage 或 auth-state 获取）。
4. 将响应体读取为文本/Blob 对象。
5. 构造浏览器内存临时对象 `URL.createObjectURL(blob)`。
6. 动态创建隐藏的虚拟 `<a>` 元素：
   - `const link = document.createElement('a');`
   - `link.href = objectUrl;`
   - `link.download = 'subscriptions.opml';`
7. 将虚拟链接 append 进 DOM，程序调用 `link.click()`，触发安全下载。
8. 触发后从 DOM 移除该虚拟链接，并释放 `URL.revokeObjectURL(objectUrl)` 规避内存泄露。

## 功能卡

### OPML 导出 Bearer 鉴权下载重构

目标：修复强鉴权模式下 OPML 导出 401 漏洞，用 fetch+Blob+虚拟点击替代原生 a 标签。

实现：重构 `RssSidebar.tsx` OPML 导出按钮——绑定点击回调（非 href），fetch `/rss/opml` 携带 `Authorization: Bearer ${token}`，响应转 Blob，`URL.createObjectURL` + 虚拟 a 元素 `link.click()` 触发下载，完成后移除+revokeObjectURL 防内存泄漏。

验收：强鉴权模式点击导出不 401、成功下载 OPML 文件；前端 vitest 全绿。

颗粒度：单文件前端改动（RssSidebar.tsx + 可能的 hook/util），1 张卡。

依赖：无（后端 `/rss/opml` 端点已存在，本卡只改前端触发方式）。

架构位置：前端 RSS 视图层（RssSidebar）→ 后端 /rss/opml 端点。

## 验收标准

- [x] OPML 导出按钮在强鉴权模式下，能携带 Bearer Token 并顺利触发 OPML 文件的本地下载，不弹出 401 或强制重新登录。
- [x] 前端打包编译、Lint、以及 `vitest` 前端测试套件全绿。（2026-08-24 实测 32 suites / 381 tests）
