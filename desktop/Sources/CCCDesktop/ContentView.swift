import SwiftUI

struct ContentView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider().overlay(CCCTheme.border)
            HStack(spacing: 0) {
                ActivityRail()
                    .frame(width: 56)
                Divider().overlay(CCCTheme.border)
                ProjectTreeSidebar()
                    .frame(width: 268)
                Divider().overlay(CCCTheme.border)
                ChatPane()
                    .frame(minWidth: 400)
                Divider().overlay(CCCTheme.border)
                FlowRail()
                    .frame(minWidth: 300, idealWidth: 340, maxWidth: 400)
            }
            Divider().overlay(CCCTheme.border)
            statusBar
        }
        .background(CCCTheme.bg)
        .foregroundStyle(CCCTheme.ink)
        .task { await model.bootstrap() }
        .sheet(isPresented: $model.showTransferSheet) {
            TransferSheet()
                .environmentObject(model)
        }
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 12) {
            Text("CCC")
                .font(CCCTheme.brandFont)
            if let p = model.selectedProject {
                Text(p.name)
                    .font(.system(size: 13, weight: .medium, design: .serif))
                    .foregroundStyle(CCCTheme.muted)
            }
            Spacer()
            Button("转任务") {
                model.openTransferSheet()
            }
            .buttonStyle(.borderedProminent)
            .tint(CCCTheme.accent)
            .disabled(model.selectedProject?.isDispatchable != true)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            LinearGradient(
                colors: [
                    Color(red: 0.99, green: 0.97, blue: 0.94),
                    Color(red: 0.95, green: 0.90, blue: 0.84),
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
    }

    private var statusBar: some View {
        HStack(spacing: 10) {
            Text(model.statusText)
                .font(CCCTheme.mono)
                .foregroundStyle(CCCTheme.muted)
            Spacer()
            if let err = model.lastError {
                Text(err)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.nodeFail)
                    .lineLimit(1)
                    .help(err)
            }
            if model.busy {
                ProgressView().controlSize(.small)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
        .background(CCCTheme.panel)
    }
}

// MARK: - Cursor-like activity rail (Hub / Ops = Automations / Customize)

struct ActivityRail: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 6) {
            Text("CCC")
                .font(.system(size: 10, weight: .bold, design: .serif))
                .foregroundStyle(CCCTheme.muted)
                .padding(.top, 12)
                .padding(.bottom, 4)

            railButton(.chat, tip: "对话（主工作区）")
            railButton(.hub, tip: "Hub 看板（浏览器运维）")
            railButton(.ops, tip: "运维控制台（浏览器）")

            Spacer()
        }
        .frame(maxWidth: .infinity)
        .background(CCCTheme.rail)
    }

    private func railButton(_ dest: SidebarDestination, tip: String) -> some View {
        let selected = model.destination == dest && dest == .chat
        return Button {
            model.selectDestination(dest)
        } label: {
            VStack(spacing: 3) {
                Image(systemName: dest.systemImage)
                    .font(.system(size: 16, weight: .semibold))
                Text(dest.title)
                    .font(.system(size: 9, weight: .medium))
            }
            .foregroundStyle(selected ? CCCTheme.accent : CCCTheme.muted)
            .frame(width: 48, height: 48)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(selected ? CCCTheme.accent.opacity(0.12) : Color.clear)
            )
        }
        .buttonStyle(.plain)
        .help(tip)
    }
}

// MARK: - Project → threads (Cursor agent/chat tree)

struct ProjectTreeSidebar: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("工作区")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(CCCTheme.muted)
                Spacer()
                Button {
                    Task { await model.newThread() }
                } label: {
                    Image(systemName: "square.and.pencil")
                }
                .buttonStyle(.plain)
                .help("新对话")
                .disabled(model.selectedProjectId == nil)

                Button {
                    Task { await model.refreshProjects() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.plain)
                .help("刷新")
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 2) {
                    ForEach(model.projects) { project in
                        ProjectSection(project: project)
                    }
                }
                .padding(.horizontal, 8)
                .padding(.bottom, 12)
            }
        }
        .background(CCCTheme.panel)
    }
}

