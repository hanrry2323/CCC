# debt-frontend-dead

> 标题: 前端删除未使用的 API 端点代码
> 创建: 2026-07-07T12:45:02Z

## 目标

## 问题
后端 /api/roles 和 /api/timeline 已实现，但前端 index.html 中 loadRoles() 和 loadTL() 函数未绑定到 UI 显示（role bar 和 timeline panel 写了但可能不可见）。

## 执行方案
1. 打开 index.html
2. 检查 loadRoles() 返回值是否渲染到 DOM
3. 检查 loadTL() 返回值是否渲染到 DOM
4. 如果函数在但 UI 不显示，要么补全 UI 绑定，要么删除死代码

## Phase

(由 dev 拆)

## Commit 计划

- dev 完成后自动 commit + push
