import Foundation
import SwiftUI

// MARK: - Tool progress（Cursor / OpenCode 式：折叠摘要 + SF Symbol）

struct ToolStep: Identifiable, Hashable, Codable {
    enum Status: String, Hashable, Codable { case running, done, error }

    let id: UUID
    var name: String
    var label: String
    var icon: String
    var status: Status
    /// toolResult 后推断的一句摘要（成功/失败）；旧盘无此字段
    var resultHint: String?

    enum CodingKeys: String, CodingKey {
        case id, name, label, icon, status, resultHint
    }

    init(
        id: UUID = UUID(),
        name: String,
        label: String,
        icon: String,
        status: Status = .running,
        resultHint: String? = nil
    ) {
        self.id = id
        self.name = name
        self.label = label
        self.icon = icon
        self.status = status
        self.resultHint = resultHint
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
        icon = try c.decodeIfPresent(String.self, forKey: .icon) ?? "wrench"
        status = try c.decodeIfPresent(Status.self, forKey: .status) ?? .done
        resultHint = try c.decodeIfPresent(String.self, forKey: .resultHint)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id.uuidString, forKey: .id)
        try c.encode(name, forKey: .name)
        try c.encode(label, forKey: .label)
        try c.encode(icon, forKey: .icon)
        try c.encode(status, forKey: .status)
        try c.encodeIfPresent(resultHint, forKey: .resultHint)
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

    /// SF Symbol 名（不再用 emoji）
    static let symbols: [String: String] = [
        "Read": "doc.text",
        "Glob": "magnifyingglass",
        "Grep": "magnifyingglass",
        "Write": "square.and.pencil",
        "Edit": "pencil",
        "StrReplace": "pencil",
        "MultiEdit": "rectangle.stack.badge.plus",
        "Bash": "terminal",
        "Shell": "terminal",
        "LS": "folder",
        "Task": "arrow.triangle.branch",
        "WebFetch": "globe",
        "WebSearch": "globe",
        "TodoWrite": "checklist",
        "NotebookEdit": "book",
    ]

    /// 兼容旧持久化 emoji → 仍映射到 symbol
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

