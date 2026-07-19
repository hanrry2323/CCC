import Foundation
import SwiftUI

// MARK: - Tool progress（必须可见：步骤列表，不只 emoji）

struct ToolStep: Identifiable, Hashable, Codable {
    enum Status: String, Hashable, Codable { case running, done, error }

    let id: UUID
    var name: String
    var label: String
    var icon: String
    var status: Status

    enum CodingKeys: String, CodingKey {
        case id, name, label, icon, status
    }

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

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        if let s = try? c.decode(String.self, forKey: .id), let u = UUID(uuidString: s) {
            id = u
        } else {
            id = (try? c.decode(UUID.self, forKey: .id)) ?? UUID()
        }
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? "tool"
        label = try c.decodeIfPresent(String.self, forKey: .label) ?? name
        icon = try c.decodeIfPresent(String.self, forKey: .icon) ?? "🔧"
        status = try c.decodeIfPresent(Status.self, forKey: .status) ?? .done
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
        "MultiEdit": "批量修改",
        "LS": "列出目录",
    ]

    static let icons: [String: String] = [
        "Read": "📄",
        "Glob": "🔎",
        "Grep": "🔎",
        "Write": "✏️",
        "Edit": "✏️",
        "StrReplace": "✏️",
        "MultiEdit": "✏️",
        "Bash": "⌘",
        "Shell": "⌘",
        "LS": "📂",
        "Task": "▸",
        "WebFetch": "🌐",
        "WebSearch": "🌐",
        "TodoWrite": "☑",
    ]

    static let writeTools: Set<String> = ["Write", "Edit", "StrReplace", "NotebookEdit", "MultiEdit"]

    static func humanLabel(name: String, input: [String: Any]?) -> String {
        let base = labels[name] ?? name
        guard let inp = input else { return base }
        let file = (inp["file_path"] as? String)
            ?? (inp["path"] as? String)
            ?? (inp["target_file"] as? String)
            ?? (inp["file"] as? String)
        if let file, !file.isEmpty {
            return base + " · " + leaf(file)
        }
        if name == "Bash" || name == "Shell" {
            if let d = inp["description"] as? String, !d.isEmpty {
                return base + " · " + short(d, 48)
            }
            if let cmd = (inp["command"] as? String) ?? (inp["cmd"] as? String), !cmd.isEmpty {
                return base + " · " + short(cmd, 48)
            }
        }
        if name == "Grep", let p = (inp["pattern"] as? String) ?? (inp["query"] as? String) {
            return "搜索 · " + short(p, 36)
        }
        if name == "Glob", let g = inp["glob_pattern"] as? String {
            return base + " · " + short(g, 36)
        }
        if name == "WebSearch", let q = (inp["search_term"] as? String) ?? (inp["query"] as? String) {
            return base + " · " + short(q, 36)
        }
        if name == "WebFetch", let url = inp["url"] as? String {
            if let host = URL(string: url)?.host { return base + " · " + short(host, 28) }
        }
        if name == "Task", let d = (inp["description"] as? String) ?? (inp["prompt"] as? String) {
            return base + " · " + short(d, 36)
        }
        return base
    }

    static func icon(for name: String) -> String { icons[name] ?? "•" }

    static func isWrite(_ name: String) -> Bool { writeTools.contains(name) }

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
            let n = steps.count
            if n > 0 {
                let base = "已完成 \(n) 步工具"
                return filesChanged > 0 ? "\(base) · 改了 \(filesChanged) 个文件" : base
            }
            return filesChanged > 0 ? "完成 · 改了 \(filesChanged) 个文件" : "完成"
        }
        if let last = steps.last {
            return last.label
        }
        return placeholder ?? "正在思考…"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                if !finished {
                    ProgressView().controlSize(.mini)
                } else {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(CCCTheme.nodeDone)
                }
                Text(headline)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(CCCTheme.secondary)
                    .lineLimit(2)
                Spacer(minLength: 0)
            }

            if steps.isEmpty, !finished {
                Text(placeholder ?? "正在思考 / 准备调用工具…")
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
            }

            // 步骤列表（必须可见文字，不只 emoji）
            if !steps.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(steps.suffix(12))) { step in
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Text(statusGlyph(step.status))
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundStyle(statusColor(step.status))
                                .frame(width: 12)
                            Text(step.icon)
                                .font(.system(size: 12))
                            Text(step.label)
                                .font(.system(size: 11.5))
                                .foregroundStyle(CCCTheme.ink.opacity(0.85))
                                .lineLimit(2)
                            Spacer(minLength: 0)
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
                .fill(CCCTheme.hover.opacity(0.9))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
        .animation(.easeOut(duration: 0.12), value: steps.count)
        .animation(.easeOut(duration: 0.12), value: finished)
    }

    private func statusGlyph(_ s: ToolStep.Status) -> String {
        switch s {
        case .running: return "●"
        case .done: return "✓"
        case .error: return "!"
        }
    }

    private func statusColor(_ s: ToolStep.Status) -> Color {
        switch s {
        case .running: return CCCTheme.accent
        case .done: return CCCTheme.nodeDone
        case .error: return CCCTheme.nodeFail
        }
    }
}
