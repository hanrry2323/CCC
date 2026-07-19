import SwiftUI

struct FlowCanvasView: View {
    let epic: FlowEpic?
    let epicId: String?
    let works: [FlowWork]
    let headline: String
    let emptyMessage: String
    /// AppModel 在 epic 首次扇出 / 切会话时递增，驱动出生动画重启
    var splitGeneration: UInt64 = 0
    var onOpenOps: (() -> Void)?
    var onSelectNode: ((String) -> Void)?

    @State private var dashPhase: CGFloat = 0
    @State private var pulse = false
    /// 已显现的 work id（按层 stagger）
    @State private var revealedWorkIds: Set<String> = []
    /// 边生长 0…1
    @State private var edgeProgress: CGFloat = 0
    /// epic「拆解中」脉冲
    @State private var splittingPulse = false
    @State private var animToken: UInt64 = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            if works.isEmpty && epic == nil && (epicId == nil || epicId?.isEmpty == true) {
                emptyState
            } else {
                graphBody
            }
        }
        .onChange(of: splitGeneration) { _ in
            restartSplitAnimation()
        }
        .onChange(of: works) { _ in
            // 同世代内 works 陆续到达：补跑显现（FlowWork: Hashable）
            if !works.isEmpty, revealedWorkIds.count < works.count {
                runRevealSequence(token: animToken)
            }
        }
        .onAppear {
            restartSplitAnimation()
        }
    }

    private var header: some View {
        Group {
            if !headline.isEmpty {
                Text(headline)
                    .font(.system(size: 12.5, weight: .medium))
                    .foregroundStyle(CCCTheme.muted)
                    .lineLimit(2)
                    .padding(.horizontal, 16)
                    .padding(.top, 4)
                    .padding(.bottom, 8)
            } else if (epic != nil || !(epicId ?? "").isEmpty), works.isEmpty {
                Text(splittingPulse ? "拆解中…" : "待拆解")
                    .font(.system(size: 12.5, weight: .medium))
                    .foregroundStyle(CCCTheme.accent.opacity(0.85))
                    .padding(.horizontal, 16)
                    .padding(.top, 4)
                    .padding(.bottom, 8)
            }
        }
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 8) {
            Spacer(minLength: 36)
            Text("转任务后，流程会出现在这里")
                .font(.system(size: 13, weight: .regular))
                .foregroundStyle(CCCTheme.faint)
                .fixedSize(horizontal: false, vertical: true)
            if !emptyMessage.isEmpty {
                Text(emptyMessage)
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint.opacity(0.85))
            }
            Spacer()
        }
        .padding(20)
    }

    private var graphBody: some View {
        let laid = FlowLayout.layout(epic: epic, epicId: epicId, works: works)
        return ScrollView([.horizontal, .vertical]) {
            ZStack(alignment: .topLeading) {
                Canvas { ctx, _ in
                    for edge in laid.edges {
                        guard let a = laid.nodes.first(where: { $0.id == edge.from }),
                              let b = laid.nodes.first(where: { $0.id == edge.to })
                        else { continue }
                        // 边：两端节点都显现后才画
                        let fromOk = a.kind == .epic || revealedWorkIds.contains(a.id)
                        let toOk = revealedWorkIds.contains(b.id) || b.kind == .epic
                        guard fromOk, toOk, edgeProgress > 0.01 else { continue }

                        let fromH = a.kind == .epic ? FlowLayout.epicHeight : FlowLayout.nodeHeight
                        let start = CGPoint(x: a.x + FlowLayout.nodeWidth / 2, y: a.y + fromH)
                        let end = CGPoint(x: b.x + FlowLayout.nodeWidth / 2, y: b.y)
                        var path = Path()
                        path.move(to: start)
                        let midY = (start.y + end.y) / 2
                        path.addCurve(
                            to: end,
                            control1: CGPoint(x: start.x, y: midY),
                            control2: CGPoint(x: end.x, y: midY)
                        )
                        let trimmed = path.trimmedPath(from: 0, to: min(1, edgeProgress))
                        let color = edge.active
                            ? Color(red: 0.86, green: 0.52, blue: 0.22).opacity(0.85)
                            : Color.black.opacity(0.12)
                        ctx.stroke(
                            trimmed,
                            with: .color(color),
                            style: StrokeStyle(
                                lineWidth: edge.active ? 2.0 : 1.2,
                                lineCap: .round,
                                dash: edge.active ? [6, 4] : [],
                                dashPhase: edge.active ? dashPhase : 0
                            )
                        )
                    }
                }
                .frame(width: laid.size.width, height: laid.size.height)

                ForEach(laid.nodes) { node in
                    let visible: Bool = {
                        if node.kind == .epic { return true }
                        return revealedWorkIds.contains(node.id)
                    }()
                    Button {
                        onSelectNode?(node.id)
                    } label: {
                        FlowNodeView(
                            node: node,
                            pulse: (pulse && FlowLayout.statusColorKey(node.statusKey) == "running")
                                || (node.kind == .epic && works.isEmpty && splittingPulse)
                        )
                    }
                    .buttonStyle(.plain)
                    .frame(
                        width: FlowLayout.nodeWidth,
                        height: node.kind == .epic ? FlowLayout.epicHeight : FlowLayout.nodeHeight
                    )
                    .opacity(visible ? 1 : 0)
                    .offset(y: visible ? 0 : 12)
                    .position(
                        x: node.x + FlowLayout.nodeWidth / 2,
                        y: node.y + (node.kind == .epic ? FlowLayout.epicHeight : FlowLayout.nodeHeight) / 2
                    )
                    .animation(.easeOut(duration: 0.35), value: revealedWorkIds)
                }
            }
            .frame(width: laid.size.width, height: laid.size.height)
            .padding(8)
        }
        .onAppear {
            withAnimation(.linear(duration: 1.1).repeatForever(autoreverses: false)) {
                dashPhase = 20
            }
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                pulse = true
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if works.contains(where: \.isFailed) {
                Button("在 Hub 运维中查看") { onOpenOps?() }
                    .font(CCCTheme.caption)
                    .buttonStyle(.plain)
                    .foregroundStyle(CCCTheme.accent)
                    .padding(12)
            }
        }
    }

    private func restartSplitAnimation() {
        animToken &+= 1
        let token = animToken
        revealedWorkIds = []
        edgeProgress = 0
        if works.isEmpty {
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                splittingPulse = true
            }
            return
        }
        splittingPulse = false
        runRevealSequence(token: token)
    }

    private func runRevealSequence(token: UInt64) {
        let layers = FlowLayout.layers(works: works)
        Task { @MainActor in
            // 短暂停：epic「拆解中」感
            try? await Task.sleep(nanoseconds: 180_000_000)
            guard token == animToken else { return }
            for layer in layers {
                guard token == animToken else { return }
                withAnimation(.easeOut(duration: 0.32)) {
                    for w in layer {
                        revealedWorkIds.insert(w.id)
                    }
                }
                try? await Task.sleep(nanoseconds: 220_000_000)
            }
            guard token == animToken else { return }
            withAnimation(.easeOut(duration: 0.45)) {
                edgeProgress = 1
            }
        }
    }
}