struct ProjectSection: View {
    @EnvironmentObject var model: AppModel
    let project: DesktopProject

    private var expanded: Bool {
        model.expandedProjectIds.contains(project.id)
    }

    private var selected: Bool {
        model.selectedProjectId == project.id
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Button {
                Task {
                    if selected {
                        model.toggleProjectExpanded(project.id)
                    } else {
                        await model.selectProject(project.id)
                    }
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: expanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(CCCTheme.muted)
                        .frame(width: 10)
                    Image(systemName: project.isOrch ? "gearshape.2" : "folder.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(project.isDispatchable ? CCCTheme.accent : CCCTheme.muted)
                    Text(project.name)
                        .font(.system(size: 13, weight: selected ? .semibold : .medium))
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    if project.isOrch {
                        Text("orch")
                            .font(CCCTheme.mono)
                            .foregroundStyle(CCCTheme.muted)
                    }
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 7)
                .background(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(selected ? CCCTheme.accent.opacity(0.10) : Color.clear)
                )
            }
            .buttonStyle(.plain)

            if expanded && selected {
                let list = model.threads
                if list.isEmpty {
                    Text("暂无对话")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.muted)
                        .padding(.leading, 28)
                        .padding(.vertical, 4)
                } else {
                    ForEach(list) { thread in
                        Button {
                            Task { await model.openThread(thread.thread_id) }
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "bubble.left")
                                    .font(.system(size: 10))
                                    .foregroundStyle(CCCTheme.muted)
                                Text(thread.title ?? thread.thread_id)
                                    .font(.system(size: 12))
                                    .lineLimit(1)
                                Spacer(minLength: 0)
                            }
                            .padding(.leading, 28)
                            .padding(.trailing, 8)
                            .padding(.vertical, 5)
                            .background(
                                RoundedRectangle(cornerRadius: 6, style: .continuous)
                                    .fill(
                                        model.selectedThreadId == thread.thread_id
                                            ? Color.white.opacity(0.55)
                                            : Color.clear
                                    )
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }
}

// MARK: - Chat

struct ChatPane: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                        if model.messages.isEmpty {
                            emptyState
                        }
                        ForEach(model.messages) { msg in
                            MessageBubble(message: msg)
                                .id(msg.id)
                        }
                    }
                    .padding(20)
                }
                .onChange(of: model.messages.count) { _ in
                    if let last = model.messages.last {
                        withAnimation(.easeOut(duration: 0.25)) {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }

            HStack(alignment: .bottom, spacing: 10) {
                TextEditor(text: $model.draft)
                    .font(CCCTheme.bodyFont)
                    .frame(minHeight: 52, maxHeight: 120)
                    .padding(8)
                    .background(Color.white.opacity(0.7))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .stroke(CCCTheme.border, lineWidth: 1)
                    )
                Button("发送") {
                    Task { await model.sendMessage() }
                }
                .keyboardShortcut(.return, modifiers: .command)
                .buttonStyle(.borderedProminent)
                .tint(CCCTheme.ink)
                .disabled(
                    model.busy
                        || model.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                )
            }
            .padding(16)
            .background(CCCTheme.panel.opacity(0.85))
        }
        .background(CCCTheme.bg)
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("方案 Agent")
                .font(.system(size: 18, weight: .semibold, design: .serif))
            Text("在左侧选项目与对话。聊透后「转任务」写入 epic；右侧显示活动编排图。\n左侧图标栏的 Hub / 运维 打开网页控制面（类似 Cursor 的 Automations / Customize）。")
                .font(CCCTheme.bodyFont)
                .foregroundStyle(CCCTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(8)
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        let isUser = message.role == "user"
        HStack {
            if isUser { Spacer(minLength: 48) }
            Text(message.content)
                .font(CCCTheme.bodyFont)
                .textSelection(.enabled)
                .padding(12)
                .background(isUser ? CCCTheme.accent.opacity(0.15) : CCCTheme.card)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(CCCTheme.border.opacity(0.6), lineWidth: 1)
                )
            if !isUser { Spacer(minLength: 48) }
        }
    }
}

