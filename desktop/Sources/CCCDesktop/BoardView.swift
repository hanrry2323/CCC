import SwiftUI
import UniformTypeIdentifiers

/// 原生看板：多 workspace + 拖拽移动 + 任务详情 + 隐藏/重开
struct BoardView: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    @State private var selectedTask: BoardTask?
    @State private var detail: BoardTaskDetail?
    @State private var detailBusy = false
    @State private var detailError: String?
    @State private var dragTask: BoardTask?
    @State private var pollTimer: Timer?
    @State private var autoRefresh = true

    private let columnOrder = [
        "backlog", "planned", "in_progress", "testing", "verified", "released", "abnormal",
    ]

    private let columnTitles: [String: String] = [
        "backlog": "待办",
        "planned": "已规划",
        "in_progress": "进行中",
        "testing": "验收中",
        "verified": "已验证",
        "released": "已发布",
        "abnormal": "异常",
    ]

    var body: some View {
        VStack(spacing: 0) {
            header
            if let err = model.boardError {
                Text(err)
                    .font(CCCTheme.callout)
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 8)
            }
            GeometryReader { geo in
                let cols = visibleColumns
                let gap: CGFloat = 12
                let hPad: CGFloat = 16
                let n = max(cols.count, 1)
                let colW = max(200, (geo.size.width - hPad * 2 - gap * CGFloat(n - 1)) / CGFloat(n))
                ScrollView(.horizontal, showsIndicators: true) {
                    HStack(alignment: .top, spacing: gap) {
                        ForEach(cols, id: \.self) { col in
                            columnPane(col, width: colW, height: geo.size.height - 8)
                        }
                    }
                    .padding(.horizontal, hPad)
                    .padding(.bottom, 12)
                    .frame(minWidth: geo.size.width, minHeight: geo.size.height, alignment: .topLeading)
                }
            }
        }
        .background(CCCTheme.chatBg)
        .task { await model.refreshBoard() }
        .onAppear { startPolling() }
        .onDisappear { stopPolling() }
        .sheet(item: $selectedTask) { task in
            taskDetailSheet(task)
        }
    }

    private var header: some View {
        HStack(spacing: 10) {
            Text("看板")
                .font(.system(size: 16, weight: .semibold))
            workspacePicker
                .font(.system(size: 12))
                .foregroundStyle(CCCTheme.faint)
            Spacer()
            Toggle(isOn: Binding(
                get: { model.boardShowHidden },
                set: { newValue in Task { await model.setBoardShowHidden(newValue) } }
            )) {
                Text("显示已隐藏")
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
            }
            .toggleStyle(.switch)
            .controlSize(.mini)
            Toggle(isOn: $autoRefresh) {
                Text("自动")
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
            }
            .toggleStyle(.switch)
            .controlSize(.mini)
            if model.boardBusy {
                ProgressView().controlSize(.mini)
            }
            Menu {
                Button("隐藏已完成大卡") { Task { await model.hideCompletedEpics() } }
                Button("刷新") { Task { await model.refreshBoard() } }
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(.system(size: 14))
                    .foregroundStyle(CCCTheme.secondary)
            }
            .menuStyle(.borderlessButton)
            Button("回对话") {
                window.destination = .chat
                model.selectDestination(.chat, projectId: window.projectId)
            }
            .buttonStyle(.plain)
            .foregroundStyle(CCCTheme.secondary)
            .font(.system(size: 12))
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
        .padding(.bottom, 10)
    }

    private var workspacePicker: some View {
        let workspaces = model.projects
            .map { $0.workspace ?? $0.id }
            .filter { !$0.isEmpty }
        // 保序去重，避免 NSOrderedSet 桥接 as? [String] 失败回退含重复
        var seen = Set<String>()
        let unique = workspaces.filter { seen.insert($0).inserted }
        let current = model.boardWorkspaceLabel ?? "CCC"
        return Picker("", selection: Binding(
            get: { current },
            set: { newValue in
                model.boardWorkspaceLabel = newValue
                Task { await model.refreshBoard() }
            }
        )) {
            ForEach(unique, id: \.self) { Text($0).tag($0) }
            if !unique.contains(current) {
                Text(current).tag(current)
            }
        }
        .pickerStyle(.menu)
        .controlSize(.small)
    }

    private var visibleColumns: [String] {
        let keys = Set(model.boardColumns.keys)
        let ordered = columnOrder.filter { keys.contains($0) }
        let extra = keys.subtracting(columnOrder).sorted()
        return ordered + extra
    }

    private func columnPane(_ col: String, width: CGFloat, height: CGFloat) -> some View {
        let tasks = model.boardColumns[col] ?? []
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(columnTitles[col] ?? col)
                    .font(.system(size: 13, weight: .semibold))
                Spacer()
                Text("\(tasks.count)")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(CCCTheme.faint)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("\(columnTitles[col] ?? col)列，\(tasks.count) 项")
            .padding(.horizontal, 4)
            ScrollView(showsIndicators: false) {
                LazyVStack(spacing: 6) {
                    if tasks.isEmpty {
                        Text("空")
                            .font(CCCTheme.caption)
                            .foregroundStyle(CCCTheme.faint)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(8)
                    }
                    ForEach(tasks) { task in
                        boardCard(task, col: col)
                            .onDrag {
                                dragTask = task
                                return NSItemProvider(object: NSString(string: task.id))
                            }
                            .onTapGesture { openDetail(task) }
                    }
                }
            }
            .frame(width: width, height: max(height - 36, 120))
            .padding(8)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(CCCTheme.surface)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(CCCTheme.border, lineWidth: 1)
            )
            .onDrop(of: [.text], delegate: BoardDropDelegate(col: col, model: model, dragTask: $dragTask))
        }
    }

    private func boardCard(_ task: BoardTask, col: String) -> some View {
        let highlight = model.currentEpicId == task.id
            || (model.flowEpic?.id == task.id)
        let isAbnormal = (task.status == "abnormal") || (task.split_status == "failed")
        return VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                if task.isEpic {
                    Text("EPIC")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(CCCTheme.accent)
                }
                Spacer(minLength: 0)
                if isAbnormal {
                    Circle().fill(CCCTheme.nodeFail).frame(width: 6, height: 6)
                }
            }
            Text(task.displayTitle)
                .font(.system(size: 13.5, weight: .medium))
                .foregroundStyle(CCCTheme.ink)
                .lineLimit(3)
            if let note = task.note, !note.isEmpty {
                Text(note)
                    .font(.system(size: 11.5))
                    .foregroundStyle(CCCTheme.faint)
                    .lineLimit(2)
            }
            HStack(spacing: 6) {
                if let split = task.split_status, !split.isEmpty {
                    Text(split)
                        .font(.system(size: 10))
                        .foregroundStyle(CCCTheme.secondary)
                }
                if let ex = task.executor, !ex.isEmpty {
                    Text(ex)
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(CCCTheme.faint)
                        .padding(.horizontal, 4)
                        .background(CCCTheme.chatBg)
                        .clipShape(RoundedRectangle(cornerRadius: 3))
                }
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(highlight ? CCCTheme.accent.opacity(0.12) : CCCTheme.chatBg)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(highlight ? CCCTheme.accent.opacity(0.55) : Color.clear, lineWidth: 1.5)
        )
    }

    private func openDetail(_ task: BoardTask) {
        selectedTask = task
        detail = nil
        detailError = nil
        detailBusy = true
        Task {
            defer { detailBusy = false }
            do {
                detail = try await model.fetchTaskDetail(task)
            } catch {
                detailError = error.localizedDescription
            }
        }
    }

    private func taskDetailSheet(_ task: BoardTask) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                if task.isEpic {
                    Text("EPIC").font(.system(size: 10, weight: .bold)).foregroundStyle(CCCTheme.accent)
                }
                Text(task.displayTitle)
                    .font(.system(size: 14, weight: .semibold))
                    .lineLimit(2)
                Spacer()
                Button("关闭") { selectedTask = nil }
                    .buttonStyle(.plain)
                    .foregroundStyle(CCCTheme.secondary)
            }
            HStack(spacing: 12) {
                Label(task.status ?? "—", systemImage: "circle.grid.2x2")
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
                if let split = task.split_status, !split.isEmpty {
                    Label(split, systemImage: "arrow.triangle.branch")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.secondary)
                }
                if let ex = task.executor, !ex.isEmpty {
                    Label(ex, systemImage: "cpu")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            if detailBusy {
                ProgressView().controlSize(.small)
            }
            if let err = detailError {
                Text(err).font(.system(size: 11)).foregroundStyle(CCCTheme.nodeFail)
            }
            if let note = task.note, !note.isEmpty {
                Text("备注").font(.system(size: 11, weight: .semibold)).foregroundStyle(CCCTheme.faint)
                Text(note).font(.system(size: 12))
            }
            if let d = detail {
                if let acc = d.acceptance, !acc.isEmpty {
                    Text("验收").font(.system(size: 11, weight: .semibold)).foregroundStyle(CCCTheme.faint)
                    Text(acc).font(.system(size: 12))
                }
                if let phases = d.phases, !phases.isEmpty {
                    Text("阶段").font(.system(size: 11, weight: .semibold)).foregroundStyle(CCCTheme.faint)
                    ForEach(phases) { phase in
                        HStack {
                            Text(phase.name).font(.system(size: 11, design: .monospaced))
                            Spacer()
                            Text(phase.status ?? "—")
                                .font(.system(size: 10))
                                .foregroundStyle(CCCTheme.secondary)
                        }
                        .padding(.vertical, 2)
                    }
                }
                if let events = d.events, !events.isEmpty {
                    Text("事件").font(.system(size: 11, weight: .semibold)).foregroundStyle(CCCTheme.faint)
                    ForEach(events.prefix(20)) { ev in
                        VStack(alignment: .leading, spacing: 2) {
                            if let ts = ev.ts {
                                Text(ts).font(.system(size: 9, design: .monospaced)).foregroundStyle(CCCTheme.faint)
                            }
                            if let m = ev.message { Text(m).font(.system(size: 11)) }
                        }
                        .padding(.vertical, 2)
                    }
                }
            }
            Spacer()
            HStack {
                if task.status == "abnormal" || task.split_status == "failed" {
                    Button("重开 → planned") {
                        Task { await model.reopenBoardTask(task, to: "planned"); selectedTask = nil }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                }
                Spacer()
            }
        }
        .padding(20)
        .frame(width: 480, height: 560, alignment: .topLeading)
        .background(CCCTheme.chatBg)
    }

    private func startPolling() {
        stopPolling()
        guard autoRefresh else { return }
        pollTimer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { _ in
            guard autoRefresh else { return }
            Task { @MainActor in await model.refreshBoard() }
        }
    }

    private func stopPolling() {
        pollTimer?.invalidate()
        pollTimer = nil
    }
}

/// 拖拽落点：把拖动的任务移到目标列
struct BoardDropDelegate: DropDelegate {
    let col: String
    let model: AppModel
    @Binding var dragTask: BoardTask?

    func performDrop(info: DropInfo) -> Bool {
        guard let task = dragTask else { return false }
        if task.status == col {
            dragTask = nil
            return false
        }
        Task { await model.moveBoardTask(task, to: col) }
        dragTask = nil
        return true
    }
}
