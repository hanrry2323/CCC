import SwiftUI

/// 轻量 Markdown（系统 AttributedString）
struct MarkdownText: View {
    let source: String
    var font: Font = CCCTheme.body
    var foreground: Color = CCCTheme.ink

    var body: some View {
        Text(attributed)
            .font(font)
            .foregroundStyle(foreground)
            .textSelection(.enabled)
            .tint(CCCTheme.accent)
            .frame(maxWidth: .infinity, alignment: .leading)
            .lineSpacing(3)
    }

    private var attributed: AttributedString {
        do {
            var opts = AttributedString.MarkdownParsingOptions()
            opts.interpretedSyntax = .full
            return try AttributedString(markdown: source, options: opts)
        } catch {
            return AttributedString(source)
        }
    }
}
