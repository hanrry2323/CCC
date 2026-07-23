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

    /// discuss = 只读探查；engineer = 允许本机写文件（仅平台仓 ccc；ccc 默认 engineer）
    static func resolveToolMode(
        preferred: String,
        userText: String,
        projectId: String? = nil
    ) -> String {
        let pref = preferred.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let pid = projectId?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() ?? ""
        // 编排运维 Agent（ccc）：默认 engineer；仅显式 discuss 保持只读
        if pid == "ccc" {
            if pref == "discuss" { return "discuss" }
            let t = userText.trimmingCharacters(in: .whitespacesAndNewlines)
            if t.contains("规划模式") || t.contains("只读讨论") {
                return "discuss"
            }
            return "engineer"
        }
        var mode = "discuss"
        if pref == "engineer" {
            mode = "engineer"
        } else {
            let t = userText.trimmingCharacters(in: .whitespacesAndNewlines)
            if t.contains("工程师模式") || t.contains("直接改本机") {
                mode = "engineer"
            }
        }
        // 业务仓拒绝工程师模式
        if mode == "engineer" { return "discuss" }
        return mode
    }

    static func resolvePromptMode(forUserText text: String) -> String {
        // 已取消 light：discuss = Plan 恒 full（短闲聊靠纪律直接答，不掏空工具）
        _ = text
        return "full"
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
