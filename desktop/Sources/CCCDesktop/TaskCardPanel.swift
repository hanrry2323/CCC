import SwiftUI

/// T40 三栏右栏：任务卡流（与 HTTP 端视觉一致 · Linear 风格卡片）。
///
/// 数据走 AppModel.boardColumns（/board/snapshot 缓存）；
/// 卡片：ID + 标题 + 状态徽章 + 执行体 + 打回次数 + 更新时间，点击展开详情。
struct TaskCardPanel: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    @State private var expandedId: String?
    @State private var detail: BoardTaskDetail?
    @State private var detailBusy = false
    @State private var detailError: String?
    @State private var pollTimer: Timer?
    @State private var isLinkedMode = true

    // 契约 §2 五态（与新栈 models.STATES 对齐）
    private let states = ["待分派", "执行中", "已回写", "已关闭", "打回"]
    private let stateOrder: [String: Int] = [
        "打回": 0, "执行中": 1, "待分派": 2, "已回写": 3, "已关闭": 4,
    ]

    var body: some View {
        VStack(spacing: 0) {
            header
            statRow
            Divider()
            cardList
        }
        .frame(width: 300)
        .glassEffect()
        .onAppear { startPolling() }
        .onDisappear { stopPolling() }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 6) {
            Image(systemName: "square.stack.3d.up.fill")
                .font(.system(size: 12))
                .foregroundStyle(CCCTheme.accent)
            Text("任务卡流")
                .font(.system(size: 13, weight: .semibold))
            if model.boardBusy {
                ProgressView().controlSize(.mini)
            }
            Spacer()
            HStack(spacing: 0) {
                Button("关联") {
                    isLinkedMode = true
                }
                .buttonStyle(.plain)
                .font(.system(size: 10, weight: isLinkedMode ? .bold : .regular))
                .foregroundStyle(isLinkedMode ? CCCTheme.accent : CCCTheme.faint)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(isLinkedMode ? CCCTheme.hover : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 4))

                Button("全部") {
                    isLinkedMode = false
                }
                .buttonStyle(.plain)
                .font(.system(size: 10, weight: !isLinkedMode ? .bold : .regular))
                .foregroundStyle(!isLinkedMode ? CCCTheme.accent : CCCTheme.faint)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(!isLinkedMode ? CCCTheme.hover : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 4))
            }
            .background(RoundedRectangle(cornerRadius: 6).stroke(CCCTheme.border, lineWidth: 0.5))
            .padding(.trailing, 4)

            Button {
                Task { await model.refreshBoard() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
            }
            .buttonStyle(.plain)
            .help("刷新")
            .accessibilityLabel("刷新任务卡流")
        }
        .padding(.horizontal, 12)
        .padding(.top, 12)
        .padding(.bottom, 8)
    }

    // MARK: - Stat row (5 chips)

    private var statRow: some View {
        HStack(spacing: 4) {
            ForEach(states, id: \.self) { st in
                statChip(st)
            }
        }
        .padding(.horizontal, 12)
        .padding(.bottom, 8)
    }

    private func statChip(_ state: String) -> some View {
        let n = model.boardColumns[state]?.count ?? 0
        let tone = StateTone.of(state)
        return VStack(spacing: 1) {
            Text("\(n)")
                .font(.system(size: 12, weight: .bold, design: .rounded))
                .foregroundStyle(tone.fg)
            Text(state.prefix(2))
                .font(.system(size: 9))
                .foregroundStyle(CCCTheme.faint)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 4)
        .background(
            RoundedRectangle(cornerRadius: 6, style: .continuous)
                .fill(tone.bg)
        )
        .accessibilityLabel("\(state) \(n) 个")
    }

    // MARK: - Card list

    private var cardList: some View {
        let cards = sortedCards()
        return ScrollView(showsIndicators: false) {
            LazyVStack(spacing: 6) {
                if cards.isEmpty {
                    if model.boardBusy {
                        VStack(spacing: 8) {
                            ForEach(0..<4, id: \.self) { _ in
                                VStack(alignment: .leading, spacing: 6) {
                                    HStack {
                                        SkeletonView(width: 60, height: 12)
                                        Spacer()
                                        SkeletonView(width: 40, height: 12)
                                    }
                                    SkeletonView(width: 200, height: 14)
                                    HStack {
                                        SkeletonView(width: 80, height: 10)
                                        Spacer()
                                        SkeletonView(width: 50, height: 10)
                                    }
                                }
                                .padding(10)
                                .background(RoundedRectangle(cornerRadius: 8).fill(CCCTheme.surface))
                            }
                        }
                    } else {
                        Text("暂无任务")
                            .font(.system(size: 11))
                            .foregroundStyle(CCCTheme.faint)
                            .frame(maxWidth: .infinity)
                            .padding(.top, 24)
                    }
                } else {
                    ForEach(cards, id: \.id) { task in
                        TaskCard(
                            task: task,
                            isExpanded: expandedId == task.id,
                            detail: expandedId == task.id ? detail : nil,
                            detailBusy: expandedId == task.id && detailBusy,
                            detailError: expandedId == task.id ? detailError : nil,
                            onToggle: { toggle(task) },
                            onCopyId: { copyId(task.id) }
                        )
                    }
                }
            }
            .padding(.horizontal, 10)
            .padding(.top, 8)
            .padding(.bottom, 20)
        }
    }

    private func sortedCards() -> [BoardTask] {
        // 列名 → 状态映射（task.status 可能为 nil，按列回退）
        var stateMap: [String: String] = [:]
        var all: [BoardTask] = []
        for st in states {
            if let arr = model.boardColumns[st] {
                for t in arr {
                    if stateMap[t.id] == nil { stateMap[t.id] = st }
                }
                all.append(contentsOf: arr)
            }
        }
        // dedupe by id
        var seen = Set<String>()
        all = all.filter { seen.insert($0.id).inserted }

        if isLinkedMode {
            let currentThread = model.selectedThreadId ?? ""
            all = all.filter { task in
                let status = task.status ?? stateMap[task.id] ?? ""
                let isNotClosed = (status != "已关闭" && status != "released" && status != "closed")
                let isAssociatedWithCurrentThread = !currentThread.isEmpty && currentThread.contains(task.id)
                return isNotClosed || isAssociatedWithCurrentThread
            }
        }

        all.sort { (a, b) in
            let sa = a.status ?? stateMap[a.id] ?? ""
            let sb = b.status ?? stateMap[b.id] ?? ""
            let oa = stateOrder[sa] ?? 9
            let ob = stateOrder[sb] ?? 9
            if oa != ob { return oa < ob }
            return a.id > b.id
        }
        return all
    }

    // MARK: - Toggle / detail

    private func toggle(_ task: BoardTask) {
        if expandedId == task.id {
            expandedId = nil
            detail = nil
            detailError = nil
            return
        }
        expandedId = task.id
        detail = nil
        detailBusy = true
        detailError = nil
        Task {
            do {
                let d = try await model.fetchTaskDetail(task)
                await MainActor.run {
                    if expandedId == task.id {
                        detail = d
                        detailBusy = false
                    }
                }
            } catch {
                await MainActor.run {
                    if expandedId == task.id {
                        detailError = error.localizedDescription
                        detailBusy = false
                    }
                }
            }
        }
    }

    private func copyId(_ id: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(id, forType: .string)
        model.showToast("已复制任务 ID: \(id)")
    }

    // MARK: - Polling

    private func startPolling() {
        stopPolling()
        // 首次进入：触发一次拉取（若 boardColumns 为空）
        if model.boardColumns.isEmpty {
            Task { await model.refreshBoard() }
        }
        pollTimer = Timer.scheduledTimer(withTimeInterval: 12, repeats: true) { _ in
            Task { await model.refreshBoard() }
        }
    }

    private func stopPolling() {
        pollTimer?.invalidate()
        pollTimer = nil
    }
}

