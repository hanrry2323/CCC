import Foundation
import SwiftUI

// MARK: - Tool progress（Cursor 式：默认折叠 + 一句轮播 + 分段进度轨）

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

    /// toolResult 后一句摘要（展开列表副行；轮播主文用 label）
    static func resultHint(name: String, ok: Bool, label: String) -> String {
        if !ok { return "调用失败" }
        let detail: String? = {
            if let r = label.range(of: " · ") {
                let d = String(label[r.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
                return d.isEmpty ? nil : short(d, 40)
            }
            return nil
        }()
        switch name {
        case "Write", "Edit", "StrReplace", "MultiEdit", "NotebookEdit":
            return detail.map { "已写入 \($0)" } ?? "已写入"
        case "Read", "LS":
            return detail.map { "已查阅 \($0)" } ?? "查阅完成"
        case "Bash", "Shell":
            return detail.map { "已执行 \($0)" } ?? "命令已执行"
        case "Grep", "Glob":
            return detail.map { "已搜索 \($0)" } ?? "搜索完成"
        case "WebSearch", "WebFetch":
            return detail.map { "已请求 \($0)" } ?? "请求完成"
        case "Task":
            return detail.map { "子任务 · \($0)" } ?? "子任务完成"
        case "TodoWrite":
            return "待办已更新"
        default:
            return detail.map { "完成 · \($0)" } ?? "调用完成"
        }
    }

    /// 轮播主文：每步执行简介（label）一句话；失败才用 resultHint
    static func carouselLine(for step: ToolStep) -> String {
        if step.status == .error {
            if let hint = step.resultHint, !hint.isEmpty { return hint }
        }
        let line = step.label.trimmingCharacters(in: .whitespacesAndNewlines)
        return line.isEmpty ? (step.resultHint ?? step.name) : line
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
    /// 流式状态栏文案（如「对齐基线：生成中…」）；优先于默认思考占位
    var statusHint: String? = nil

    /// 默认折叠；用户点开才展开（禁止 onAppear 翻开造成闪）
    @State private var expanded = false
    @State private var carouselIndex = 0

    private var isThinking: Bool { !finished && steps.isEmpty }
    private var isRunningTools: Bool { !finished && !steps.isEmpty }

    private var thinkingLabel: String {
        let hint = (statusHint ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if !hint.isEmpty { return hint }
        return placeholder ?? "正在思考…"
    }

    private var carouselLines: [String] {
        steps.suffix(8).map { ToolProgressHelper.carouselLine(for: $0) }
    }

    private var carouselText: String {
        // 有进行中的一步：钉住该步简介（转圈旁一句话）
        if let running = steps.last(where: { $0.status == .running }) {
            return ToolProgressHelper.carouselLine(for: running)
        }
        let lines = carouselLines
        guard !lines.isEmpty else { return placeholder ?? "调用工具…" }
        let i = carouselIndex % lines.count
        return lines[i]
    }

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
        // 禁止绑 steps.count 动画（追加会闪）
        .animation(nil, value: steps.count)
        .animation(.easeOut(duration: 0.15), value: finished)
        .onChange(of: finished) { done in
            if done { expanded = false }
        }
        .onChange(of: steps.count) { _ in
            // 新 step 落到最新一句；不触发展开
            let n = carouselLines.count
            if n > 0 { carouselIndex = n - 1 }
        }
        .task(id: "\(isRunningTools)-\(steps.count)") {
            guard isRunningTools else { return }
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_600_000_000)
                guard !Task.isCancelled, isRunningTools else { return }
                let n = carouselLines.count
                guard n > 1 else { continue }
                carouselIndex = (carouselIndex + 1) % n
            }
        }
    }

    private var thinkingLine: some View {
        HStack(spacing: 8) {
            ProgressView()
                .controlSize(.mini)
            Text(thinkingLabel)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(CCCTheme.secondary)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(CCCTheme.surface)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
        .accessibilityLabel(thinkingLabel)
    }

    /// 进行中：无绿勾；一句轮播 + 进度轨；默认折叠步骤列表
    private var runningBlock: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                ProgressView()
                    .controlSize(.mini)
                Image(systemName: "wrench.and.screwdriver")
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.accent)
                    .frame(width: 16)
                Text(carouselText)
                    .font(.system(size: 13))
                    .foregroundStyle(CCCTheme.ink)
                    .lineLimit(1)
                    .id("carousel-\(carouselIndex)-\(steps.count)")
                    .transition(.opacity)
                Spacer(minLength: 0)
                Text("\(steps.filter { $0.status == .done }.count)/\(steps.count)")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(CCCTheme.faint)
            }
            .animation(.easeOut(duration: 0.2), value: carouselIndex)

            segmentProgressTrack

            DisclosureGroup(isExpanded: $expanded) {
                stepList(steps)
            } label: {
                Text(expanded ? "收起步骤" : "展开 \(steps.count) 步")
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.faint)
            }
            .id("tool-steps-disclosure")
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

    /// 分段进度轨：done / running / error（固定高度，防闪）
    private var segmentProgressTrack: some View {
        HStack(spacing: 2) {
            ForEach(steps, id: \.id) { step in
                RoundedRectangle(cornerRadius: 1.5, style: .continuous)
                    .fill(segmentFill(step.status))
                    .frame(height: 3)
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: 3)
        .accessibilityLabel("工具进度 \(steps.filter { $0.status == .done }.count)/\(steps.count)")
    }

    private func segmentFill(_ s: ToolStep.Status) -> Color {
        switch s {
        case .done: return CCCTheme.nodeDone
        case .running: return CCCTheme.accent
        case .error: return CCCTheme.nodeFail
        }
    }

    /// 整轮结束后才出现绿勾
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
