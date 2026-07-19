import AppKit
import SwiftUI

/// Codex 三栏 + 系统材质侧栏
struct ContentView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        ZStack(alignment: .top) {
            HStack(spacing: 0) {
                CodexSidebar()
                    .frame(width: 260)
                    .cccHairline(.trailing)

                Group {
                    switch model.destination {
                    case .chat:
                        CodexChatPane()
                            .frame(minWidth: 480)
                    case .board:
                        BoardView()
                            .frame(minWidth: 560)
                    case .ops:
                        OpsView()
                            .frame(minWidth: 480)
                    }
                }

                if model.destination == .chat {
                    FlowRail()
                        .frame(minWidth: 280, idealWidth: 320, maxWidth: 380)
                        .cccHairline(.leading)
                }
            }

            if let toast = model.toast {
                ToastBanner(message: toast, isError: true) {
                    model.dismissToast()
                }
                .padding(.top, 14)
                .transition(.opacity.combined(with: .move(edge: .top)))
                .zIndex(10)
            }
        }
        .foregroundStyle(CCCTheme.ink)
        .task { await model.bootstrap() }
        .sheet(isPresented: $model.showTransferSheet) {
            TransferSheet().environmentObject(model)
        }
        .animation(.easeOut(duration: 0.18), value: model.toast)
    }
}

// MARK: - Sidebar

struct CodexSidebar: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                SoftRow(title: "新对话", icon: "plus", prominent: true) {
                    Task { await model.newThread() }
                }
                .disabled(!model.connected)
                .opacity(model.connected ? 1 : 0.4)
                .padding(.bottom, 6)

                if model.connected {
                    projectMenu
                        .padding(.bottom, 4)
                }

                SoftRow(title: "看板", icon: "square.grid.2x2", selected: model.destination == .board) {
                    model.selectDestination(.board)
                }
                SoftRow(title: "运维", icon: "wrench.and.screwdriver", selected: model.destination == .ops) {
                    model.selectDestination(.ops)
                }
            }
            .padding(.horizontal, 10)
            .padding(.top, CCCTheme.trafficLightInset)
            .padding(.bottom, 10)

            divider

            if !model.connected {
                offlineBlock
            } else {
                threadList
            }

            Spacer(minLength: 0)

            divider

            VStack(spacing: 1) {
                SoftRow(title: "用户", icon: "person") {
                    model.showToast("账号功能预留，尚未接入")
                }
                SoftRow(title: "设置", icon: "gearshape") {
                    openAppSettings()
                }
            }
            .padding(.horizontal, 8)
            .padding(.top, 6)
            .padding(.bottom, 12)
        }
        .background(CCCTheme.sidebar)
    }

    private var projectMenu: some View {
        Menu {
            ForEach(model.projects) { p in
                Button {
                    Task { await model.selectProject(p.id) }
                } label: {
                    HStack {
                        Text(p.name)
                        if p.id == model.selectedProjectId {
                            Image(systemName: "checkmark")
                        }
                    }
                }
            }
        } label: {
            HStack(spacing: 6) {
                Text(model.selectedProject?.name ?? "项目")
                    .font(.system(size: 12.5))
                    .lineLimit(1)
                Spacer(minLength: 0)
                Image(systemName: "chevron.down")
                    .font(.system(size: 8, weight: .semibold))
                    .foregroundStyle(CCCTheme.faint)
            }
            .foregroundStyle(CCCTheme.secondary)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .contentShape(Rectangle())
        }
    }

    private var offlineBlock: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("未连接服务")
                .font(.system(size: 13, weight: .medium))
            Text("在设置中填写 Server 地址。")
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint)
                .fixedSize(horizontal: false, vertical: true)
            Button("打开设置") { openAppSettings() }
                .buttonStyle(.borderedProminent)
                .tint(CCCTheme.accent)
                .controlSize(.small)
            Button("重试") { Task { await model.reconnect() } }
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.secondary)
                .buttonStyle(.plain)
        }
        .padding(14)
    }

    private var threadList: some View {
        ScrollView(showsIndicators: false) {
            LazyVStack(spacing: 1) {
                if model.threads.isEmpty {
                    Text("暂无对话")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 12)
                }
                ForEach(model.threads) { thread in
                    let on = model.selectedThreadId == thread.thread_id
                    SoftRow(
                        title: thread.title ?? "新对话",
                        selected: on,
                        trailingBusy: model.isThreadStreaming(thread.thread_id)
                    ) {
                        Task { await model.openThread(thread.thread_id) }
                    }
                    .contextMenu {
                        Button("重命名…") { model.beginRenameThread(thread) }
                        Button("删除", role: .destructive) {
                            Task { await model.deleteThread(thread.thread_id) }
                        }
                    }
                }
            }
            .padding(.horizontal, 8)
            .padding(.top, 8)
            .padding(.bottom, 16)
        }
        .sheet(isPresented: Binding(
            get: { model.renameThreadId != nil },
            set: { if !$0 { model.renameThreadId = nil } }
        )) {
            VStack(alignment: .leading, spacing: 14) {
                Text("重命名对话")
                    .font(.system(size: 16, weight: .semibold))
                TextField("标题", text: $model.renameDraft)
                    .textFieldStyle(.roundedBorder)
                HStack {
                    Spacer()
                    Button("取消") { model.renameThreadId = nil }
                    Button("保存") { Task { await model.commitRenameThread() } }
                        .keyboardShortcut(.defaultAction)
                }
            }
            .padding(20)
            .frame(width: 360)
        }
    }

    private var divider: some View {
        Rectangle()
            .fill(CCCTheme.border)
            .frame(height: 1)
            .padding(.horizontal, 12)
    }

    private func openAppSettings() {
        NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
    }
}