// MARK: - Flow rail (active cards)

struct FlowRail: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("编排流程")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(CCCTheme.muted)
                Spacer()
                if !model.flowWorks.isEmpty {
                    Text("\(model.flowWorks.count) works")
                        .font(CCCTheme.mono)
                        .foregroundStyle(CCCTheme.muted)
                }
            }
            .padding(12)

            if model.flowWorks.isEmpty && model.flowEpic == nil {
                emptyState
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        if let epic = model.flowEpic ?? model.currentEpicId.map({
                            FlowEpic(id: $0, title: $0, split_status: nil, column: nil)
                        }) {
                            EpicCard(epic: epic)
                                .padding(.bottom, 8)
                            FlowConnector(active: model.flowWorks.contains(where: \.isActive))
                        }
                        ForEach(Array(model.flowWorks.enumerated()), id: \.element.id) { idx, work in
                            WorkCard(work: work)
                            if idx < model.flowWorks.count - 1 {
                                FlowConnector(active: work.isActive || model.flowWorks[idx + 1].isActive)
                            }
                        }
                        FlowLegend()
                            .padding(.top, 16)
                    }
                    .padding(.horizontal, 12)
                    .padding(.bottom, 16)
                }
            }
        }
        .background(
            LinearGradient(
                colors: [CCCTheme.panel, CCCTheme.bg],
                startPoint: .top,
                endPoint: .bottom
            )
        )
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(CCCTheme.border, style: StrokeStyle(lineWidth: 1, dash: [5, 4]))
                    .frame(height: 120)
                VStack(spacing: 8) {
                    Image(systemName: "point.3.connected.trianglepath.dotted")
                        .font(.system(size: 26))
                        .foregroundStyle(CCCTheme.muted.opacity(0.75))
                    Text(model.flowEmptyMessage)
                        .font(.system(size: 12))
                        .foregroundStyle(CCCTheme.muted)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 12)
                }
            }
            Spacer()
        }
        .padding(12)
    }
}

struct EpicCard: View {
    let epic: FlowEpic

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("EPIC")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(CCCTheme.accent)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(CCCTheme.accent.opacity(0.12))
                    .clipShape(Capsule())
                Spacer()
                if let ss = epic.split_status {
                    Text(ss)
                        .font(CCCTheme.mono)
                        .foregroundStyle(CCCTheme.muted)
                }
            }
            Text(epic.title ?? epic.id ?? "—")
                .font(.system(size: 13, weight: .semibold))
                .lineLimit(2)
            if let id = epic.id {
                Text(id)
                    .font(CCCTheme.mono)
                    .foregroundStyle(CCCTheme.muted)
                    .lineLimit(1)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(CCCTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(CCCTheme.accent.opacity(0.35), lineWidth: 1)
        )
        .shadow(color: Color.black.opacity(0.04), radius: 4, y: 2)
    }
}

struct WorkCard: View {
    let work: FlowWork
    @State private var pulse = false

    private var statusColor: Color {
        if work.isFailed { return CCCTheme.nodeFail }
        if work.isTerminalDone { return CCCTheme.nodeDone }
        if work.status == "in_progress" || work.status == "testing" {
            return CCCTheme.nodeRunning
        }
        return CCCTheme.nodePending
    }

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            RoundedRectangle(cornerRadius: 2)
                .fill(statusColor)
                .frame(width: 4)
                .opacity(work.status == "in_progress" ? (pulse ? 1 : 0.45) : 1)