// MARK: - Single card

struct TaskCard: View {
    let task: BoardTask
    let isExpanded: Bool
    let detail: BoardTaskDetail?
    let detailBusy: Bool
    let detailError: String?
    let onToggle: () -> Void
    let onCopyId: () -> Void

    var body: some View {
        let tone = StateTone.of(task.status ?? "")
        return VStack(alignment: .leading, spacing: 0) {
            // 卡片主体
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(task.id)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(CCCTheme.faint)
                    Spacer()
                    Text(task.status ?? "—")
                        .font(.system(size: 10, weight: .semibold))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 1)
                        .background(Capsule().fill(tone.bg))
                        .foregroundStyle(tone.fg)
                }
                Text(task.displayTitle)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(CCCTheme.ink)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                HStack(spacing: 6) {
                    if let exec = task.executor, !exec.isEmpty, exec != "未知" {
                        Text("@\(exec)")
                            .font(.system(size: 10))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 1)
                            .background(Capsule().fill(CCCTheme.hover))
                            .foregroundStyle(CCCTheme.secondary)
                    }
                    if let rc = task.split_status, !rc.isEmpty, rc != "0" {
                        Text("↩ \(rc)")
                            .font(.system(size: 10, weight: .medium))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 1)
                            .background(Capsule().fill(StateTone.returned.bg.opacity(0.5)))
                            .foregroundStyle(StateTone.returned.fg)
                    }
                    Spacer()
                    Button(action: onCopyId) {
                        Image(systemName: "doc.on.doc")
                            .font(.system(size: 10))
                            .foregroundStyle(CCCTheme.faint)
                    }
                    .buttonStyle(.plain)
                    .help("复制 ID")
                    .accessibilityLabel("复制任务 ID")
                }
            }
            .padding(10)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(CCCTheme.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(CCCTheme.border, lineWidth: 0.5)
                    )
            )
            .overlay(alignment: .leading) {
                // 状态色条（左 3px）
                RoundedRectangle(cornerRadius: 1.5, style: .continuous)
                    .fill(tone.bar)
                    .frame(width: 3)
                    .padding(.vertical, 4)
            }
            .contentShape(Rectangle())
            .powHoverSpring()
            .powSpringClick()
            .onTapGesture { onToggle() }

            // 展开详情
            if isExpanded {
                detailView
                    .padding(.top, 6)
                    .padding(.leading, 6)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.bottom, 4)
    }

    @ViewBuilder
    private var detailView: some View {
        if detailBusy {
            VStack(alignment: .leading, spacing: 6) {
                SkeletonView(width: 240, height: 12)
                SkeletonView(width: 160, height: 10)
                SkeletonView(width: 200, height: 10)
            }
            .padding(8)
        } else if let err = detailError {
            Text("详情不可用: \(err)")
                .font(.system(size: 10))
                .foregroundStyle(StateTone.returned.fg)
                .padding(8)
        } else if let d = detail {
            VStack(alignment: .leading, spacing: 6) {
                if let note = d.note, !note.isEmpty {
                    Text(note)
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.secondary)
                }
                if let acc = d.acceptance, !acc.isEmpty {
                    Text("验收")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(CCCTheme.faint)
                    Text(acc)
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.ink)
                }
                if let phases = d.phases, !phases.isEmpty {
                    Text("阶段")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(CCCTheme.faint)
                    ForEach(phases) { ph in
                        HStack(spacing: 6) {
                            Text(ph.name)
                                .font(.system(size: 11))
                                .foregroundStyle(CCCTheme.ink)
                            Spacer()
                            Text(ph.status ?? "—")
                                .font(.system(size: 9))
                                .padding(.horizontal, 5)
                                .padding(.vertical, 1)
                                .background(Capsule().fill(CCCTheme.hover))
                                .foregroundStyle(CCCTheme.secondary)
                            if let c = ph.commit, !c.isEmpty {
                                Text(c.prefix(7))
                                    .font(.system(size: 9, design: .monospaced))
                                    .foregroundStyle(CCCTheme.faint)
                            }
                        }
                    }
                }
                if let evs = d.events, !evs.isEmpty {
                    Text("时间线")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(CCCTheme.faint)
                    ForEach(evs.prefix(8)) { ev in
                        HStack(alignment: .top, spacing: 6) {
                            Text(ev.ts ?? "")
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                                .frame(width: 48, alignment: .leading)
                            Text("@" + (ev.role ?? "system"))
                                .font(.system(size: 9))
                                .foregroundStyle(CCCTheme.secondary)
                                .frame(width: 50, alignment: .leading)
                            Text(ev.message ?? "")
                                .font(.system(size: 10))
                                .foregroundStyle(CCCTheme.secondary)
                                .lineLimit(2)
                        }
                    }
                }
            }
            .padding(8)
            .background(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .fill(CCCTheme.hover.opacity(0.5))
            )
        }
    }
}

