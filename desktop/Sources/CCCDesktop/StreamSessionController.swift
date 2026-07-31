import Foundation

/// Composer 附件（路径/图片引用进 prompt；不嵌 OpenCode）
struct ComposerAttachment: Identifiable, Hashable, Equatable {
    let id: UUID
    var path: String
    var isImage: Bool

    init(id: UUID = UUID(), path: String, isImage: Bool = false) {
        self.id = id
        self.path = path
        let lower = path.lowercased()
        self.isImage = isImage
            || lower.hasSuffix(".png")
            || lower.hasSuffix(".jpg")
            || lower.hasSuffix(".jpeg")
            || lower.hasSuffix(".gif")
            || lower.hasSuffix(".webp")
    }
}

/// 流式策略与 prompt 拼装（从 AppModel 热路径拆出，对齐 OpenCode session 心智）
enum StreamSessionController {
    /// 请求级逻辑名（sidecar / loop-code / relay 三档契约，一律小写）
    static let allowedModels = ["flash", "pro", "code"]

    /// UI 快选：id → 显示名（标签由 relay upstreams 定义，此处为默认 fallback）
    static let modelPickerOptions: [(id: String, label: String)] = [
        ("flash", "flash · 免费日常"),
        ("pro", "Pro · 高级"),
        ("code", "code · 写码"),
    ]

    static func modelDisplayName(_ preferred: String) -> String {
        let id = resolveModel(preferred)
        return modelPickerOptions.first(where: { $0.id == id })?.label ?? id
    }

    /// discuss = 可选只读；engineer = 默认 全功能（开发/定任务/优化，工具全开）
    static func resolveToolMode(
        preferred: String,
        userText: String,
        projectId: String? = nil
    ) -> String {
        _ = projectId
        let pref = preferred.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if pref == "discuss" { return "discuss" }
        if pref == "engineer" { return "engineer" }
        let t = userText.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.contains("规划模式") || t.contains("只读讨论") {
            return "discuss"
        }
        if t.contains("工程师模式") || t.contains("直接改本机") || t.contains("全功能") {
            return "engineer"
        }
        // Desktop Agent 全功能：默认 engineer
        return "engineer"
    }

    static func resolvePromptMode(forUserText text: String) -> String {
        // 已取消 light：discuss = Plan 恒 full（短闲聊靠纪律直接答，不掏空工具）
        _ = text
        return "full"
    }

    static func resolveModel(_ preferred: String) -> String {
        var m = preferred.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        // 历史伪档 / 大小写别名 → 三档
        if m == "sonnet" || m == "haiku" || m == "opus" { m = "flash" }
        return allowedModels.contains(m) ? m : "flash"
    }

    /// 附件路径拼进用户原文（sidecar 只吃文本 prompt）
    static func composeUserText(text: String, attachments: [ComposerAttachment]) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !attachments.isEmpty else { return trimmed }
        var lines: [String] = []
        if !trimmed.isEmpty { lines.append(trimmed) }
        lines.append("")
        lines.append("【附件】")
        for a in attachments {
            let kind = a.isImage ? "图片" : "文件"
            lines.append("- \(kind): \(a.path)")
        }
        lines.append("请结合上述本地路径阅读（全功能模式可直接改文件）。")
        return lines.joined(separator: "\n")
    }

    static func writePaths(from steps: [ToolStep]) -> [String] {
        var out: [String] = []
        for s in steps where ToolProgressHelper.isWrite(s.name) {
            // humanLabel 形如「写入 path」或含路径片段
            let label = s.label
            if let range = label.range(of: "/") {
                let path = String(label[range.lowerBound...]).trimmingCharacters(in: .whitespaces)
                if !path.isEmpty, !out.contains(path) { out.append(path) }
            }
        }
        return out
    }
}
