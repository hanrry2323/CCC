import AppKit
import SwiftUI

/// Codex 三栏 + 系统材质侧栏
struct ContentView: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState

    var body: some View {
        ZStack(alignment: .top) {
            HStack(spacing: 0) {
                CodexSidebar()
                    .frame(width: 260)
                    .cccHairline(.trailing)

                Group {
                    switch window.destination {
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

                if window.destination == .chat {
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
        // bootstrap 在 WindowRootView，避免多窗重复打 Hub
        .sheet(isPresented: Binding(
            get: { model.isTransferSheetPresented(for: window.threadId) },
            set: { if !$0 { model.dismissTransferSheet(threadId: window.threadId) } }
        )) {
            TransferSheet(threadId: window.threadId ?? model.transferSheetThreadId ?? "")
                .environmentObject(model)
        }
        .sheet(isPresented: Binding(
            get: { model.previewMarkdown != nil },
            set: { if !$0 { model.previewMarkdown = nil } }
        )) {
            MessagePreviewSheet(markdown: model.previewMarkdown ?? "")
                .environmentObject(model)
        }
        .animation(.easeOut(duration: 0.18), value: model.toast)
        // 纯文字嵌进顶栏右侧；依赖 model.routerUsageTick 触发 updateNSView
        .background(
            TitlebarUsageAccessory(model: model)
                .frame(width: 0, height: 0)
                .id(model.routerUsageTick)
        )
        .toolbarBackground(CCCTheme.sidebar, for: .windowToolbar)
        .toolbarBackground(.visible, for: .windowToolbar)
        .toolbarColorScheme(.light, for: .windowToolbar)
    }
}

// MARK: - Sidebar

struct CodexSidebar: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                SoftRow(title: "重置对话", icon: "arrow.counterclockwise", prominent: true) {
                    Task { await model.resetConversation(projectId: window.projectId) }
                }
                .disabled(!model.connected)
                .opacity(model.connected ? 1 : 0.4)
                .padding(.bottom, 6)

                SoftRow(title: "对话", icon: "bubble.left.and.bubble.right", selected: window.destination == .chat) {
                    window.destination = .chat
                    model.selectDestination(.chat, projectId: window.projectId)
                }
                SoftRow(title: "看板", icon: "square.grid.2x2", selected: window.destination == .board) {
                    window.destination = .board
                    model.selectDestination(.board, projectId: window.projectId)
                }
                SoftRow(title: "运维", icon: "wrench.and.screwdriver", selected: window.destination == .ops) {
                    window.destination = .ops
                    model.selectDestination(.ops, projectId: window.projectId)
                }
            }
            .padding(.horizontal, 10)
            .padding(.top, CCCTheme.trafficLightInset)
            .padding(.bottom, 10)

            divider

            if !model.connected {
                offlineBlock
            } else {
                projectCardList
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

    private var projectCardList: some View {
        ScrollView(showsIndicators: false) {
            LazyVStack(spacing: 2) {
                if model.projects.isEmpty {
                    Text("暂无项目")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 12)
                }
                ForEach(model.projects) { project in
                    ProjectCard(
                        project: project,
                        isSelected: project.id == window.projectId
                    )
                }
            }
            .padding(.horizontal, 8)
            .padding(.top, 8)
            .padding(.bottom, 16)
        }
    }

    private var offlineBlock: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(model.canChat ? "Hub 暂不可达" : "本机 Agent 未就绪")
                .font(.system(size: 13, weight: .medium))
            Text(
                model.canChat
                    ? "可继续聊；转任务需恢复 Hub。"
                    : "对话只走本机 sidecar。设置中确认 Agent 地址，或执行 install-agent-sidecar-plist.sh --start。"
            )
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

    var body: some View {
        // 仍订阅 ChatState 以刷新 streamStatus；消息列表只用 threadMessages
        CodexChatPaneBody(chat: model.chat)
            .environmentObject(model)
    }
}

struct CodexChatPaneBody: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    @ObservedObject var chat: ChatState
    /// 草稿必须本地持有：右栏 SSE 刷新 AppModel 时不能重绘冲掉键盘
    @State private var composerText: String = ""
    @State private var lastScrollTargetId: String = ""
    @FocusState private var composerFocused: Bool

    /// 本窗唯一项目焦点；禁止回落全局 selected（否则他窗切项会拖走本窗历史）
    private var paneProjectId: String? {
        window.projectId
    }

    private var paneThreadId: String? {
        paneProjectId.map { LocalSessionStore.conversationThreadId(for: $0) }
    }

    /// 本窗消息：只绑 window.projectId 对应线程；观察 threadRevision 接收后台流式
    private var displayMessages: [ChatMessage] {
        let tid = paneThreadId
        if let tid {
            _ = model.threadRevision[tid]
        }
        // 强制不读 chat.messages，避免全局选中切换时串台
        return model.messagesForThread(tid)
    }

    private var paneStreaming: Bool {
        guard let tid = paneThreadId else { return false }
        return model.isThreadStreaming(tid)
    }

    /// 状态文案：只读本窗 thread 的 streamStatus（OpenCode session 隔离）
    private var paneStatusText: String {
        let local = model.streamStatus(for: paneThreadId)
        if paneStreaming, !local.isEmpty {
            return local
        }
        return model.statusText
    }

    var body: some View {
        VStack(spacing: 0) {
            statusBar

            if !model.canChat {
                offlineCenter
            } else {
                messageArea
                if model.transferDraft(for: paneThreadId) != nil {
                    transferConfirmBar
                }
                composerDock
            }
        }
        .background(CCCTheme.chatBg)
        .onAppear {
            if window.projectId == nil {
                window.projectId = model.selectedProjectId
            }
            if let pid = window.projectId {
                model.ensureThreadHydrated(projectId: pid)
            }
            NSApp.activate(ignoringOtherApps: true)
            composerFocused = true
        }
        .onChange(of: window.projectId) { pid in
            lastScrollTargetId = ""
            if let pid {
                model.ensureThreadHydrated(projectId: pid)
            }
        }
    }

    /// 定稿 JSON 就绪后的一键转任务条
    private var transferConfirmBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("确认转任务")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(CCCTheme.ink)
                    Text(model.transferDraft(for: paneThreadId)?.previewLine ?? "")
                        .font(.system(size: 11.5))
                        .foregroundStyle(CCCTheme.secondary)
                        .lineLimit(2)
                    if let d = model.transferDraft(for: paneThreadId) {
                        Text("产线 \(d.pipeline) · 验收 \(d.acceptanceLines.count) 条")
                            .font(.system(size: 10.5))
                            .foregroundStyle(CCCTheme.faint)
                    }
                }
                Spacer(minLength: 0)
                Button("展开编辑") { model.openTransferSheet(projectId: window.projectId) }
                    .buttonStyle(.plain)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.secondary)
                Button("忽略") { model.dismissPendingTransfer(threadId: paneThreadId) }
                    .buttonStyle(.plain)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
                Button("确认转任务") { model.confirmPendingTransfer(threadId: paneThreadId) }
                    .buttonStyle(.borderedProminent)
                    .tint(CCCTheme.accent)
                    .controlSize(.small)
                    .disabled(
                        model.busy
                            || !model.canTransfer
                            || !(model.transferDraft(for: paneThreadId)?.isGateReady ?? false)
                    )
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .frame(maxWidth: CCCTheme.chatMaxWidth)
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(CCCTheme.accent.opacity(0.08))
        )
        .padding(.horizontal, 28)
        .padding(.bottom, 4)
    }

    private var statusBar: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(model.canChat ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                .frame(width: 6, height: 6)
            Text(paneStatusText)
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.faint)
            Text(model.agentBadge)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(
                    model.canChat
                        ? CCCTheme.accent.opacity(0.9)
                        : CCCTheme.faint
                )
                .padding(.horizontal, 5)
                .padding(.vertical, 1)
                .background(
                    (model.canChat
                        ? CCCTheme.accent.opacity(0.12)
                        : CCCTheme.hover),
                    in: Capsule()
                )
            Spacer(minLength: 0)
            if model.busy && !paneStreaming {
                ProgressView().controlSize(.mini)
            }
            if paneStreaming {
                ProgressView().controlSize(.mini)
                Button("停止") { model.cancelChat(threadId: paneThreadId) }
                    .buttonStyle(.plain)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(CCCTheme.accent)
            }
            Button("导出") { model.exportThreadToPasteboard(threadId: paneThreadId) }
                .buttonStyle(.plain)
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.faint)
                .disabled(displayMessages.isEmpty)
        }
        .padding(.horizontal, 24)
        .padding(.top, 8)
        .padding(.bottom, 4)
    }

    private var offlineCenter: some View {
        VStack(spacing: 10) {
            Spacer()
            Text("本机 Agent 未就绪")
                .font(CCCTheme.title)
                .foregroundStyle(CCCTheme.ink)
            Text("对话只走本机 sidecar（:7788），不经 Hub。")
                .font(.system(size: 13))
                .foregroundStyle(CCCTheme.secondary)
            Text(model.agentURLString)
                .font(.system(size: 13, design: .monospaced))
                .foregroundStyle(CCCTheme.secondary)
            Text("bash scripts/install-agent-sidecar-plist.sh --start")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(CCCTheme.faint)
            if model.hubReachable {
                Text("Hub 可达 · 可转任务（需先能聊出定稿）")
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.faint)
            }
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
        GeometryReader { geometry in
            ScrollViewReader { proxy in
                ScrollView(showsIndicators: false) {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        if displayMessages.isEmpty {
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
                        ForEach(displayMessages) { msg in
                            CodexMessageRow(message: msg)
                                // 固定 id：toolSteps 变化靠 Hashable diff 刷新轨，勿重建整行 Markdown
                                .id("\(paneThreadId ?? "")-\(msg.id)")
                                .environmentObject(model)
                                .contextMenu {
                                    Button("复制") { model.copyMessage(msg.content) }
                                    if msg.role == "user" {
                                        Button("编辑") { model.editUserMessage(msg, projectId: paneProjectId) }
                                    }
                                    if msg.role == "assistant", !msg.isStreaming {
                                        Button("重新生成") {
                                            model.regenerateAssistant(after: msg, projectId: paneProjectId)
                                        }
                                        Button("预览") { model.previewMessage(msg.content) }
                                        if model.canTransfer {
                                            Button("转任务") { model.openTransfer(fromAssistantContent: msg.content) }
                                        }
                                    }
                                }
                        }
                        // Cursor 式底部留白：最新内容居中而非贴底
                        Spacer().frame(height: max(geometry.size.height * 0.35, 120))
                    }
                    .id(paneThreadId ?? "none") // 切会话强制重建，防工具轨串台
                    .frame(maxWidth: CCCTheme.chatMaxWidth)
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 28)
                    .padding(.top, 8)
                }
                .onChange(of: displayMessages.count) { _ in scroll(proxy) }
                .onChange(of: displayMessages.last?.content) { _ in scroll(proxy) }
                .onChange(of: displayMessages.last?.toolSteps.count) { _ in scroll(proxy) }
                .onChange(of: model.threadRevision[paneThreadId ?? ""]) { _ in scroll(proxy) }
                .onChange(of: model.selectedThreadId) { _ in lastScrollTargetId = "" }
            }
        }
    }

    private func scroll(_ proxy: ScrollViewProxy) {
        guard let last = displayMessages.last else { return }
        let lastId = "\(paneThreadId ?? "")-\(last.id)"
        // 同目标跳过，避免每个 delta 反复 withAnimation + scrollTo
        guard lastId != lastScrollTargetId || displayMessages.last?.isStreaming == true else { return }
        // streaming 时节流：仅当内容长度跨过 80 字边界或目标变化才滚
        if last.isStreaming, lastId == lastScrollTargetId {
            let n = last.content.count
            if n > 0, n % 80 != 0 { return }
        }
        lastScrollTargetId = lastId
        withAnimation(.easeOut(duration: 0.2)) {
            proxy.scrollTo(lastId, anchor: .center)
        }
    }

    /// 矮输入条；草稿用本地 @State，避免 SSE 冲焦点
    private var composerDock: some View {
        VStack(spacing: 6) {
            quickActionBar

            HStack {
                Button {
                    model.openTransferSheet(projectId: window.projectId)
                } label: {
                    Text("转任务")
                        .font(.system(size: 11.5, weight: .medium))
                        .foregroundStyle(
                            model.canTransfer(projectId: window.projectId)
                                ? CCCTheme.accent
                                : CCCTheme.faint
                        )
                }
                .buttonStyle(.plain)
                .disabled(!model.canTransfer(projectId: window.projectId))
                Spacer(minLength: 0)
            }
            .frame(maxWidth: CCCTheme.chatMaxWidth)
            .frame(maxWidth: .infinity)

            HStack(alignment: .bottom, spacing: 8) {
                ComposerTextView(
                    text: $composerText,
                    placeholder: (window.projectId.flatMap { pid in model.projects.first { $0.id == pid } }?.isOrch == true)
                        ? "编排仓可聊方案；转任务请切到业务项目…"
                        : "问任何问题…",
                    isEnabled: model.canChat,
                    onSubmit: { sendFromComposer() }
                )
                .frame(minHeight: 22, idealHeight: 22, maxHeight: 72)
                .padding(.leading, 8)
                .padding(.vertical, 6)

                // 固定同一 Button 身份，避免 if/else 换控件触发 Composer 整行重布局打断 IME
                Button {
                    if showStopInsteadOfSend {
                        model.cancelChat(threadId: paneThreadId)
                    } else {
                        sendFromComposer()
                    }
                } label: {
                    Image(systemName: showStopInsteadOfSend
                          ? "stop.fill"
                          : (paneStreaming ? "arrow.up.circle.fill" : "arrow.up"))
                        .font(.system(size: showStopInsteadOfSend ? 10 : 11, weight: .bold))
                        .foregroundStyle(
                            showStopInsteadOfSend
                                ? Color.white
                                : (canSend ? Color.white : CCCTheme.faint)
                        )
                        .frame(width: 26, height: 26)
                        .background(
                            Circle().fill(
                                showStopInsteadOfSend
                                    ? CCCTheme.nodeFail.opacity(0.9)
                                    : (canSend ? CCCTheme.accent : CCCTheme.hover)
                            )
                        )
                }
                .buttonStyle(.plain)
                .disabled(!showStopInsteadOfSend && !canSend)
                .padding(.trailing, 8)
                .padding(.bottom, 6)
                .help(showStopInsteadOfSend
                      ? "停止生成"
                      : (paneStreaming ? "停止当前并发送" : "发送"))
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
            // 仅失败回填一次，且必须是本窗线程
            guard let bounce, !bounce.isEmpty else { return }
            guard model.composerBounceThreadId == nil
                    || model.composerBounceThreadId == paneThreadId else { return }
            composerText = bounce
            model.composerBounce = nil
            model.composerBounceThreadId = nil
        }
    }

    private var quickActionBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                quickChip("对齐基线") {
                    Task { await model.alignBaseline(projectId: paneProjectId) }
                }
                quickChip("下一步") {
                    model.applyQuickPrompt(QuickPrompts.nextStep, uiLabel: "下一步", projectId: paneProjectId)
                }
                quickChip("定稿") {
                    model.applyQuickPrompt(QuickPrompts.finalize, uiLabel: "定稿方案", projectId: paneProjectId)
                }
                quickChip("扫风险") {
                    model.applyQuickPrompt(QuickPrompts.scanRisks, uiLabel: "扫风险", projectId: paneProjectId)
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
        .disabled(!model.canChat)
    }

    private var canSend: Bool {
        model.canChat && !composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private var showStopInsteadOfSend: Bool {
        paneStreaming
            && composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func sendFromComposer() {
        let text = composerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        // 立刻清空本地输入；不要经 model.draft，避免 onChange 回填
        composerText = ""
        model.sendUserMessage(text, projectId: paneProjectId, stopAndSend: true)
    }
}

struct CodexMessageRow: View {
    @EnvironmentObject var model: AppModel
    let message: ChatMessage

    var body: some View {
        if message.kind == "summary" {
            summaryCard
        } else if message.role == "user" {
            userBubble
        } else {
            assistantBlock
        }
    }

    private var summaryCard: some View {
        HStack(spacing: 8) {
            Image(systemName: "archivebox.fill")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
            Text(message.content)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(CCCTheme.hover)
        )
        .frame(maxWidth: .infinity)
        .padding(.vertical, 4)
    }

    private var userBubble: some View {
        let body = message.content.isEmpty && message.isStreaming && message.toolSteps.isEmpty
            ? "…"
            : message.content
        let showActions = !message.isStreaming && !body.isEmpty && body != "…"
        return VStack(alignment: .trailing, spacing: 4) {
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
            if showActions {
                MessageActionBar(role: "user", content: body, message: message)
                    .padding(.trailing, 4)
            }
        }
    }

    private var assistantBlock: some View {
        let body = message.content.isEmpty && message.isStreaming && message.toolSteps.isEmpty
            ? "…"
            : message.content
        let showActions = !message.isStreaming && !body.isEmpty && body != "…"
        return VStack(alignment: .leading, spacing: 8) {
            if message.isStreaming || !message.toolSteps.isEmpty {
                ToolProgressRail(
                    steps: message.toolSteps,
                    filesChanged: message.filesChanged,
                    finished: message.toolsFinished || !message.isStreaming,
                    placeholder: message.toolSteps.isEmpty ? "正在思考 / 调用工具…" : nil
                )
            }
            if let note = message.transientNote, !note.isEmpty {
                Text(note)
                    .font(.system(size: 12).italic())
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 4)
            }
            if !body.isEmpty && body != "…" {
                MarkdownText(source: body)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(CCCTheme.bubbleAssistant)
                    )
                    // 末段流式收尾：isStreaming true→false 时淡入上移，去「弹出」
                    .transition(.opacity.combined(with: .move(edge: .bottom)))
                    .animation(.easeOut(duration: 0.25), value: message.isStreaming)
            }
            if showActions {
                MessageActionBar(role: "assistant", content: body, message: message)
            }
        }
        .padding(.trailing, 40)
    }
}

