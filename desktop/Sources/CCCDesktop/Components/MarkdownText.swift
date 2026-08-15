import SwiftUI
import Textual

/// 聊天 Markdown：换用 Textual 渲染核心，保留公共 API
struct MarkdownText: View {
    let source: String
    var font: Font = CCCTheme.body
    var foreground: Color = CCCTheme.ink

    var body: some View {
        StructuredText(markdown: Self.preprocessMarkdown(source))
            .font(font)
            .foregroundStyle(foreground)
            .textual.textSelection(.enabled)
            .textual.structuredTextStyle(.gitHub)
    }

    private static func preprocessMarkdown(_ text: String) -> String {
        let normalized = text
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")
        
        var result = ""
        var inCodeBlock = false
        
        let lines = normalized.components(separatedBy: "\n")
        for (index, line) in lines.enumerated() {
            var processedLine = line
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            
            if line.hasPrefix("```") {
                inCodeBlock.toggle()
            } else if !inCodeBlock {
                if !trimmed.isEmpty && !line.hasSuffix("  ") && !line.hasSuffix("\\") {
                    let isBlockElement = trimmed.hasPrefix("#") ||
                                         trimmed.hasPrefix("- ") ||
                                         trimmed.hasPrefix("* ") ||
                                         trimmed.hasPrefix("+ ") ||
                                         trimmed.hasPrefix(">") ||
                                         trimmed.hasPrefix("---") ||
                                         trimmed.hasPrefix("***") ||
                                         trimmed.contains("|") ||
                                         isOpenListMatch(trimmed)
                    
                    if !isBlockElement {
                        processedLine = line + "  "
                    }
                }
            }
            result += processedLine
            if index < lines.count - 1 {
                result += "\n"
            }
        }
        return result
    }

    private static func isOpenListMatch(_ trimmed: String) -> Bool {
        guard let dotIndex = trimmed.firstIndex(of: ".") else { return false }
        let numberPart = trimmed[..<dotIndex]
        guard Int(numberPart) != nil else { return false }
        let afterDot = trimmed.index(after: dotIndex)
        guard afterDot < trimmed.endIndex, trimmed[afterDot] == " " else { return false }
        return true
    }
}
