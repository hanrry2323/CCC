import AppKit
import SwiftUI

/// 卡片右下角「快捷复制」：复制给人/Agent 的定位短串，免打字。
enum CardLocator {
    static func line(
        project: String?,
        thread: String? = nil,
        kind: String,
        id: String?,
        title: String? = nil,
        stage: String? = nil,
        parent: String? = nil,
        column: String? = nil
    ) -> String {
        var parts: [String] = []
        if let p = project?.trimmingCharacters(in: .whitespacesAndNewlines), !p.isEmpty {
            parts.append("project=\(p)")
        }
        if let t = thread?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty {
            parts.append("thread=\(t)")
        }
        parts.append("kind=\(kind)")
        if let i = id?.trimmingCharacters(in: .whitespacesAndNewlines), !i.isEmpty {
            parts.append("id=\(i)")
        }
        if let parent, !parent.isEmpty {
            parts.append("parent=\(parent)")
        }
        if let column, !column.isEmpty {
            parts.append("column=\(column)")
        }
        if let stage, !stage.isEmpty {
            parts.append("stage=\(stage)")
        }
        if let title, !title.isEmpty {
            let t = title.replacingOccurrences(of: "\n", with: " ")
            parts.append("title=\(String(t.prefix(80)))")
        }
        return parts.joined(separator: " · ")
    }
}

struct LocatorCopyButton: View {
    let text: String
    var helpText: String = "复制定位信息（发给 Agent）"
    @State private var copied = false

    var body: some View {
        Button {
            let pb = NSPasteboard.general
            pb.clearContents()
            pb.setString(text, forType: .string)
            copied = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
                copied = false
            }
        } label: {
            Image(systemName: copied ? "checkmark" : "doc.on.doc")
                .font(.system(size: 9, weight: .semibold))
                .foregroundStyle(copied ? CCCTheme.nodeDone : CCCTheme.faint)
                .frame(width: 18, height: 18)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help(helpText)
        .accessibilityLabel(helpText)
    }
}