// MARK: - Chat（Cursor 节奏：消息区占满 + 输入条贴底）

struct CodexChatPane: View {
    @EnvironmentObject var model: AppModel
    /// 草稿必须本地持有：右栏 SSE 刷新 AppModel 时不能重绘冲掉键盘
    @State private var composerText: String = ""
    @FocusState private var composerFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            statusBar

            if !model.connected {
                offlineCenter
            } else {
                messageArea
                composerDock
            }
        }
        .background(CCCTheme.chatBg)
        .onAppear {
            NSApp.activate(ignoringOtherApps: true)
            composerFocused = true
        }
    }

    private var statusBar: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(model.connected ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                .frame(width: 6, height: 6)
            Text(model.connected
                   ? (model.currentThreadStreaming
                      ? (model.agentMode == "local" ? "本机生成中…" : "生成中…")
                      : model.statusText)
                   : "未连接")
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.faint)
            if model.agentMode == "local" && model.connected {
                Text("loop-code")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(CCCTheme.accent.opacity(0.85))
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(CCCTheme.accent.opacity(0.12), in: Capsule())
            }
            Spacer(minLength: 0)
            if model.busy && !model.currentThreadStreaming {
                ProgressView().controlSize(.mini)
            }
            if model.currentThreadStreaming {
                ProgressView().controlSize(.mini)
                Button("停止") { model.cancelChat() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(CCCTheme.accent)
            }
            Button("导出") { model.exportThreadToPasteboard() }
                .buttonStyle(.plain)
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.faint)
                .disabled(model.messages.isEmpty)
        }
        .padding(.horizontal, 24)
        .padding(.top, 8)
        .padding(.bottom, 4)
    }

    private var offlineCenter: some View {
        VStack(spacing: 10) {
            Spacer()
            Text("未连接到 Server")
                .font(CCCTheme.title)
                .foregroundStyle(CCCTheme.ink)
            Text(model.serverURLString)
                .font(.system(size: 13, design: .monospaced))
                .foregroundStyle(CCCTheme.secondary)
            if let err = model.lastError, !err.isEmpty {
                Text(err)
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.faint)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }
            HStack(spacing: 12) {
                Button("重试") { Task { await model.reconnect() } }
                    .buttonStyle(.borderedProminent)
                    .tint(CCCTheme.accent)
                    .controlSize(.small)
                Button("打开设置") {
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                }
                .buttonStyle(.plain)
                .foregroundStyle(CCCTheme.accent)
                .controlSize(.small)
            }
            .padding(.top, 4)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private var messageArea: some View {
        ScrollViewReader { proxy in
            ScrollView(showsIndicators: false) {
                LazyVStack(alignment: .leading, spacing: 18) {
                    if model.messages.isEmpty {
                        VStack(spacing: 8) {
                            Spacer().frame(height: 72)
                            Text("有什么可以帮忙的？")
                                .font(CCCTheme.title)
                                .foregroundStyle(CCCTheme.ink)
                            Text("说明目标与验收，再转任务。")
                                .font(.system(size: 13.5))
                                .foregroundStyle(CCCTheme.faint)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.bottom, 24)
                    }
                    ForEach(model.messages) { msg in
                        CodexMessageRow(message: msg)
                            .id("\(model.selectedThreadId ?? "")-\(msg.id)")
                            .contextMenu {
                                Button("复制") { model.copyMessage(msg.content) }
                            }
                    }
                }
                .id(model.selectedThreadId ?? "none") // 切会话强制重建，防工具轨串台
                .frame(maxWidth: CCCTheme.chatMaxWidth)
                .frame(maxWidth: .infinity)
                .padding(.horizontal, 28)
                .padding(.top, 8)
                .padding(.bottom, 16)
            }
            .onChange(of: model.messages.count) { _ in scroll(proxy) }
            .onChange(of: model.messages.last?.content) { _ in scroll(proxy) }
        }
    }

    private func scroll(_ proxy: ScrollViewProxy) {
        guard let last = model.messages.last else { return }
        withAnimation(.easeOut(duration: 0.12)) {
            proxy.scrollTo(last.id, anchor: .bottom)
        }
    }

    /// 矮输入条；草稿用本地 @State，避免 SSE 冲焦点
    private var composerDock: some View {
        VStack(spacing: 6) {
            quickActionBar

            HStack {
                Button {
                    model.openTransferSheet()
                } label: {
                    Text("转任务")
                        .font(.system(size: 11.5, weight: .medium))
                        .foregroundStyle(
                            model.selectedProject?.isDispatchable == true
                                ? CCCTheme.accent
                                : CCCTheme.faint
                        )
                }
                .buttonStyle(.plain)
                .disabled(model.selectedProject?.isDispatchable != true)
                Spacer(minLength: 0)
            }
            .frame(maxWidth: CCCTheme.chatMaxWidth)
            .frame(maxWidth: .infinity)

            HStack(alignment: .bottom, spacing: 8) {
                ComposerTextView(
                    text: $composerText,
                    placeholder: model.selectedProject?.isOrch == true
                        ? "编排仓可聊方案；转任务请切到业务项目…"
                        : "问任何问题…",
                    isEnabled: model.connected,
                    onSubmit: { sendFromComposer() }
                )
                .frame(minHeight: 22, idealHeight: 22, maxHeight: 72)
                .padding(.leading, 8)
                .padding(.vertical, 6)

                if model.currentThreadStreaming && composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    Button {
                        model.cancelChat()
                    } label: {
                        Image(systemName: "stop.fill")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundStyle(Color.white)
                            .frame(width: 26, height: 26)
                            .background(Circle().fill(CCCTheme.nodeFail.opacity(0.9)))
                    }
                    .buttonStyle(.plain)
                    .padding(.trailing, 8)
                    .padding(.bottom, 6)
                    .help("停止生成")
                } else {
                    Button {
                        sendFromComposer()
                    } label: {
                        Image(systemName: model.currentThreadStreaming ? "arrow.up.circle.fill" : "arrow.up")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(canSend ? Color.white : CCCTheme.faint)
                            .frame(width: 26, height: 26)
                            .background(Circle().fill(canSend ? CCCTheme.accent : CCCTheme.hover))
                    }
                    .buttonStyle(.plain)
                    .disabled(!canSend)
                    .padding(.trailing, 8)
                    .padding(.bottom, 6)
                    .help(model.currentThreadStreaming ? "停止当前并发送" : "发送")
                }
            }
            .frame(minHeight: 36)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(CCCTheme.surface)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(CCCTheme.border, lineWidth: 1)
            )
            .frame(maxWidth: CCCTheme.chatMaxWidth)
            .frame(maxWidth: .infinity)
        }
        .padding(.horizontal, 28)
        .padding(.top, 6)
        .padding(.bottom, 36)
        .background(CCCTheme.chatBg)
        .onChange(of: model.composerBounce) { bounce in
            // 仅失败回填一次
            guard let bounce, !bounce.isEmpty else { return }
            composerText = bounce
            model.composerBounce = nil
        }
    }

    private var quickActionBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                quickChip("对齐基线") {
                    Task { await model.alignBaseline() }
                }
                quickChip("下一步") {
                    model.applyQuickPrompt(QuickPrompts.nextStep, uiLabel: "下一步")
                }
                quickChip("定稿") {
                    model.applyQuickPrompt(QuickPrompts.finalize, uiLabel: "定稿方案")
                }
                quickChip("扫风险") {
                    model.applyQuickPrompt(QuickPrompts.scanRisks, uiLabel: "扫风险")
                }
            }
        }
        .frame(maxWidth: CCCTheme.chatMaxWidth)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func quickChip(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(CCCTheme.secondary)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(
                    Capsule(style: .continuous)
                        .fill(CCCTheme.hover)
                )
        }
        .buttonStyle(.plain)
        .disabled(!model.connected)
    }

    private var canSend: Bool {
        model.connected && !composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func sendFromComposer() {
        let text = composerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        // 立刻清空本地输入；不要经 model.draft，避免 onChange 回填
        composerText = ""
        model.sendUserMessage(text, stopAndSend: true)
    }
}

