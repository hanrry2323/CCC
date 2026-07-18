import SwiftUI

/// 聊天 Markdown：强制保留换行（单换行=硬换行），并拆开被粘连的 `.md` 文件名
struct MarkdownText: View {
    let source: String
    var font: Font = CCCTheme.body
    var foreground: Color = CCCTheme.ink

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(blocks.enumerated()), id: \.offset) { _, block in
                switch block {
                case .markdown(let text):
                    Text(parseMarkdown(Self.prepareProse(text)))
                        .font(font)
                        .foregroundStyle(foreground)
                        .textSelection(.enabled)
                        .tint(CCCTheme.accent)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .lineSpacing(4)
                        .fixedSize(horizontal: false, vertical: true)
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
                case .plainLines(let lines):
                    // 兜底：逐行渲染，绝不粘连
                    VStack(alignment: .leading, spacing: 3) {
                        ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                            Text(line.isEmpty ? " " : line)
                                .font(font)
                                .foregroundStyle(foreground)
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private enum Block {
        case markdown(String)
        case code(lang: String, code: String)
        case table(headers: [String], rows: [[String]])
        case plainLines([String])
    }

    private var blocks: [Block] {
        Self.splitBlocks(source)
    }

    private func parseMarkdown(_ text: String) -> AttributedString {
        do {
            var opts = AttributedString.MarkdownParsingOptions()
            opts.interpretedSyntax = .full
            let attr = try AttributedString(markdown: text, options: opts)
            // 若解析后几乎变成一行，而原文多行 → 降级逐行
            let srcLines = text.components(separatedBy: "\n").filter { !$0.isEmpty }.count
            let flat = String(attr.characters)
            if srcLines >= 3, !flat.contains("\n"), flat.count > 40 {
                return AttributedString(text.replacingOccurrences(of: "  \n", with: "\n"))
            }
            return attr
        } catch {
            return AttributedString(text)
        }
    }

    /// 1) 拆开 `foo.mdBar.md` 粘连  2) 每个单换行变成 Markdown 硬换行
    static func prepareProse(_ raw: String) -> String {
        var s = raw
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")
        // CHANGELOG.mdREADME.md → 换行（常见模型/传输粘连）
        if let re = try? NSRegularExpression(pattern: #"(\.[A-Za-z0-9]{1,8})([A-Z])"#) {
            let range = NSRange(s.startIndex..<s.endIndex, in: s)
            s = re.stringByReplacingMatches(in: s, options: [], range: range, withTemplate: "$1\n$2")
        }
        let lines = s.components(separatedBy: "\n")
        var out: [String] = []
        for (i, line) in lines.enumerated() {
            if i > 0 {
                let prevBlank = lines[i - 1].trimmingCharacters(in: .whitespaces).isEmpty
                let curBlank = line.trimmingCharacters(in: .whitespaces).isEmpty
                if prevBlank || curBlank {
                    out.append(line)
                } else {
                    // 硬换行：两空格 + 下一行
                    if let last = out.indices.last {
                        out[last] = out[last] + "  "
                    }
                    out.append(line)
                }
            } else {
                out.append(line)
            }
        }
        return out.joined(separator: "\n")
    }

    private static func splitBlocks(_ source: String) -> [Block] {
        var result: [Block] = []
        var remaining = source[...]
        while let open = remaining.range(of: "```") {
            let before = String(remaining[..<open.lowerBound])
            appendProseOrTable(&result, before)
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
        appendProseOrTable(&result, String(remaining))
        if result.isEmpty { result.append(.markdown(source)) }
        return result
    }

    private static func appendProseOrTable(_ result: inout [Block], _ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let lines = text.components(separatedBy: "\n")
        var i = 0
        var buf: [String] = []
        func flushBuf() {
            let chunk = buf.joined(separator: "\n")
            if !chunk.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                result.append(.markdown(chunk))
            }
            buf = []
        }
        while i < lines.count {
            let line = lines[i]
            if line.contains("|"), i + 1 < lines.count, isSeparatorRow(lines[i + 1]) {
                flushBuf()
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
            buf.append(line)
            i += 1
        }
        flushBuf()
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