struct FlowNodeView: View {
    let node: FlowGraphNode
    var pulse: Bool = false

    private var colorKey: String { FlowLayout.statusColorKey(node.statusKey) }
    private var isFail: Bool { colorKey == "fail" }
    private var isRunning: Bool { colorKey == "running" }

    private var tint: Color {
        switch colorKey {
        case "running": return CCCTheme.nodeRunning
        case "done": return CCCTheme.nodeDone
        case "fail": return CCCTheme.nodeFail
        default: return CCCTheme.nodePending
        }
    }

    /// 执行器图标（按 badge 文本启发式映射）
    private var executorIcon: String {
        let b = node.badge.lowercased()
        if b.contains("opencode") || b.contains("dev") { return "terminal" }
        if b.contains("claude") || b.contains("loop-code") || b.contains("product") { return "cpu" }
        if b.contains("python") { return "curlybraces" }
        if b.contains("review") || b.contains("tester") { return "checkmark.shield" }
        if b.contains("kb") { return "books.vertical" }
        if b.contains("ops") { return "stethoscope" }
        return "cpu"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Image(systemName: executorIcon)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(tint)
                Text(node.badge)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(tint)
                    .lineLimit(1)
                Spacer(minLength: 0)
                Circle()
                    .fill(tint)
                    .frame(width: 5, height: 5)
                    .scaleEffect(pulse ? 1.35 : 1.0)
                    .opacity(pulse ? 0.35 : 1)
            }
            Text(node.title)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(CCCTheme.ink)
                .lineLimit(2)
            Text(node.subtitle)
                .font(.system(size: 11))
                .foregroundStyle(isFail ? CCCTheme.nodeFail : CCCTheme.faint)
                .lineLimit(1)
            if let detail = node.detail, !detail.isEmpty {
                Text(detail)
                    .font(.system(size: 10))
                    .foregroundStyle(isFail ? CCCTheme.nodeFail.opacity(0.9) : CCCTheme.faint.opacity(0.9))
                    .lineLimit(isFail ? 3 : 1)
            }
        }
        .padding(11)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(CCCTheme.surface, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(
                    isFail ? CCCTheme.nodeFail.opacity(0.85) : CCCTheme.border,
                    lineWidth: isFail ? 1.8 : 1
                )
        )
        .shadow(
            color: isFail ? CCCTheme.nodeFail.opacity(0.35) : (isRunning ? tint.opacity(0.18) : .clear),
            radius: isFail ? 6 : (isRunning ? 3 : 0),
            x: 0, y: 0
        )
        .contentShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .animation(.easeInOut(duration: 0.28), value: node.statusKey)
    }
}