struct CodexMessageRow: View {
    let message: ChatMessage

    var body: some View {
        let isUser = message.role == "user"
        let body = message.content.isEmpty && message.isStreaming && message.toolSteps.isEmpty
            ? "…"
            : message.content
        Group {
            if isUser {
                HStack(alignment: .top, spacing: 0) {
                    Spacer(minLength: 80)
                    Text(body)
                        .font(CCCTheme.body)
                        .foregroundStyle(CCCTheme.ink)
                        .textSelection(.enabled)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .fill(CCCTheme.bubbleUser)
                        )
                }
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    // 生成一开始就显示进度轨（不必等首个 tool_use）
                    if message.isStreaming || !message.toolSteps.isEmpty {
                        ToolProgressRail(
                            steps: message.toolSteps,
                            filesChanged: message.filesChanged,
                            finished: message.toolsFinished || !message.isStreaming,
                            placeholder: message.toolSteps.isEmpty ? "正在思考 / 调用工具…" : nil
                        )
                    }
                    if !body.isEmpty && body != "…" {
                        MarkdownText(source: body)
                    }
                }
                .padding(.trailing, 40)
            }
        }
    }
}

// MARK: - Flow rail（跟当前对话绑定）

struct FlowRail: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Color.clear.frame(height: 8)

            // 标题：说明这是「本对话的编排」，不是全局测试列表
            VStack(alignment: .leading, spacing: 4) {
                Text("本对话编排")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(CCCTheme.ink)
                if let title = boundEpicTitle {
                    Text(title)
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.secondary)
                        .lineLimit(2)
                } else {
                    Text(model.selectedThreadId == nil
                         ? "先选左侧对话"
                         : "转任务后显示流程")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            .padding(.horizontal, 14)
            .padding(.top, CCCTheme.trafficLightInset - 8)
            .padding(.bottom, 8)

            // 仅当本对话有多个转任务时才出现切换（不再甩全项目 smoke 列表）
            if model.recentEpics.count > 1 {
                Menu {
                    ForEach(model.recentEpics) { epic in
                        Button {
                            Task { await model.selectEpic(epic.epic_id) }
                        } label: {
                            HStack {
                                Text(epic.title ?? epic.epic_id)
                                if epic.epic_id == model.currentEpicId {
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Text("切换本对话任务")
                            .font(.system(size: 11, weight: .medium))
                        Image(systemName: "chevron.down")
                            .font(.system(size: 8, weight: .semibold))
                        Spacer(minLength: 0)
                    }
                    .foregroundStyle(CCCTheme.accent)
                    .padding(.horizontal, 14)
                    .padding(.bottom, 6)
                }
            }

            if let hint = model.flowFanoutHint {
                VStack(alignment: .leading, spacing: 8) {
                    Text(hint)
                        .font(.system(size: 11.5))
                        .foregroundStyle(CCCTheme.nodeFail)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 10) {
                        Button("开运维") {
                            model.selectDestination(.ops)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(CCCTheme.accent)
                        .controlSize(.small)
                        Button("忽略") {
                            model.clearFanoutHint()
                        }
                        .buttonStyle(.plain)
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.faint)
                    }
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(CCCTheme.nodeFail.opacity(0.08))
                )
                .padding(.horizontal, 12)
                .padding(.bottom, 8)
            }

            FlowCanvasView(
                epic: model.flowEpic,
                epicId: model.currentEpicId,
                works: model.flowWorks,
                headline: model.flowHeadline,
                emptyMessage: model.flowEmptyMessage,
                onOpenOps: { model.selectDestination(.ops) },
                onSelectNode: { model.openNodeDetail(id: $0) }
            )
        }
        .background(CCCTheme.sidebar)
        .sheet(item: $model.selectedNodeDetail) { detail in
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(detail.kind == "epic" ? "任务" : "步骤")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                    Spacer()
                    Button("关闭") { model.dismissNodeDetail() }
                        .buttonStyle(.plain)
                        .foregroundStyle(CCCTheme.secondary)
                }
                Text(detail.title)
                    .font(.system(size: 16, weight: .semibold))
                if !detail.status.isEmpty {
                    Text(detail.status)
                        .font(.system(size: 12))
                        .foregroundStyle(CCCTheme.secondary)
                }
                ScrollView {
                    Text(detail.body)
                        .font(.system(size: 13))
                        .foregroundStyle(CCCTheme.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
                if detail.kind == "work", model.flowWorks.contains(where: { $0.workId == detail.id && $0.isFailed }) {
                    Button("在运维中查看") {
                        model.dismissNodeDetail()
                        model.selectDestination(.ops)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(CCCTheme.accent)
                }
            }
            .padding(22)
            .frame(width: 420, height: 360)
        }
    }

    private var boundEpicTitle: String? {
        if let cur = model.recentEpics.first(where: { $0.epic_id == model.currentEpicId }) {
            return cur.title ?? cur.epic_id
        }
        return model.flowEpic?.title ?? model.currentEpicId
    }
}

// MARK: - Sheets

struct TransferSheet: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("转任务")
                .font(.system(size: 20, weight: .semibold))
                .tracking(-0.4)
            Text("确认门禁字段后写入待办；右侧展开编排。")
                .font(CCCTheme.callout)
                .foregroundStyle(CCCTheme.faint)

            Form {
                TextField("标题", text: $model.transferTitle)
                TextField("目标", text: $model.transferGoal, axis: .vertical)
                    .lineLimit(3...6)
                TextField("验收（每行一条）", text: $model.transferAcceptance, axis: .vertical)
                    .lineLimit(3...8)
                TextField("产线", text: $model.transferPipeline)
                Picker("可行性", selection: $model.transferFeasibility) {
                    Text("可执行").tag("ok")
                    Text("阻塞").tag("blocked")
                }
                if model.transferFeasibility == "blocked" {
                    TextField("阻塞原因", text: $model.transferFeasibilityReason, axis: .vertical)
                        .lineLimit(2...4)
                }
                Picker("执行面", selection: $model.transferExecutor) {
                    Text("写码").tag("opencode")
                    Text("脚本").tag("python")
                    Text("ollama").tag("ollama")
                    Text("cli").tag("cli")
                    Text("auto").tag("auto")
                }
                TextField("方案正文（可选）", text: $model.transferPlanMd, axis: .vertical)
                    .lineLimit(4...10)
            }
            .formStyle(.grouped)

            if let err = model.transferError {
                Text(err)
                    .font(CCCTheme.callout)
                    .foregroundStyle(CCCTheme.nodeFail)
            }

            HStack {
                Button("取消") { dismiss() }
                    .foregroundStyle(CCCTheme.secondary)
                Spacer()
                Button("重新预填") { model.prefillTransferFromChat() }
                    .foregroundStyle(CCCTheme.secondary)
                Button("确认") { Task { await model.submitTransfer() } }
                    .buttonStyle(.borderedProminent)
                    .tint(CCCTheme.accent)
                    .disabled(model.busy)
            }
        }
        .padding(28)
        .frame(width: 520, height: 640)
    }
}

struct SettingsView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        Form {
            TextField("Server (Hub)", text: $model.serverURLString)
            TextField("本机 Agent", text: $model.agentURLString)
            TextField("本机工作区", text: $model.localWorkspacePath)
            Text("Agent 探测到则走 localhost；否则回退 Hub。转任务/右栏仍走 Hub。")
                .font(.caption)
                .foregroundStyle(.secondary)
            TextField("用户", text: $model.authUser)
            SecureField("密码", text: $model.authPass)
            Button("重新连接") { Task { await model.reconnect() } }
        }
        .padding(20)
        .frame(width: 440, height: 280)
    }
}
