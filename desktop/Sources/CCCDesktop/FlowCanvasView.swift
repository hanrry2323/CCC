import SwiftUI

/// 右栏单列时间线：epic → 竖轨 → work 卡（按依赖深度 + 看板阶段排序）
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

    @State private var pulse = false
    @State private var revealedWorkIds: Set<String> = []
    /// 已知 work id 集合（用于判断「真正增长」 vs 同 id 状态更新）
    @State private var seenWorkIds: Set<String> = []
    @State private var splittingPulse = false
    @State private var animToken: UInt64 = 0

    private var ordered: [FlowWork] { FlowLayout.orderedWorks(works) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            if works.isEmpty && epic == nil && (epicId == nil || epicId?.isEmpty == true) {
                emptyState
            } else {
                timelineBody
            }
        }
        .onChange(of: splitGeneration) { _ in
            restartSplitAnimation()
        }
        .onChange(of: epicIdSignature) { _ in
            // 真正的「换 epic」才触发 reveal；同 epic 内 SSE 增量不重启动画
            seenWorkIds.removeAll()
            restartSplitAnimation()
        }
        .onChange(of: works) { _ in
            // 实际增长（出现新 work id）才 stagger；纯状态更新不重放
            let incoming = Set(works.map(\.id))
            let fresh = incoming.subtracting(seenWorkIds).subtracting(revealedWorkIds)
            if !fresh.isEmpty {
                runRevealSequence(newIds: Array(fresh), token: animToken)
            }
            seenWorkIds.formUnion(incoming)
        }
        .onAppear {
            seenWorkIds = Set(works.map(\.id))
            restartSplitAnimation()
        }
    }

    /// 仅 pending/planned 且无 works 才显示「待拆解」；done/failed/running 用 headline 或 stageLabel
    private var epicStageKey: String {
        FlowLayout.epicStageKey(epic: epic)
    }

    /// 整轨唯一标识：epic 切换 → 重新 stagger；同 epic 内 SSE 增量 → 不重启动画
    private var epicIdSignature: String {
        (epicId ?? epic?.id ?? "_") + "|" + (epic?.user_stage ?? epic?.split_status ?? "")
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 3) {
            if let text = headerText {
                Text(text)
                    .font(.system(size: 12.5, weight: .medium))
                    .foregroundStyle(headerUsesAccent ? CCCTheme.accent.opacity(0.9) : CCCTheme.muted)
                    .lineLimit(2)
            }
            if let goal = headerGoal, !goal.isEmpty {
                Text(goal)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
                    .lineLimit(1)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 4)
        .padding(.bottom, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var headerText: String? {
        // 阶段主文案（UX 表对齐）
        let stage = FlowLayout.epicHeadlineText(epic: epic, works: works, fallbackHeadline: headline)
        if stage.isEmpty { return nil }
        // 已 done 时强制空轨（除非外层条件）；空轨时主文案保持
        return stage
    }

    private var headerGoal: String? {
        guard let g = epic?.goal_summary?.trimmingCharacters(in: .whitespacesAndNewlines),
              !g.isEmpty else { return nil }
        return FlowLayout.truncate(g, max: 64)
    }

    private var headerUsesAccent: Bool {
        // pending/planned 且未到 works → 强调色（拆解中）
        if !works.isEmpty { return false }
        let k = epicStageKey
        return ["pending", "planned", ""].contains(k)
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
            Text("已完成任务在看板维护；右栏只跟当前未完成编排。")
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint.opacity(0.75))
            Spacer()
        }
        .padding(20)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("编排空闲。转任务后流程会出现在这里。")
    }

    private var timelineBody: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
                epicCard
                if !ordered.isEmpty {
                    railConnector(active: ordered.contains(where: \.isActive))
                    workSections
                }
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 16)
        }
        .onAppear {
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

    private var epicCard: some View {
        let node = FlowLayout.epicGraphNode(epic: epic, epicId: epicId)
        return Button {
            onSelectNode?(node.id)
        } label: {
            FlowNodeView(
                node: node,
                pulse: works.isEmpty && splittingPulse
            )
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity, minHeight: FlowLayout.epicHeight, alignment: .topLeading)
        .accessibilityLabel("大卡 \(node.title)，\(node.subtitle)")
    }

    private var workSections: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(ordered.enumerated()), id: \.element.id) { idx, work in
                let section = FlowLayout.stageSectionTitle(work.status)
                let showHeader = idx == 0
                    || FlowLayout.stageSectionTitle(ordered[idx - 1].status) != section
                if showHeader {
                    Text(section)
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(CCCTheme.faint)
                        .padding(.top, idx == 0 ? 4 : 10)
                        .padding(.bottom, 4)
                        .padding(.leading, 2)
                }
                workCard(work)
                if idx < ordered.count - 1 {
                    railConnector(active: work.isActive || ordered[idx + 1].isActive)
                }
            }
        }
    }

    private func workCard(_ work: FlowWork) -> some View {
        let visible = revealedWorkIds.contains(work.id)
        return Button {
            onSelectNode?(work.id)
        } label: {
            FlowNodeView(
                node: FlowLayout.graphNode(from: work),
                pulse: pulse && FlowLayout.statusColorKey(work.status) == "running"
            )
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity, minHeight: FlowLayout.nodeHeight, alignment: .topLeading)
        .opacity(visible ? 1 : 0)
        .offset(y: visible ? 0 : 8)
        .animation(.easeOut(duration: 0.32), value: revealedWorkIds)
        .accessibilityLabel("步骤 \(work.title)，\(work.displayStatus)")
    }

    private func railConnector(active: Bool) -> some View {
        HStack {
            Spacer(minLength: 0)
            RoundedRectangle(cornerRadius: 1, style: .continuous)
                .fill(active ? CCCTheme.nodeRunning.opacity(0.55) : CCCTheme.borderStrong)
                .frame(width: 2, height: 14)
            Spacer(minLength: 0)
        }
        .padding(.vertical, 2)
    }

    private func restartSplitAnimation() {
        animToken &+= 1
        let token = animToken
        // 仅在「真切换 epic」时清空 revealed（onChange of epicIdSignature 已做）
        // 同 epic 内的 reveal 由 runRevealSequence 增量追加
        // 仅待拆解阶段脉冲；done/failed 不闪「拆解中」
        if works.isEmpty, ["pending", "planned", ""].contains(epicStageKey) {
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                splittingPulse = true
            }
            return
        }
        splittingPulse = false
        guard !works.isEmpty else { return }
        // 首次 stagger：把所有当前 works 加入动画
        let all = works.map(\.id)
        runRevealSequence(newIds: all, token: token)
    }

    /// 增量 stagger：仅对新出现的 work id 做层序 reveal；同 epic 内纯状态更新不再触发
    private func runRevealSequence(newIds: [String], token: UInt64) {
        guard !newIds.isEmpty else { return }
        let byId = Dictionary(uniqueKeysWithValues: works.map { ($0.id, $0) })
        let deps = FlowLayout.layers(works: works)
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 160_000_000)
            guard token == animToken else { return }
            for layer in deps {
                let freshInLayer = layer.map(\.id).filter { newIds.contains($0) && byId[$0] != nil }
                guard !freshInLayer.isEmpty else { continue }
                guard token == animToken else { return }
                withAnimation(.easeOut(duration: 0.32)) {
                    for id in freshInLayer { revealedWorkIds.insert(id) }
                }
                try? await Task.sleep(nanoseconds: 200_000_000)
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

    private var executorIcon: String {
        let b = node.badge.lowercased()
        if b.contains("opencode") || b.contains("dev") || b.contains("写码") { return "terminal" }
        if b.contains("claude") || b.contains("loop-code") || b.contains("product") { return "cpu" }
        if b.contains("python") || b.contains("脚本") { return "curlybraces" }
        if b.contains("review") || b.contains("tester") || b.contains("验收") { return "checkmark.shield" }
        if b.contains("kb") { return "books.vertical" }
        if b.contains("ops") { return "stethoscope" }
        if b.contains("任务") { return "flag.fill" }
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
                .font(.system(size: 12, weight: node.kind == .epic ? .semibold : .medium))
                .foregroundStyle(CCCTheme.ink)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
            Text(node.subtitle)
                .font(.system(size: 11))
                .foregroundStyle(isFail ? CCCTheme.nodeFail : CCCTheme.faint)
                .lineLimit(1)
            if let detail = node.detail, !detail.isEmpty {
                Text(detail)
                    .font(.system(size: 10))
                    .foregroundStyle(isFail ? CCCTheme.nodeFail.opacity(0.95) : CCCTheme.faint.opacity(0.9))
                    .lineLimit(isFail ? 3 : 1)
            }
        }
        .padding(11)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(CCCTheme.surface)
                // 左侧强调条（running/failed）；done 不画；pending 仅淡边
                if isFail {
                    HStack {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(CCCTheme.nodeFail.opacity(0.85))
                            .frame(width: 3)
                        Spacer(minLength: 0)
                    }
                    .padding(.vertical, 6)
                    .padding(.leading, 5)
                } else if isRunning {
                    HStack {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(CCCTheme.nodeRunning.opacity(0.75))
                            .frame(width: 3)
                        Spacer(minLength: 0)
                    }
                    .padding(.vertical, 6)
                    .padding(.leading, 5)
                }
            }
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(
                    isFail ? CCCTheme.nodeFail.opacity(0.85)
                        : (isRunning ? CCCTheme.nodeRunning.opacity(0.45) : CCCTheme.border),
                    lineWidth: isFail ? 1.8 : 1
                )
        )
        .shadow(
            color: isFail ? CCCTheme.nodeFail.opacity(0.35)
                : (isRunning ? tint.opacity(0.18) : .clear),
            radius: isFail ? 6 : (isRunning ? 3 : 0),
            x: 0, y: 0
        )
        // done 节点弱化（不抢 running/failed 视线）
        .opacity(colorKey == "done" && node.kind != .epic ? 0.68 : 1)
        .contentShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .animation(.easeInOut(duration: 0.28), value: node.statusKey)
    }
}
