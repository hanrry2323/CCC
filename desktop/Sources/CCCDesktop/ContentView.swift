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
        .sheet(isPresented: Binding(
            get: { model.previewMarkdown != nil },
            set: { if !$0 { model.previewMarkdown = nil } }
        )) {
            MessagePreviewSheet(markdown: model.previewMarkdown ?? "")
                .environmentObject(model)
        }
        .animation(.easeOut(duration: 0.18), value: model.toast)
        // 纯文字嵌进顶栏右侧（无 Toolbar 胶囊、不加第二排）
        .background(TitlebarUsageAccessory(model: model).frame(width: 0, height: 0))
        .toolbarBackground(CCCTheme.sidebar, for: .windowToolbar)
        .toolbarBackground(.visible, for: .windowToolbar)
        .toolbarColorScheme(.light, for: .windowToolbar)
    }
}

// MARK: - Sidebar

struct CodexSidebar: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                SoftRow(title: "重置对话", icon: "arrow.counterclockwise", prominent: true) {
                    Task { await model.resetConversation() }
                }
                .disabled(!model.connected)
                .opacity(model.connected ? 1 : 0.4)
                .padding(.bottom, 6)

                SoftRow(title: "对话", icon: "bubble.left.and.bubble.right", selected: model.destination == .chat) {
                    model.selectDestination(.chat)
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
                        isSelected: project.id == model.selectedProjectId
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
        // 必须把 ChatState 交给子视图 @ObservedObject，嵌套 OO 否则流式不刷新
        CodexChatPaneBody(chat: model.chat)
            .environmentObject(model)
    }
}

struct CodexChatPaneBody: View {
    @EnvironmentObject var model: AppModel
    @ObservedObject var chat: ChatState
    /// 草稿必须本地持有：右栏 SSE 刷新 AppModel 时不能重绘冲掉键盘
    @State private var composerText: String = ""
    @State private var lastScrollTargetId: String = ""
    @FocusState private var composerFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            statusBar

            if !model.canChat {
                offlineCenter
            } else {
                messageArea
                if model.pendingTransferDraft != nil {
                    transferConfirmBar
                }
                composerDock
            }
        }
        .background(CCCTheme.chatBg)
        .onAppear {
            NSApp.activate(ignoringOtherApps: true)
            composerFocused = true
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
                    Text(model.pendingTransferDraft?.previewLine ?? "")
                        .font(.system(size: 11.5))
                        .foregroundStyle(CCCTheme.secondary)
                        .lineLimit(2)
                    if let d = model.pendingTransferDraft {
                        Text("产线 \(d.pipeline) · 验收 \(d.acceptanceLines.count) 条")
                            .font(.system(size: 10.5))
                            .foregroundStyle(CCCTheme.faint)
                    }
                }
                Spacer(minLength: 0)
                Button("展开编辑") { model.openTransferSheet() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.secondary)
                Button("忽略") { model.dismissPendingTransfer() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
                Button("确认转任务") { model.confirmPendingTransfer() }
                    .buttonStyle(.borderedProminent)
                    .tint(CCCTheme.accent)
                    .controlSize(.small)
                    .disabled(
                        model.busy
                            || !model.canTransfer
                            || !(model.pendingTransferDraft?.isGateReady ?? false)
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
            Text(model.statusText)
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
                .disabled(chat.messages.isEmpty)
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
                        if chat.messages.isEmpty {
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
                        ForEach(chat.messages) { msg in
                            CodexMessageRow(message: msg)
                                // 固定 id：toolSteps 变化靠 Hashable diff 刷新轨，勿重建整行 Markdown
                                .id("\(model.selectedThreadId ?? "")-\(msg.id)")
                                .environmentObject(model)
                                .contextMenu {
                                    Button("复制") { model.copyMessage(msg.content) }
                                    if msg.role == "user" {
                                        Button("编辑") { model.editUserMessage(msg) }
                                    }
                                    if msg.role == "assistant", !msg.isStreaming {
                                        Button("重新生成") { model.regenerateAssistant(after: msg) }
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
                    .id(model.selectedThreadId ?? "none") // 切会话强制重建，防工具轨串台
                    .frame(maxWidth: CCCTheme.chatMaxWidth)
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 28)
                    .padding(.top, 8)
                }
                .onChange(of: chat.messages.count) { _ in scroll(proxy) }
                .onChange(of: chat.messages.last?.content) { _ in scroll(proxy) }
                .onChange(of: chat.messages.last?.toolSteps.count) { _ in scroll(proxy) }
                .onChange(of: model.selectedThreadId) { _ in lastScrollTargetId = "" }
            }
        }
    }

    private func scroll(_ proxy: ScrollViewProxy) {
        guard let last = chat.messages.last else { return }
        let lastId = "\(model.selectedThreadId ?? "")-\(last.id)"
        // 同目标跳过，避免每个 delta 反复 withAnimation + scrollTo
        guard lastId != lastScrollTargetId || chat.messages.last?.isStreaming == true else { return }
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
                    model.openTransferSheet()
                } label: {
                    Text("转任务")
                        .font(.system(size: 11.5, weight: .medium))
                        .foregroundStyle(
                            model.canTransfer
                                ? CCCTheme.accent
                                : CCCTheme.faint
                        )
                }
                .buttonStyle(.plain)
                .disabled(!model.canTransfer)
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
                    isEnabled: model.canChat,
                    onSubmit: { sendFromComposer() }
                )
                .frame(minHeight: 22, idealHeight: 22, maxHeight: 72)
                .padding(.leading, 8)
                .padding(.vertical, 6)

                // 固定同一 Button 身份，避免 if/else 换控件触发 Composer 整行重布局打断 IME
                Button {
                    if showStopInsteadOfSend {
                        model.cancelChat()
                    } else {
                        sendFromComposer()
                    }
                } label: {
                    Image(systemName: showStopInsteadOfSend
                          ? "stop.fill"
                          : (model.currentThreadStreaming ? "arrow.up.circle.fill" : "arrow.up"))
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
                      : (model.currentThreadStreaming ? "停止当前并发送" : "发送"))
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
        .disabled(!model.canChat)
    }

    private var canSend: Bool {
        model.canChat && !composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private var showStopInsteadOfSend: Bool {
        model.currentThreadStreaming
            && composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
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
    let role: String
    let content: String
    let message: ChatMessage

    var body: some View {
        HStack(spacing: 10) {
            actionBtn("复制") { model.copyMessage(content) }
            if role == "user" {
                actionBtn("编辑") { model.editUserMessage(message) }
            } else {
                actionBtn("重新生成") { model.regenerateAssistant(after: message) }
                actionBtn("预览") { model.previewMessage(content) }
                if model.canTransfer {
                    actionBtn("转任务") { model.openTransfer(fromAssistantContent: content) }
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
            .padding(.top, 4)
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
                splitGeneration: model.flowSplitGeneration,
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