// MARK: - State tone (与 HTTP 端 .state-* 色板对齐)

enum StateTone {
    struct Palette {
        let fg: Color
        let bg: Color
        let bar: Color
    }

    static let pending = Palette(
        fg: CCCTheme.tonePendingFG,
        bg: CCCTheme.tonePendingBG,
        bar: CCCTheme.tonePendingBar
    )
    static let running = Palette(
        fg: CCCTheme.toneRunningFG,
        bg: CCCTheme.toneRunningBG,
        bar: CCCTheme.toneRunningBar
    )
    static let written = Palette(
        fg: CCCTheme.toneWrittenFG,
        bg: CCCTheme.toneWrittenBG,
        bar: CCCTheme.toneWrittenBar
    )
    static let closed = Palette(
        fg: CCCTheme.toneClosedFG,
        bg: CCCTheme.toneClosedBG,
        bar: CCCTheme.toneClosedBar
    )
    static let returned = Palette(
        fg: CCCTheme.toneReturnedFG,
        bg: CCCTheme.toneReturnedBG,
        bar: CCCTheme.toneReturnedBar
    )
    static let unknown = Palette(
        fg: CCCTheme.secondary,
        bg: CCCTheme.hover,
        bar: CCCTheme.border
    )

    static func of(_ state: String?) -> Palette {
        switch state ?? "" {
        case "待分派": return pending
        case "执行中": return running
        case "已回写": return written
        case "已关闭": return closed
        case "打回": return returned
        default: return unknown
        }
    }
}
