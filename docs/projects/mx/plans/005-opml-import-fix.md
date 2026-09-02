# 方案 · OPML 导入属性顺序依赖漏洞修复

> 项目：mx · 编号：mx-plan-005 · 状态：已完成 · 作者：Claude Code W1 · 工具：ccc-plan
> 创建：2026-08-18 · 更新：2026-08-24
> 验收：验收席：DSH（受老板临时授权代行 · 2026-08-24） · 证据：乱序属性端到端测试在位（rss.rs:971 extreme disordered 用例，commit fd039e5）；parse_opml 延迟推导实现与方案一致；cargo test --workspace 578 全绿（2026-08-24 实测）
>  关联卡：已归档（原引用 mx052 随 8-24 治理归档，见 docs/archive 与 RETIRED 记录）
> 进度：1/1 (100%)
> 里程碑：M8 · 媒体库与 RSS 阅读体验优化（子项目 8.1）

## 目标

修复 OPML 导入由于 XML 属性无序遍历时，因 `xmlUrl` 属性先被读到而提前触发 push 导致的订阅源显示名称丢失漏洞 (P0)。保证不管 XML 属性在 OPML 节点中按什么顺序排列，解析出的订阅源名称都完美、准确。

## 背景

在 `api/routes/rss.rs` 的 `parse_opml` 中，遍历 XML 属性是无序的。若 `<outline>` 标签中的 `xmlUrl` 属性出现在 `text` 属性之前，解析器会在 `xmlUrl` 触发时将 `name` 直接设为 `url` 写入列表；等后续读到 `text` 属性更新 `current_text` 变量时，由于该节点已完成 push，导致该条订阅的显示名称在数据库中永久丢失并显示为原始 URL。这属于严重影响数据完备性的 P0 级 Bug。

## 方案内容

### 属性解析延迟推导设计
1. 废弃在 XML 属性遍历 `Event::Start` 或 `Event::Empty` 循环内部直接 push 结果的做法。
2. 处理单个 `outline` 节点时，声明一组临时变量或局部 Option 变量：
   - `let mut title_opt: Option<String> = None;`
   - `let mut text_opt: Option<String> = None;`
   - `let mut xml_url_opt: Option<String> = None;`
3. 遍历当前节点的所有属性，仅做数据解析与 Option 暂存，例如：
   ```rust
   match attr.key.as_ref() {
       b"title" => title_opt = Some(val_str),
       b"text" => text_opt = Some(val_str),
       b"xmlUrl" => xml_url_opt = Some(val_str),
       _ => {}
   }
   ```
4. 退出当前节点属性循环后，在循环外部进行名称合并推导并执行 `push`：
   - 优先使用 `title_opt`。
   - 无 `title_opt` 则使用 `text_opt`。
   - 无 `text_opt` 且有 `xml_url_opt` 则使用 `xml_url_opt` 兜底作为 `name`。

## 验收标准

- [x] `parse_opml` 函数对 XML 属性的顺序完全解耦，乱序属性解析不再导致订阅显示名称丢失。
- [x] 乱序属性 OPML 文件的端到端解析断言单元测试编写完成并 100% 绿灯。（rss.rs:971，fd039e5）
- [x] `cargo test -p medio-core` 全绿，无编译错误与 warnings。（2026-08-24 实测 578 全绿；clippy -D warnings 绿）

## 功能卡

### 修复 OPML 导入属性顺序依赖漏洞 (mx052 · P0)

*   **目标**：修复 OPML 导入由于 XML 属性读取顺序不同而导致显示名称丢失的漏洞。
*   **实现**：重构 `api/routes/rss.rs` 中的 `parse_opml` 函数，使用局部变量缓存并延迟 push。
*   **验收**：使用乱序属性 OPML 测试片段，解析后导入的订阅名称正确，不显示为原始 URL。