/// 对齐旧 Hub：复制 / 编辑 / 重新生成 / 预览 / 转任务
struct MessageActionBar: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    let role: String
    let content: String
    let message: ChatMessage

    var body: some View {
        HStack(spacing: 10) {
            actionBtn("复制") { model.copyMessage(content) }
            if role == "user" {
                actionBtn("编辑") { model.editUserMessage(message, projectId: window.projectId) }
            } else {
                actionBtn("重新生成") {
                    model.regenerateAssistant(after: message, projectId: window.projectId)
                }
                actionBtn("预览") { model.previewMessage(content) }
                if model.canTransfer(projectId: window.projectId) {
                    actionBtn("转任务") {
                        model.openTransfer(fromAssistantContent: content, projectId: window.projectId)
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.top, 2)
    }

    private func actionBtn(_ title: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.faint)
        }
        .buttonStyle(.plain)
    }
}

struct MessagePreviewSheet: View {
    @EnvironmentObject var model: AppModel
    let markdown: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("预览")
                    .font(.system(size: 16, weight: .semibold))
                Spacer()
                Button("复制") { model.copyMessage(markdown) }
                Button("关闭") { model.previewMarkdown = nil }
                    .keyboardShortcut(.cancelAction)
            }
            ScrollView {
                MarkdownText(source: markdown)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(20)
        .frame(minWidth: 480, idealWidth: 560, minHeight: 360, idealHeight: 480)
    }
}

