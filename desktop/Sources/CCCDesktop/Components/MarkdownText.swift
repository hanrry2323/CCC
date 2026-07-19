import SwiftUI

/// 聊天 Markdown：按块/按行渲染，**绝不**走 AttributedString(markdown:)（会吞单换行）。
struct MarkdownText: View {
    let source: String
    var font: Font = CCCTheme.body
    var foreground: Color = CCCTheme.ink

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(blocks.enumerated()), id: \.offset) { _, block in
                switch block {
                case .paragraph(let lines):
                    VStack(alignment: .leading, spacing: 3) {
                        ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                            inlineLine(line)
                        }
                    }
                case .heading(let level, let text):
                    Text(text)
                        .font(headingFont(level))
                        .foregroundStyle(foreground)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.top, level <= 2 ? 6 : 2)
                case .bullet(let text):
                    HStack(alignment: .top, spacing: 8) {
                        Text("•")
                            .foregroundStyle(CCCTheme.secondary)
                        inlineLine(text)
                    }
                case .ordered(let n, let text):
                    HStack(alignment: .top, spacing: 8) {
                        Text("\(n).")
                            .foregroundStyle(CCCTheme.secondary)
                            .font(font)
                        inlineLine(text)
                    }
                case .code(let lang, let code):
                    VStack(alignment: .leading, spacing: 4) {
                        if !lang.isEmpty {
                            Text(lang)
                                .font(.system(size: 10, weight: .medium, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                        }
                        Text(code)
                            .font(.system(size: 12.5, design: .monospaced))
                            .foregroundStyle(CCCTheme.ink)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(Color.black.opacity(0.06))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(CCCTheme.border, lineWidth: 1)
                    )
                case .table(let headers, let rows):
                    MarkdownTableView(headers: headers, rows: rows)
                case .blank:
                    Spacer().frame(height: 4)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func inlineLine(_ raw: String) -> some View {
        Text(Self.attributedInline(raw, base: font))
            .foregroundStyle(foreground)
            .textSelection(.enabled)
            .tint(CCCTheme.accent)
            .frame(maxWidth: .infinity, alignment: .leading)
            .fixedSize(horizontal: false, vertical: true)
    }

    private func headingFont(_ level: Int) -> Font {
        switch level {
        case 1: return .system(size: 20, weight: .semibold)
        case 2: return .system(size: 17, weight: .semibold)
        case 3: return .system(size: 15, weight: .semibold)
        default: return .system(size: 14, weight: .semibold)
        }
    }

    private enum Block {
        case paragraph([String])
        case heading(level: Int, text: String)
        case bullet(String)
        case ordered(Int, String)
        case code(lang: String, code: String)
        case table(headers: [String], rows: [[String]])
        case blank
    }

    private var blocks: [Block] {
        Self.parse(source)
    }

    // MARK: - Parse

    private static func parse(_ source: String) -> [Block] {
        var result: [Block] = []
        var remaining = source
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")[...]

        while let open = remaining.range(of: "```") {
            appendProse(&result, String(remaining[..<open.lowerBound]))
            let afterOpen = remaining[open.upperBound...]
            let langEnd = afterOpen.firstIndex(of: "\n") ?? afterOpen.endIndex
            let lang = String(afterOpen[..<langEnd]).trimmingCharacters(in: .whitespacesAndNewlines)
            let bodyStart = langEnd < afterOpen.endIndex
                ? afterOpen.index(after: langEnd)
                : afterOpen.endIndex
            let bodySlice = afterOpen[bodyStart...]
            if let close = bodySlice.range(of: "```") {
                let code = String(bodySlice[..<close.lowerBound]).trimmingCharacters(in: .newlines)
                result.append(.code(lang: lang, code: code))
                remaining = bodySlice[close.upperBound...]
            } else {
                result.append(.code(lang: lang, code: String(bodySlice)))
                remaining = ""[...]
            }
        }
        appendProse(&result, String(remaining))
        if result.isEmpty, !source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            result.append(.paragraph([source]))
        }
        return result
    }

    private static func appendProse(_ result: inout [Block], _ text: String) {
        let lines = text.components(separatedBy: "\n")
        var i = 0
        var para: [String] = []

        func flushPara() {
            guard !para.isEmpty else { return }
            result.append(.paragraph(para))
            para = []
        }

        while i < lines.count {
            let line = lines[i]
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            if trimmed.isEmpty {
                flushPara()
                result.append(.blank)
                i += 1
                continue
            }

            // table
            if trimmed.contains("|"), i + 1 < lines.count, isSeparatorRow(lines[i + 1]) {
                flushPara()
                var tableLines = [line, lines[i + 1]]
                i += 2
                while i < lines.count, lines[i].contains("|") {
                    tableLines.append(lines[i])
                    i += 1
                }
                let parsed = parseTable(tableLines)
                result.append(.table(headers: parsed.0, rows: parsed.1))
                continue
            }

            // heading
            if let h = headingMatch(trimmed) {
                flushPara()
                result.append(.heading(level: h.0, text: h.1))
                i += 1
                continue
            }

            // bullet
            if trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") {
                flushPara()
                let body = String(trimmed.dropFirst(2))
                result.append(.bullet(body))
                i += 1
                continue
            }

            // ordered
            if let ord = orderedMatch(trimmed) {
                flushPara()
                result.append(.ordered(ord.0, ord.1))
                i += 1
                continue
            }

            // unglue glued filenames: foo.mdBar → keep as one visual line but insert space
            para.append(unglueExtensions(line))
            i += 1
        }
        flushPara()
    }

    private static func headingMatch(_ line: String) -> (Int, String)? {
        var n = 0
        for ch in line {
            if ch == "#" { n += 1 } else { break }
        }
        guard n >= 1, n <= 6, line.count > n, line[line.index(line.startIndex, offsetBy: n)] == " " else {
            return nil
        }
        let text = String(line.dropFirst(n + 1)).trimmingCharacters(in: .whitespaces)
        return (n, text)
    }

    private static func orderedMatch(_ line: String) -> (Int, String)? {
        guard let dot = line.firstIndex(of: ".") else { return nil }
        let numPart = line[..<dot]
        guard let n = Int(numPart), n > 0 else { return nil }
        let after = line.index(after: dot)
        guard after < line.endIndex, line[after] == " " else { return nil }
        return (n, String(line[line.index(after: after)...]))
    }

    private static func unglueExtensions(_ line: String) -> String {
        guard let re = try? NSRegularExpression(pattern: #"(\.[A-Za-z0-9]{1,8})([A-Z])"#) else {
            return line
        }
        let range = NSRange(line.startIndex..<line.endIndex, in: line)
        return re.stringByReplacingMatches(in: line, options: [], range: range, withTemplate: "$1 $2")
    }

    private static func isSeparatorRow(_ line: String) -> Bool {
        let t = line.trimmingCharacters(in: .whitespaces)
        guard t.contains("|"), t.contains("-") else { return false }
        return t.unicodeScalars.allSatisfy { ch in
            ch == "|" || ch == "-" || ch == ":" || ch == " " || ch == "\t"
        }
    }

    private static func parseTable(_ lines: [String]) -> ([String], [[String]]) {
        func cells(_ line: String) -> [String] {
            var s = line.trimmingCharacters(in: .whitespaces)
            if s.hasPrefix("|") { s.removeFirst() }
            if s.hasSuffix("|") { s.removeLast() }
            return s.split(separator: "|", omittingEmptySubsequences: false)
                .map { $0.trimmingCharacters(in: .whitespaces) }
        }
        guard lines.count >= 2 else { return ([], []) }
        let headers = cells(lines[0])
        let rows = lines.dropFirst(2).map(cells)
        return (headers, rows)
    }

    /// 行内 **bold** / `code` / *italic* — 不触发段落级 Markdown 解析
    private static func attributedInline(_ raw: String, base: Font) -> AttributedString {
        var attr = AttributedString(raw)
        attr.font = base

        // Simple rebuild: **bold**, `code`, *italic*
        var out = AttributedString()
        var s = raw[...]
        while !s.isEmpty {
            if s.hasPrefix("**"), let end = s.dropFirst(2).range(of: "**") {
                let inner = String(s[s.index(s.startIndex, offsetBy: 2)..<end.lowerBound])
                var chunk = AttributedString(inner)
                chunk.font = .system(size: 14, weight: .semibold)
                out += chunk
                s = s[end.upperBound...]
                continue
            }
            if s.hasPrefix("`"), let end = s.dropFirst().range(of: "`") {
                let inner = String(s[s.index(after: s.startIndex)..<end.lowerBound])
                var chunk = AttributedString(inner)
                chunk.font = .system(size: 12.5, design: .monospaced)
                chunk.backgroundColor = Color.black.opacity(0.06)
                out += chunk
                s = s[end.upperBound...]
                continue
            }
            if s.hasPrefix("*"), !s.hasPrefix("**"), let end = s.dropFirst().range(of: "*") {
                let inner = String(s[s.index(after: s.startIndex)..<end.lowerBound])
                var chunk = AttributedString(inner)
                chunk.font = .system(size: 14).italic()
                out += chunk
                s = s[end.upperBound...]
                continue
            }
            let ch = s.removeFirst()
            out += AttributedString(String(ch))
        }
        if out.characters.isEmpty {
            return AttributedString(raw)
        }
        return out
    }
}

private struct MarkdownTableView: View {
    let headers: [String]
    let rows: [[String]]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 0) {
                ForEach(Array(headers.enumerated()), id: \.offset) { _, h in
                    Text(h)
                        .font(.system(size: 12, weight: .semibold))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(6)
                }
            }
            .background(CCCTheme.hover)
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                Divider()
                HStack(spacing: 0) {
                    ForEach(Array(headers.indices), id: \.self) { idx in
                        Text(idx < row.count ? row[idx] : "")
                            .font(.system(size: 12))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(6)
                    }
                }
            }
        }
        .overlay(
            RoundedRectangle(cornerRadius: 6, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
    }
}
