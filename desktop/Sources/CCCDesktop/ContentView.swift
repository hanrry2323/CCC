import SwiftUI

struct ContentView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider().overlay(CCCTheme.border)
            HStack(spacing: 0) {
                ProjectSidebar()
                    .frame(width: 240)
                Divider().overlay(CCCTheme.border)
                ChatPane()
                    .frame(minWidth: 420)
                Divider().overlay(CCCTheme.border)
                FlowRail()
                    .frame(width: 300)
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
        HStack(alignment: .firstTextBaseline) {
            Text("CCC")
                .font(CCCTheme.brandFont)
            Text("Desktop")
                .font(.system(size: 13, weight: .medium, design: .serif))
                .foregroundStyle(CCCTheme.muted)
            Spacer()
            Button("转任务") {
                model.showTransferSheet = true
            }
            .buttonStyle(.borderedProminent)
            .tint(CCCTheme.accent)
            .disabled(model.selectedProjectId == nil)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
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
        HStack {
            Text(model.statusText)
                .font(CCCTheme.mono)
                .foregroundStyle(CCCTheme.muted)
            Spacer()
            if let err = model.lastError {
                Text(err)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.nodeFail)
                    .lineLimit(1)
            }
            if model.busy {
                ProgressView().controlSize(.small)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(CCCTheme.panel)
    }
}

struct ProjectSidebar: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("项目")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(CCCTheme.muted)
                Spacer()
                Button {
                    Task { await model.refreshProjects() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.plain)
            }
            .padding(12)

            List(selection: Binding(
                get: { model.selectedProjectId },
                set: { id in
                    if let id {
                        Task { await model.selectProject(id) }
                    }
                }
            )) {
                ForEach(model.projects) { p in
                    HStack {
                        Image(systemName: "folder.fill")
                            .foregroundStyle(p.isDispatchable ? CCCTheme.accent : CCCTheme.muted)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.name)
                                .font(.system(size: 13, weight: .medium))
                            Text(p.role ?? "app")
                                .font(CCCTheme.mono)
                                .foregroundStyle(CCCTheme.muted)
                        }
                    }
                    .tag(p.id)
                    .listRowBackground(CCCTheme.panel)
                }
            }
            .listStyle(.sidebar)
            .scrollContentBackground(.hidden)

            Divider().overlay(CCCTheme.border)

            HStack {
                Text("对话")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(CCCTheme.muted)
                Spacer()
                Button {
                    Task { await model.newThread() }
                } label: {
                    Image(systemName: "plus")
                }
                .buttonStyle(.plain)
            }
            .padding(12)

            List(selection: Binding(
                get: { model.selectedThreadId },
                set: { id in
                    if let id {
                        Task { await model.openThread(id) }
                    }
                }
            )) {
                ForEach(model.threads) { t in
                    Text(t.title ?? t.thread_id)
                        .font(.system(size: 12))
                        .lineLimit(2)
                        .tag(t.thread_id)
                }
            }
            .listStyle(.sidebar)
            .scrollContentBackground(.hidden)
        }
        .background(CCCTheme.panel)
    }
}

struct ChatPane: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                        if model.messages.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("方案 Agent")
                                    .font(.system(size: 18, weight: .semibold, design: .serif))
                                Text("聊透目标、验收与产线后，点「转任务」写入待办大卡。编排在右侧展开。")
                                    .font(CCCTheme.bodyFont)
                                    .foregroundStyle(CCCTheme.muted)
                            }
                            .padding(28)
                        }
                        ForEach(Array(model.messages.enumerated()), id: \.offset) { _, msg in
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
                .disabled(model.busy || model.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(16)
            .background(CCCTheme.panel.opacity(0.85))
        }
        .background(CCCTheme.bg)
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        let isUser = message.role == "user"
        HStack {
            if isUser { Spacer(minLength: 40) }
            Text(message.content)
                .font(CCCTheme.bodyFont)
                .textSelection(.enabled)
                .padding(12)
                .background(isUser ? CCCTheme.accent.opacity(0.15) : Color.white.opacity(0.65))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(CCCTheme.border.opacity(0.6), lineWidth: 1)
                )
            if !isUser { Spacer(minLength: 40) }
        }
        .transition(.opacity.combined(with: .move(edge: .bottom)))
    }
}

struct FlowRail: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("编排流程")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(CCCTheme.muted)
                .padding(12)

            if let epic = model.currentEpicId {
                Text(epic)
                    .font(CCCTheme.mono)
                    .foregroundStyle(CCCTheme.accent)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 8)
            }

            if model.flowWorks.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    Image(systemName: "point.3.connected.trianglepath.dotted")
                        .font(.system(size: 28))
                        .foregroundStyle(CCCTheme.muted.opacity(0.7))
                        .opacity(0.85)
                    Text(model.flowEmptyMessage)
                        .font(CCCTheme.bodyFont)
                        .foregroundStyle(CCCTheme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(20)
                Spacer()
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(model.flowWorks.enumerated()), id: \.element.id) { idx, work in
                            FlowNode(work: work, isLast: idx == model.flowWorks.count - 1)
                        }
                    }
                    .padding(12)
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
}

struct FlowNode: View {
    let work: FlowWork
    let isLast: Bool

    var color: Color {
        switch work.status {
        case "released", "verified": return CCCTheme.nodeDone
        case "in_progress", "testing": return CCCTheme.nodeRunning
        case "abnormal": return CCCTheme.nodeFail
        default: return CCCTheme.nodePending
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(spacing: 0) {
                Circle()
                    .fill(color)
                    .frame(width: 12, height: 12)
                    .shadow(color: color.opacity(0.45), radius: 4, y: 1)
                if !isLast {
                    Rectangle()
                        .fill(CCCTheme.border)
                        .frame(width: 2, height: 36)
                }
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(work.title)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(2)
                HStack(spacing: 6) {
                    Text(work.status)
                        .font(CCCTheme.mono)
                    Text("·")
                    Text(work.executor)
                        .font(CCCTheme.mono)
                        .foregroundStyle(CCCTheme.accent)
                }
                .foregroundStyle(CCCTheme.muted)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 4)
        .animation(.easeInOut(duration: 0.35), value: work.status)
    }
}

struct TransferSheet: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("转任务（聊透门禁）")
                .font(.system(size: 18, weight: .semibold, design: .serif))
            Text("通过后仅创建待办大卡 (epic)；Engine 随后扇出。")
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

            if let err = model.lastError {
                Text(err)
                    .foregroundStyle(CCCTheme.nodeFail)
                    .font(.system(size: 12))
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
                Task { await model.refreshProjects() }
            }
        }
        .padding(20)
        .frame(width: 420, height: 220)
    }
}
