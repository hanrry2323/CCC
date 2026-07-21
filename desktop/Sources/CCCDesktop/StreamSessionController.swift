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
    /// 请求级逻辑名（sidecar / loop-code 认这些；现网均映射 MiniMax-M3）
    static let allowedModels = ["flash", "code", "sonnet", "haiku", "minimax-m3"]

    /// UI 快选：id → 显示名（Phase17）
    static let modelPickerOptions: [(id: String, label: String)] = [
        ("flash", "MiniMax-M3"),
        ("code", "MiniMax · code"),
        ("sonnet", "MiniMax · sonnet"),
        ("haiku", "MiniMax · haiku"),
    ]

    static func modelDisplayName(_ preferred: String) -> String {
        let id = resolveModel(preferred)
        return modelPickerOptions.first(where: { $0.id == id })?.label
            ?? (id == "minimax-m3" ? "MiniMax-M3" : id)
    }

    /// discuss = 只读探查；engineer = 允许本机写文件
    static func resolveToolMode(preferred: String, userText: String) -> String {
        let pref = preferred.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if pref == "engineer" { return "engineer" }
        let t = userText.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.contains("工程师模式") || t.contains("直接改本机") { return "engineer" }
        return "discuss"
    }

    static func resolvePromptMode(forUserText text: String) -> String {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let forceFull = ["定稿", "转任务", "下达", "可以转了"].contains { t.contains($0) }
        if forceFull || t.count > 80 { return "full" }
        return "light"
    }

    static func resolveModel(_ preferred: String) -> String {
        let m = preferred.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        // minimax-m3 与 flash 同出口；对外 API 仍发 flash（sidecar 白名单）
        if m == "minimax-m3" || m == "minimax" { return "flash" }
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
        lines.append("请结合上述本地路径阅读（工程师模式才可改文件）。")
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
