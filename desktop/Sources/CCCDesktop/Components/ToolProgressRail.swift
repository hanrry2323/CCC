import Foundation
import SwiftUI

// MARK: - Tool progress (Hub agent-progress 语义)

struct ToolStep: Identifiable, Hashable {
    enum Status: Hashable { case running, done, error }

    let id: UUID
    var name: String
    var label: String
    var icon: String
    var status: Status

    init(
        id: UUID = UUID(),
        name: String,
        label: String,
        icon: String,
        status: Status = .running
    ) {
        self.id = id
        self.name = name
        self.label = label
        self.icon = icon
        self.status = status
    }
}

enum ToolProgressHelper {
    static let labels: [String: String] = [
        "Read": "查阅文件",
        "Glob": "查找文件",
        "Grep": "搜索代码",
        "Write": "写入文件",
        "Edit": "修改文件",
        "StrReplace": "修改文件",
        "Bash": "运行命令",
        "Shell": "运行命令",
        "Task": "子任务",
        "WebFetch": "读取网页",
        "WebSearch": "检索资料",
        "NotebookEdit": "编辑笔记",
        "TodoWrite": "更新待办",
    ]

    static let icons: [String: String] = [
        "Read": "📄",
        "Glob": "🔎",
        "Grep": "🔎",
        "Write": "✏️",
        "Edit": "✏️",
        "StrReplace": "✏️",
        "Bash": "⌘",
        "Shell": "⌘",
        "Task": "▸",
        "WebFetch": "🌐",
        "WebSearch": "🌐",
        "TodoWrite": "☑",
    ]

    static let writeTools: Set<String> = ["Write", "Edit", "StrReplace", "NotebookEdit"]

    static func humanLabel(name: String, input: [String: Any]?) -> String {
        let base = labels[name] ?? "处理中"
        guard let inp = input else { return base }
        let file = (inp["file_path"] as? String)
            ?? (inp["path"] as? String)
            ?? (inp["target_file"] as? String)
            ?? (inp["file"] as? String)
        if let file, !file.isEmpty, name == "Read" || writeTools.contains(name) || name == "Glob" {
            return base + " · " + leaf(file)
        }
        if name == "Bash" || name == "Shell" {
            if let d = inp["description"] as? String, !d.isEmpty {
                return base + " · " + short(d, 40)
            }
            if let cmd = (inp["command"] as? String) ?? (inp["cmd"] as? String), !cmd.isEmpty {
                return base + " · " + short(cmd, 42)
            }
        }
        if name == "Grep", let p = (inp["pattern"] as? String) ?? (inp["query"] as? String) {
            return "搜索 · " + short(p, 28)
        }
        if name == "Glob", let g = inp["glob_pattern"] as? String {
            return base + " · " + short(g, 28)
        }
        if name == "WebSearch", let q = (inp["search_term"] as? String) ?? (inp["query"] as? String) {
            return base + " · " + short(q, 28)
        }
        if name == "WebFetch", let url = inp["url"] as? String {
            if let host = URL(string: url)?.host { return base + " · " + short(host, 24) }
        }
        if name == "Task", let d = (inp["description"] as? String) ?? (inp["prompt"] as? String) {
            return base + " · " + short(d, 32)
        }
        return base
    }

    static func icon(for name: String) -> String { icons[name] ?? "•" }

    static func isWrite(_ name: String) -> Bool { writeTools.contains(name) }

    static func filePath(from input: [String: Any]?) -> String? {
        guard let inp = input else { return nil }
        return (inp["file_path"] as? String)
            ?? (inp["path"] as? String)
            ?? (inp["target_file"] as? String)
            ?? (inp["file"] as? String)
    }

    private static func leaf(_ p: String) -> String {
        (p as NSString).lastPathComponent
    }

    private static func short(_ s: String, _ n: Int) -> String {
        let t = s.replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if t.count <= n { return t }
        return String(t.prefix(n - 1)) + "…"
    }
}

struct ToolProgressRail: View {
    let steps: [ToolStep]
    let filesChanged: Int
    var finished: Bool = false
    var placeholder: String? = nil

    private var headline: String {
        if finished {
            return filesChanged > 0 ? "完成 · ✏️ \(filesChanged) 个文件已修改" : "完成"
        }
        if let last = steps.last {
            let extra = filesChanged > 0 ? "  ·  已改 \(filesChanged) 文件" : ""
            return last.label + extra
        }
        return placeholder ?? "准备中…"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                if !finished {
                    ProgressView().controlSize(.mini)
                }
                Text(headline)
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.secondary)
                    .lineLimit(2)
                Spacer(minLength: 0)
                if filesChanged > 0 {
                    Text("✏️ \(filesChanged)")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            if !steps.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 4) {
                        ForEach(steps.suffix(10)) { step in
                            Text(step.icon)
                                .font(.system(size: 13))
                                .padding(.horizontal, 5)
                                .padding(.vertical, 3)
                                .background(
                                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                                        .fill(stepBackground(step.status))
                                )
                                .opacity(step.status == .running ? 1 : 0.75)
                                .help(step.label)
                        }
                    }
                }
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(CCCTheme.hover.opacity(0.85))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
    }

    private func stepBackground(_ status: ToolStep.Status) -> Color {
        switch status {
        case .running: return CCCTheme.accent.opacity(0.18)
        case .done: return CCCTheme.nodeDone.opacity(0.15)
        case .error: return CCCTheme.nodeFail.opacity(0.15)
        }
    }
}
