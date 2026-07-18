import SwiftUI

struct FlowCanvasView: View {
    let epic: FlowEpic?
    let epicId: String?
    let works: [FlowWork]
    let headline: String
    let emptyMessage: String
    var onOpenOps: (() -> Void)?
    var onSelectNode: ((String) -> Void)?

    @State private var dashPhase: CGFloat = 0
    @State private var pulse = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            if works.isEmpty && epic == nil && (epicId == nil || epicId?.isEmpty == true) {
                emptyState
            } else {
                graphBody
            }
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
                        let color = edge.active
                            ? Color(red: 0.86, green: 0.52, blue: 0.22).opacity(0.85)
                            : Color.black.opacity(0.12)
                        ctx.stroke(
                            path,
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
                    Button {
                        onSelectNode?(node.id)
                    } label: {
                        FlowNodeView(
                            node: node,
                            pulse: pulse && FlowLayout.statusColorKey(node.statusKey) == "running"
                        )
                    }
                    .buttonStyle(.plain)
                    .frame(
                        width: FlowLayout.nodeWidth,
                        height: node.kind == .epic ? FlowLayout.epicHeight : FlowLayout.nodeHeight
                    )
                    .position(
                        x: node.x + FlowLayout.nodeWidth / 2,
                        y: node.y + (node.kind == .epic ? FlowLayout.epicHeight : FlowLayout.nodeHeight) / 2
                    )
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
}

struct FlowNodeView: View {
    let node: FlowGraphNode
    var pulse: Bool = false

    private var tint: Color {
        switch FlowLayout.statusColorKey(node.statusKey) {
        case "running": return CCCTheme.nodeRunning
        case "done": return CCCTheme.nodeDone
        case "fail": return CCCTheme.nodeFail
        default: return CCCTheme.nodePending
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Text(node.badge)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(tint)
                Spacer(minLength: 0)
                Circle()
                    .fill(tint)
                    .frame(width: 5, height: 5)
                    .opacity(pulse ? 0.35 : 1)
            }
            Text(node.title)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(CCCTheme.ink)
                .lineLimit(2)
            Text(node.subtitle)
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.faint)
                .lineLimit(1)
            if let detail = node.detail, !detail.isEmpty {
                Text(detail)
                    .font(.system(size: 10))
                    .foregroundStyle(CCCTheme.faint.opacity(0.9))
                    .lineLimit(1)
            }
        }
        .padding(11)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
        .contentShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .animation(.easeInOut(duration: 0.28), value: node.statusKey)
    }
}
