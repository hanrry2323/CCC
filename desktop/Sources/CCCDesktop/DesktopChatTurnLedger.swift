import Foundation

/// 本机对话 turn 账本（稳定性诊断）：`~/Library/Logs/CCC/desktop-chat-turns.jsonl`
enum DesktopChatTurnLedger {
    private static let maxBytes = 2_000_000

    static var logURL: URL {
        let dir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/CCC", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("desktop-chat-turns.jsonl")
    }

    static func append(_ record: [String: Any]) {
        var row = record
        if row["ts"] == nil {
            let fmt = ISO8601DateFormatter()
            fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            row["ts"] = fmt.string(from: Date())
        }
        guard JSONSerialization.isValidJSONObject(row),
              let data = try? JSONSerialization.data(withJSONObject: row),
              var line = String(data: data, encoding: .utf8)
        else { return }
        line += "\n"
        let url = logURL
        if let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
           let size = attrs[.size] as? NSNumber,
           size.intValue > maxBytes {
            try? FileManager.default.removeItem(at: url)
        }
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        guard let handle = try? FileHandle(forWritingTo: url) else { return }
        defer { try? handle.close() }
        _ = try? handle.seekToEnd()
        if let payload = line.data(using: .utf8) {
            try? handle.write(contentsOf: payload)
        }
    }
}

/// 最近一次本条失败（供状态栏「重试 / 清槽」）
struct ChatTurnFailure: Equatable {
    let threadId: String
    let projectId: String
    let code: String?
    let message: String
    let userText: String
    let at: Date

    var shortLabel: String {
        if let code, !code.isEmpty {
            return humanCode(code)
        }
        if message.contains("鉴权") { return "鉴权失败" }
        if message.contains("无进展") || message.contains("首") { return "首包超时" }
        if message.contains("中断") { return "回复中断" }
        return "本条失败"
    }

    private func humanCode(_ code: String) -> String {
        switch code.lowercased() {
        case "first_event_timeout": return "首包超时"
        case "tool_stall": return "工具挂死"
        case "lock_timeout": return "会话锁超时"
        case "client_progress_stall": return "无进展"
        case "empty_stub", "empty_reply": return "空回复"
        case "partial_done", "incomplete": return "回复中断"
        case "hang", "connect_failed": return "连接失败"
        default: return code
        }
    }
}