// MARK: - Flow rail（跟当前对话绑定）

struct FlowRail: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState

    /// OpenCode 式：右栏跟本窗 session/thread，不跟全局 selectedThreadId
    private var paneThreadId: String? { window.threadId }

    private var snap: FlowThreadSnapshot? {
        // 订阅 threadRevision，后台写 threadFlow 时刷新
        if let tid = paneThreadId {
            _ = model.threadRevision[tid]
        }
        return model.flowSnapshot(for: paneThreadId)
    }

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
                    Text(paneThreadId == nil
                         ? "先选左侧对话"
                         : "转任务后显示流程")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            .padding(.horizontal, 14)
            .padding(.top, 4)
            .padding(.bottom, 8)

            // 仅当本对话有多个转任务时才出现切换（不再甩全项目 smoke 列表）
            if (snap?.recentEpics ?? model.recentEpics).count > 1 {
                Menu {
                    ForEach(snap?.recentEpics ?? model.recentEpics) { epic in
                        Button {
                            Task { await model.selectEpic(epic.epic_id, projectId: window.projectId) }
                        } label: {
                            HStack {
                                Text(epic.title ?? epic.epic_id)
                                if epic.epic_id == (snap?.epicId ?? model.currentEpicId) {
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

            if let hint = snap?.fanoutHint ?? (model.selectedThreadId == paneThreadId ? model.flowFanoutHint : nil) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(hint)
                        .font(.system(size: 11.5))
                        .foregroundStyle(CCCTheme.nodeFail)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 10) {
                        Button("开运维") {
                            window.destination = .ops
                            model.selectDestination(.ops, projectId: window.projectId)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(CCCTheme.accent)
                        .controlSize(.small)
                        Button("忽略") {
                            model.clearFanoutHint(projectId: window.projectId)
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
                epic: snap?.epic ?? (model.selectedThreadId == paneThreadId ? model.flowEpic : nil),
                epicId: snap?.epicId ?? (model.selectedThreadId == paneThreadId ? model.currentEpicId : nil),
                works: snap?.works ?? (model.selectedThreadId == paneThreadId ? model.flowWorks : []),
                headline: snap?.headline
                    ?? (model.selectedThreadId == paneThreadId ? model.flowHeadline : ""),
                emptyMessage: snap?.emptyMessage
                    ?? (model.selectedThreadId == paneThreadId
                        ? model.flowEmptyMessage
                        : "编排空闲·等定稿下达（与对话故障无关）"),
                splitGeneration: model.flowSplitGeneration,
                onOpenOps: {
                    window.destination = .ops
                    model.selectDestination(.ops, projectId: window.projectId)
                },
                onSelectNode: { model.openNodeDetail(id: $0, projectId: window.projectId) }
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
                if detail.kind == "work",
                   (snap?.works ?? model.flowWorks).contains(where: { $0.workId == detail.id && $0.isFailed }) {
                    Button("在运维中查看") {
                        model.dismissNodeDetail()
                        window.destination = .ops
                        model.selectDestination(.ops, projectId: window.projectId)
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
        let epics = snap?.recentEpics ?? model.recentEpics
        let eid = snap?.epicId ?? (model.selectedThreadId == paneThreadId ? model.currentEpicId : nil)
        if let cur = epics.first(where: { $0.epic_id == eid }) {
            return cur.title ?? cur.epic_id
        }
        return snap?.epic?.title ?? eid
    }
}

// MARK: - Sheets

struct TransferSheet: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) private var dismiss
    let threadId: String

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("转任务")
                .font(.system(size: 20, weight: .semibold))
                .tracking(-0.4)
            Text("确认门禁字段后写入待办；右侧展开编排。")
                .font(CCCTheme.callout)
                .foregroundStyle(CCCTheme.faint)

            Form {
                TextField("标题", text: model.bindingTransferField(threadId, \.title))
                TextField("目标", text: model.bindingTransferField(threadId, \.goal), axis: .vertical)
                    .lineLimit(3...6)
                TextField("验收（每行一条）", text: model.bindingTransferField(threadId, \.acceptance), axis: .vertical)
                    .lineLimit(3...8)
                TextField("产线", text: model.bindingTransferField(threadId, \.pipeline))
                Picker("可行性", selection: model.bindingTransferField(threadId, \.feasibility)) {
                    Text("可执行").tag("ok")
                    Text("阻塞").tag("blocked")
                }
                if model.transferForm(for: threadId).feasibility == "blocked" {
                    TextField("阻塞原因", text: model.bindingTransferField(threadId, \.feasibilityReason), axis: .vertical)
                        .lineLimit(2...4)
                }
                Picker("执行面", selection: model.bindingTransferField(threadId, \.executor)) {
                    Text("写码").tag("opencode")
                    Text("脚本").tag("python")
                    Text("ollama").tag("ollama")
                    Text("cli").tag("cli")
                    Text("auto").tag("auto")
                }
                TextField("方案正文（可选）", text: model.bindingTransferField(threadId, \.planMd), axis: .vertical)
                    .lineLimit(4...10)
            }
            .formStyle(.grouped)

            if let err = model.transferForm(for: threadId).error {
                Text(err)
                    .font(CCCTheme.callout)
                    .foregroundStyle(CCCTheme.nodeFail)
            }

            HStack {
                Button("取消") {
                    model.dismissTransferSheet(threadId: threadId)
                    dismiss()
                }
                    .foregroundStyle(CCCTheme.secondary)
                Spacer()
                Button("重新预填") { model.prefillTransferFromChat(threadId: threadId) }
                    .foregroundStyle(CCCTheme.secondary)
                Button("确认") { Task { await model.submitTransfer(threadId: threadId) } }
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
            TextField("CCC 仓根 (拉起 sidecar)", text: $model.cccHomePath)
            TextField(
                "当前项目本机路径",
                text: Binding(
                    get: { model.selectedProjectLocalPath },
                    set: { model.selectedProjectLocalPath = $0 }
                )
            )
            TextField("全局工作区 fallback", text: $model.localWorkspacePath)
            Text("对话只走本机 Agent（:7788）；失败显示「本机 Agent 未就绪」，不回退 Hub。转任务/右栏走 Hub。")
                .font(.caption)
                .foregroundStyle(.secondary)
            TextField("用户", text: $model.authUser)
            SecureField("密码", text: $model.authPass)
            Button("重新连接") { Task { await model.reconnect() } }
        }
        .padding(20)
        .frame(width: 460, height: 340)
    }
}