    /// toolResult 后一句摘要（不依赖 sidecar payload）
    static func resultHint(name: String, ok: Bool, label: String) -> String {
        if !ok { return "调用失败" }
        let detail: String? = {
            if let r = label.range(of: " · ") {
                let d = String(label[r.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
                return d.isEmpty ? nil : short(d, 36)
            }
            return nil
        }()
        switch name {
        case "Write", "Edit", "StrReplace", "MultiEdit", "NotebookEdit":
            return detail.map { "已写入 \($0)" } ?? "已写入"
        case "Read", "LS":
            return detail.map { "已查阅 \($0)" } ?? "查阅完成"
        case "Bash", "Shell":
            return "命令完成"
        case "Grep", "Glob":
            return "搜索完成"
        case "WebSearch", "WebFetch":
            return "请求完成"
        case "Task":
            return "子任务完成"
        case "TodoWrite":
            return "待办已更新"
        default:
            return "调用完成"
        }
    }

    static func icon(for name: String) -> String { symbols[name] ?? "wrench.and.screwdriver" }

    static func isWrite(_ name: String) -> Bool { writeTools.contains(name) }

    static func sfSymbol(for step: ToolStep) -> String {
        symbols[step.name] ?? "wrench.and.screwdriver"
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

    @State private var expanded = false

    private var isThinking: Bool { !finished && steps.isEmpty }
    private var isRunningTools: Bool { !finished && !steps.isEmpty }

    var body: some View {
        Group {
            if isThinking {
                thinkingLine
            } else if isRunningTools {
                runningBlock
            } else if !steps.isEmpty || filesChanged > 0 {
                finishedBlock
            }
        }
        // 仅对 finished 折叠；勿绑 steps.count（追加 step 会整块闪）
        .animation(.easeOut(duration: 0.2), value: finished)
        .onAppear {
            expanded = !finished
        }
        .onChange(of: finished) { done in
            if done { expanded = false }
        }
    }

    private var thinkingLine: some View {
        HStack(spacing: 8) {
            ProgressView()
                .controlSize(.mini)
            Text(placeholder ?? "正在思考…")
                .font(.system(size: 13))
                .foregroundStyle(CCCTheme.faint)
                .italic()
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 4)
        .padding(.vertical, 4)
        .accessibilityLabel(placeholder ?? "正在思考")
    }

    private var runningBlock: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let current = steps.last {
                HStack(spacing: 8) {
                    ProgressView()
                        .controlSize(.mini)
                    Image(systemName: ToolProgressHelper.sfSymbol(for: current))
                        .font(.system(size: 12))
                        .foregroundStyle(CCCTheme.accent)
                        .frame(width: 16)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(current.label)
                            .font(.system(size: 13))
                            .foregroundStyle(CCCTheme.ink)
                            .lineLimit(2)
                        if let hint = current.resultHint, !hint.isEmpty {
                            Text(hint)
                                .font(.system(size: 11.5))
                                .foregroundStyle(CCCTheme.secondary)
                                .lineLimit(1)
                        }
                    }
                    Spacer(minLength: 0)
                }
            }
            segmentProgressTrack
            if steps.count > 1 {
                DisclosureGroup(isExpanded: $expanded) {
                    stepList(Array(steps.dropLast()))
                } label: {
                    Text("先前 \(steps.count - 1) 步")
                        .font(.system(size: 12))
                        .foregroundStyle(CCCTheme.faint)
                }
                .id("prior-steps")
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(CCCTheme.hover)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
    }

    /// 分段进度轨：done / running / error / 未达
    private var segmentProgressTrack: some View {
        HStack(spacing: 2) {
            ForEach(Array(steps.enumerated()), id: \.element.id) { _, step in
                RoundedRectangle(cornerRadius: 1.5, style: .continuous)
                    .fill(segmentFill(step.status))
                    .frame(height: 3)
                    .overlay {
                        if step.status == .running {
                            ProgressView()
                                .controlSize(.mini)
                                .scaleEffect(0.45)
                                .opacity(0.85)
                        }
                    }
            }
        }
        .frame(maxWidth: .infinity)
        .accessibilityLabel("工具进度 \(steps.filter { $0.status == .done }.count)/\(steps.count)")
    }

    private func segmentFill(_ s: ToolStep.Status) -> Color {
        switch s {
        case .done: return CCCTheme.nodeDone
        case .running: return CCCTheme.accent
        case .error: return CCCTheme.nodeFail
        }
    }

    private var finishedBlock: some View {
        DisclosureGroup(isExpanded: $expanded) {
            stepList(steps)
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 13))
                    .foregroundStyle(CCCTheme.nodeDone)
                Text(finishedSummary)
                    .font(.system(size: 13))
                    .foregroundStyle(CCCTheme.secondary)
                Spacer(minLength: 0)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(CCCTheme.hover.opacity(0.7))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
    }

    private var finishedSummary: String {
        let n = steps.count
        if n > 0 {
            let base = "已用 \(n) 个工具"
            return filesChanged > 0 ? "\(base) · 改了 \(filesChanged) 个文件" : base
        }
        return filesChanged > 0 ? "完成 · 改了 \(filesChanged) 个文件" : "完成"
    }

    private func stepList(_ list: [ToolStep]) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            ForEach(list.suffix(16), id: \.id) { step in
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Image(systemName: statusSymbol(step.status))
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(statusColor(step.status))
                        .frame(width: 12)
                    Image(systemName: ToolProgressHelper.sfSymbol(for: step))
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.secondary)
                        .frame(width: 14)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(step.label)
                            .font(.system(size: 12.5))
                            .foregroundStyle(CCCTheme.ink.opacity(0.88))
                            .lineLimit(2)
                        if let hint = step.resultHint, !hint.isEmpty {
                            Text(hint)
                                .font(.system(size: 11))
                                .foregroundStyle(CCCTheme.faint)
                                .lineLimit(1)
                        }
                    }
                    Spacer(minLength: 0)
                }
            }
        }
        .padding(.top, 4)
    }

    private func statusSymbol(_ s: ToolStep.Status) -> String {
        switch s {
        case .running: return "circle.fill"
        case .done: return "checkmark"
        case .error: return "xmark"
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
