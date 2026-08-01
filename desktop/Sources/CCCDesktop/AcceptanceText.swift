import Foundation

/// 验收行规范化（纯函数）。行为 = 原三处内联实现原样搬迁：
/// - `plainLines`：纯 trim + 过滤空行（TransferDraft.acceptanceLines / AppModel.submitTransfer 的 accLines）
/// - `bulletStrippedJoined`：额外去 `-`/`*` 列表前缀，换行连接（AppModel.normalizeAcceptance）
enum AcceptanceText {
    /// 纯 trim + 过滤空行 → 行数组
    static func plainLines(_ text: String) -> [String] {
        text
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
    }

    /// 额外去 `-`/`*` 列表前缀 → 换行连接
    static func bulletStrippedJoined(_ text: String) -> String {
        text
            .split(separator: "\n")
            .map { line -> String in
                var s = String(line).trimmingCharacters(in: .whitespaces)
                while s.hasPrefix("-") || s.hasPrefix("*") {
                    s = String(s.dropFirst()).trimmingCharacters(in: .whitespaces)
                }
                return s
            }
            .filter { !$0.isEmpty }
            .joined(separator: "\n")
    }
}