            VStack(alignment: .leading, spacing: 8) {
                Text(work.title)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(2)
                HStack(spacing: 6) {
                    badge(work.status, color: statusColor)
                    badge(work.executor, color: CCCTheme.accent)
                }
                if !work.dependsOn.isEmpty {
                    Text("依赖 \(work.dependsOn.joined(separator: ", "))")
                        .font(CCCTheme.mono)
                        .foregroundStyle(CCCTheme.muted)
                        .lineLimit(1)
                }
            }
            .padding(12)
            Spacer(minLength: 0)
        }
        .background(CCCTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(CCCTheme.border.opacity(0.8), lineWidth: 1)
        )
        .shadow(color: Color.black.opacity(0.03), radius: 3, y: 1)
        .onAppear {
            guard work.status == "in_progress" || work.status == "testing" else { return }
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                pulse = true
            }
        }
        .animation(.easeInOut(duration: 0.3), value: work.status)
    }

    private func badge(_ text: String, color: Color) -> some View {
        Text(text)
            .font(CCCTheme.mono)
            .foregroundStyle(color)
            .padding(.horizontal, 7)
            .padding(.vertical, 2)
            .background(color.opacity(0.12))
            .clipShape(Capsule())
    }
}

struct FlowConnector: View {
    let active: Bool

    var body: some View {
        HStack {
            Spacer().frame(width: 22)
            Rectangle()
                .fill(active ? CCCTheme.nodeRunning.opacity(0.55) : CCCTheme.border)
                .frame(width: 2, height: 18)
            Spacer()
        }
        .frame(height: 18)
    }
}

struct FlowLegend: View {
    var body: some View {
        HStack(spacing: 10) {
            legendDot(CCCTheme.nodePending, "待")
            legendDot(CCCTheme.nodeRunning, "跑")
            legendDot(CCCTheme.nodeDone, "完")
            legendDot(CCCTheme.nodeFail, "异")
        }
        .font(CCCTheme.mono)
        .foregroundStyle(CCCTheme.muted)
    }

    private func legendDot(_ c: Color, _ t: String) -> some View {
        HStack(spacing: 3) {
            Circle().fill(c).frame(width: 7, height: 7)
            Text(t)
        }
    }
}

// MARK: - Transfer / Settings

struct TransferSheet: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("转任务（聊透门禁）")
                .font(.system(size: 18, weight: .semibold, design: .serif))
            Text("通过后仅创建待办大卡 (epic)；Engine 随后扇出到右侧流程图。")
                .font(.system(size: 12))
                .foregroundStyle(CCCTheme.muted)

            Form {
                TextField("标题", text: $model.transferTitle)
                TextField("目标", text: $model.transferGoal, axis: .vertical)
                    .lineLimit(3...6)
                TextField("验收（每行一条）", text: $model.transferAcceptance, axis: .vertical)
                    .lineLimit(3...8)
                TextField("产线 / pipeline", text: $model.transferPipeline)
                Picker("执行面意图", selection: $model.transferExecutor) {
                    Text("opencode（默认）").tag("opencode")
                    Text("python").tag("python")
                    Text("ollama").tag("ollama")
                    Text("cli").tag("cli")
                    Text("auto").tag("auto")
                }
            }
            .formStyle(.grouped)

            if let err = model.transferError {
                Text(err)
                    .foregroundStyle(CCCTheme.nodeFail)
                    .font(.system(size: 12))
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack {
                Button("取消") { dismiss() }
                Spacer()
                Button("确认转任务") {
                    Task { await model.submitTransfer() }
                }
                .buttonStyle(.borderedProminent)
                .tint(CCCTheme.accent)
                .disabled(model.busy)
            }
        }
        .padding(24)
        .frame(width: 520, height: 560)
        .background(CCCTheme.bg)
    }
}

struct SettingsView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        Form {
            TextField("CCC_SERVER", text: $model.serverURLString)
            TextField("用户", text: $model.authUser)
            SecureField("密码", text: $model.authPass)
            Button("重新连接") {
                Task { await model.reconnect() }
            }
        }
        .padding(20)
        .frame(width: 420, height: 220)
    }
}
