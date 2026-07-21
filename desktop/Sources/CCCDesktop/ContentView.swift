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
        // 切项目/会话时禁止整窗隐式动画（侧栏展开 + 中栏消息替换会叠成「闪一下」）
        .animation(nil, value: window.projectId)
        .animation(nil, value: window.threadId)
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
        .sheet(isPresented: $model.isManualEpicPresented) {
            ManualEpicSheet()
                .environmentObject(model)
        }
        .sheet(isPresented: $model.isTemplatePickerPresented) {
            TemplatePickerSheet()
                .environmentObject(model)
        }
        .animation(.easeOut(duration: 0.18), value: model.toast)
        .alert("重命名会话", isPresented: Binding(
            get: { model.renameThreadId != nil },
            set: { if !$0 { model.renameThreadId = nil } }
        )) {
            TextField("标题", text: $model.renameDraft)
            Button("保存") {
                if let id = model.renameThreadId {
                    model.renameThread(threadId: id, title: model.renameDraft)
                }
                model.renameThreadId = nil
            }
            Button("取消", role: .cancel) { model.renameThreadId = nil }
        } message: {
            Text("为当前会话起一个好认的名字。")
        }
        .sheet(isPresented: $model.isHelpPresented) {
            DesktopHelpSheet()
                .environmentObject(model)
        }
        .onChange(of: model.commandNewThreadTick) { _ in
            window.destination = .chat
            guard let pid = window.projectId ?? model.selectedProjectId else {
                model.showToast("请先选择项目")
                return
            }
            Task {
                let tid = await model.createNewThread(projectId: pid)
                window.projectId = pid
                window.threadId = tid
            }
        }
        .onChange(of: model.commandTransferTick) { _ in
            window.destination = .chat
            model.openTransferSheet(projectId: window.projectId, threadId: window.threadId)
        }
        .onChange(of: model.commandDestination) { dest in
            guard let dest else { return }
            window.destination = dest
            model.selectDestination(dest, projectId: window.projectId)
            model.commandDestination = nil
        }
        // 纯文字嵌进顶栏右侧；依赖 model.agentUsageTick 触发 updateNSView
        .background(
            TitlebarUsageAccessory(model: model)
                .frame(width: 0, height: 0)
                .id(model.agentUsageTick)
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
    @State private var confirmReset = false
    @FocusState private var searchFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                SoftRow(title: "重置对话", icon: "arrow.counterclockwise", prominent: true) {
                    confirmReset = true
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

            if !model.connected && model.projects.isEmpty {
                offlineBlock
            } else {
                projectCardList
            }

            Spacer(minLength: 0)

            divider

            // 搜索：可点结果跳转
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.faint)
                        .accessibilityHidden(true)
                    TextField("搜索消息…", text: $model.searchQuery)
                        .textFieldStyle(.plain)
                        .font(CCCTheme.caption)
                        .focused($searchFocused)
                        .accessibilityLabel("搜索消息")
                        .onSubmit {
                            model.performSearch(query: model.searchQuery)
                        }
                        .onChange(of: model.searchQuery) { q in
                            if q.trimmingCharacters(in: .whitespacesAndNewlines).count >= 2 {
                                model.performSearch(query: q)
                            } else if q.isEmpty {
                                model.clearSearch()
                            }
                        }
                    if !model.searchQuery.isEmpty {
                        Button {
                            model.clearSearch()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 10))
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(CCCTheme.faint)
                        .accessibilityLabel("清除搜索")
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(CCCTheme.chatBg)
                .cornerRadius(6)
                .padding(.horizontal, 8)
                .padding(.top, 6)

                if !model.searchResults.isEmpty {
                    Text("找到 \(model.searchResults.count) 条 · 点击打开")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                        .padding(.horizontal, 14)
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 2) {
                            ForEach(model.searchResults.prefix(20)) { result in
                                Button {
                                    Task {
                                        let pid = LocalSessionStore.projectId(fromThreadId: result.threadId)
                                        window.destination = .chat
                                        window.projectId = pid
                                        window.threadId = result.threadId
                                        await model.openSearchResult(result)
                                    }
                                } label: {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(result.title ?? String(result.threadId.suffix(12)))
                                            .font(.system(size: 11, weight: .medium))
                                            .foregroundStyle(CCCTheme.ink)
                                            .lineLimit(1)
                                        Text(result.content)
                                            .font(.system(size: 10.5))
                                            .foregroundStyle(CCCTheme.faint)
                                            .lineLimit(2)
                                    }
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 6)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .background(
                                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                                            .fill(CCCTheme.hover)
                                    )
                                }
                                .buttonStyle(.plain)
                                .accessibilityLabel("搜索结果：\(result.title ?? "会话")，\(result.content)")
                            }
                        }
                        .padding(.horizontal, 8)
                    }
                    .frame(maxHeight: 160)
                }
            }

            divider

            VStack(spacing: 1) {
                SoftRow(title: "用法", icon: "questionmark.circle") {
                    model.isHelpPresented = true
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
        .confirmationDialog(
            "重置当前项目的对话？",
            isPresented: $confirmReset,
            titleVisibility: .visible
        ) {
            Button("重置对话", role: .destructive) {
                Task { await model.resetConversation(projectId: window.projectId) }
            }
            Button("取消", role: .cancel) {}
        } message: {
            Text("本机会话记录会被清空，无法撤销。编排任务不受影响。")
        }
        .onChange(of: model.searchFocusTick) { _ in
            window.destination = .chat
            searchFocused = true
        }
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
                    if project.id == window.projectId {
                        threadList(for: project.id)
                    }
                }
            }
            .padding(.horizontal, 8)
            .padding(.top, 8)
            .padding(.bottom, 16)
        }
        // 切项目时禁止侧栏展开/收起动画，避免整窗闪一下
        .animation(nil, value: window.projectId)
    }

    @ViewBuilder
    private func threadList(for projectId: String) -> some View {
        let threads = model.threads.filter { LocalSessionStore.projectId(fromThreadId: $0.thread_id) == projectId }
        if !threads.isEmpty {
            VStack(alignment: .leading, spacing: 2) {
                ForEach(threads.prefix(10)) { thread in
                    SidebarThreadRow(
                        thread: thread,
                        projectId: projectId,
                        isSelected: thread.thread_id == window.threadId
                    )
                }
            }
            .padding(.bottom, 6)
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

/// 侧栏会话行：点选有底色 + 轻脉冲，避免「不知道点没点上」
private struct SidebarThreadRow: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    let thread: DesktopThread
    let projectId: String
    let isSelected: Bool

    @State private var hovering = false
    @State private var pressFlash = false

    private var streaming: Bool { model.isThreadStreaming(thread.thread_id) }
    private var unread: Bool { model.isThreadUnread(thread.thread_id) }

    var body: some View {
        Button(action: select) {
            HStack(spacing: 7) {
                Image(systemName: isSelected ? "bubble.left.fill" : "bubble.left")
                    .font(.system(size: 10, weight: isSelected ? .medium : .regular))
                    .foregroundStyle(isSelected ? CCCTheme.accent : CCCTheme.faint.opacity(0.75))
                    .frame(width: 12)
                    .scaleEffect(pressFlash ? 1.15 : 1)
                Text(thread.title ?? thread.thread_id.suffix(12).description)
                    .font(.system(size: 12, weight: isSelected ? .regular : .light))
                    .foregroundStyle(isSelected ? CCCTheme.ink : CCCTheme.secondary.opacity(0.9))
                    .lineLimit(1)
                Spacer(minLength: 0)
                if streaming {
                    ProgressView()
                        .controlSize(.mini)
                } else if unread {
                    Circle()
                        .fill(CCCTheme.unread)
                        .frame(width: 7, height: 7)
                        .accessibilityLabel("未读")
                }
            }
            .padding(.leading, 28)
            .padding(.trailing, 8)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(rowFill)
            )
            .overlay(alignment: .leading) {
                Capsule()
                    .fill(CCCTheme.accent)
                    .frame(width: 2.5, height: isSelected || pressFlash ? 16 : 0)
                    .opacity(isSelected || pressFlash ? 1 : 0)
                    .padding(.leading, 18)
                    .animation(.spring(response: 0.28, dampingFraction: 0.78), value: isSelected)
                    .animation(.easeOut(duration: 0.2), value: pressFlash)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .scaleEffect(pressFlash ? 0.985 : 1)
        .animation(.spring(response: 0.22, dampingFraction: 0.72), value: pressFlash)
        .onHover { hovering = $0 }
        .contextMenu {
            Button("重命名") {
                model.renameThreadId = thread.thread_id
                model.renameDraft = thread.title ?? ""
            }
            Button("存档", role: .destructive) {
                let tid = thread.thread_id
                Task {
                    await model.archiveThread(threadId: tid)
                    if window.threadId == tid {
                        window.threadId = model.selectedThreadId
                            ?? model.threads.first?.thread_id
                    }
                }
            }
            Button("分叉") {
                Task {
                    if let nid = await model.forkThread(threadId: thread.thread_id) {
                        window.threadId = nid
                    }
                }
            }
        }
        .accessibilityLabel(
            "\(thread.title ?? "会话")\(isSelected ? "，已选中" : "")\(streaming ? "，生成中" : "")\(unread ? "，未读" : "")"
        )
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    private var rowFill: Color {
        if pressFlash { return CCCTheme.accent.opacity(0.18) }
        if isSelected { return CCCTheme.selected }
        if hovering { return CCCTheme.hover }
        return .clear
    }

    private func select() {
        withAnimation(.easeOut(duration: 0.12)) {
            pressFlash = true
        }
        window.projectId = projectId
        window.threadId = thread.thread_id
        window.destination = .chat
        model.selectedThreadId = thread.thread_id
        model.selectedProjectId = projectId
        model.clearThreadUnread(thread.thread_id)
        Task {
            await model.openThread(thread.thread_id)
            try? await Task.sleep(nanoseconds: 220_000_000)
            withAnimation(.easeOut(duration: 0.25)) {
                pressFlash = false
            }
        }
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
    @Environment(\.scenePhase) private var scenePhase
    /// 草稿必须本地持有：右栏 SSE 刷新 AppModel 时不能重绘冲掉键盘
    @State private var composerText: String = ""
    @State private var lastScrollTargetId: String = ""
    /// 切窗/切会话后下一次滚动必须瞬移到末轮，禁止 easeOut 扫历史（长对话「刷一遍」）
    @State private var needsInstantBottomPin: Bool = true
    /// 流式跟滚节流桶（字数/120 + toolSteps）
    @State private var lastStreamScrollBucket: Int = -1
    /// 触发 ScrollViewReader 内再钉一次（scene 激活时 onAppear 不一定重跑）
    @State private var bottomPinTick: UInt64 = 0
    /// 切会话过渡：先遮罩 + 圆圈，再缓慢露出内容（掩盖瞬时闪屏）
    @State private var paneContentOpacity: Double = 1
    @State private var showPaneSwitchSpinner = false
    @State private var paneSwitchGeneration: UInt64 = 0
    @FocusState private var composerFocused: Bool

    /// 本窗唯一项目焦点；禁止回落全局 selected（否则他窗切项会拖走本窗历史）
    private var paneProjectId: String? {
        window.projectId
    }

    private var paneThreadId: String? {
        window.threadId
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

    /// 投递态前景色：failed 醒目；queued/delivering 中性；accepted 成功感；delivered 不伪装受理
    private func deliveryPhaseForeground(_ phase: TransferDeliveryPhase) -> Color {
        switch phase {
        case .failed: return CCCTheme.nodeFail
        case .accepted: return CCCTheme.nodeDone
        case .queued, .delivering: return CCCTheme.secondary
        case .delivered, .draft: return CCCTheme.secondary
        }
    }

    private func deliveryPhaseBackground(_ phase: TransferDeliveryPhase) -> Color {
        switch phase {
        case .failed: return CCCTheme.nodeFail.opacity(0.12)
        case .accepted: return CCCTheme.nodeDone.opacity(0.14)
        case .queued, .delivering: return CCCTheme.secondary.opacity(0.12)
        case .delivered, .draft: return CCCTheme.secondary.opacity(0.12)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            if !model.dismissedFirstRunTip {
                firstRunTip
            }
            statusBar

            if !model.canChat {
                offlineCenter
            } else {
                ZStack {
                    messageArea
                        .opacity(paneContentOpacity)
                    if showPaneSwitchSpinner {
                        VStack(spacing: 10) {
                            ProgressView()
                                .controlSize(.regular)
                                .scaleEffect(1.15)
                            Text("加载对话…")
                                .font(.system(size: 12, weight: .light))
                                .foregroundStyle(CCCTheme.faint)
                        }
                        .transition(.opacity)
                        .allowsHitTesting(false)
                    }
                }
                if model.transferDraft(for: paneThreadId) != nil {
                    transferConfirmBar
                        .opacity(paneContentOpacity)
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
            if let pid {
                model.ensureThreadHydrated(projectId: pid)
            }
        }
        .onChange(of: window.threadId) { _ in
            // 消息源只跟 thread；以 thread 切换驱动过渡，避免与 project 双触发叠闪
            beginPaneSwitchTransition()
        }
        .onChange(of: scenePhase) { phase in
            // A→B→A：窗体未必销毁，onAppear 不跑；激活时仍要瞬移最新，禁止扫历史
            if phase == .active {
                pinBottomOnNextScroll()
                bottomPinTick &+= 1
            }
        }
    }

    private var firstRunTip: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "lightbulb")
                .font(.system(size: 12))
                .foregroundStyle(CCCTheme.accent)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 4) {
                Text("三步走完主路径")
                    .font(.system(size: 12, weight: .medium))
                Text("① 说明目标与验收  →  ② 点「定稿」  →  ③ 确认转任务，右侧看编排。侧栏「用法」可随时打开。")
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            Button("知道了") { model.dismissFirstRunTip() }
                .buttonStyle(.plain)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(CCCTheme.accent)
                .accessibilityLabel("关闭首启提示")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(CCCTheme.accent.opacity(0.08))
        .accessibilityElement(children: .combine)
    }

    private func pinBottomOnNextScroll() {
        lastScrollTargetId = ""
        lastStreamScrollBucket = -1
        needsInstantBottomPin = true
    }

    /// 切项目/会话：遮罩下一帧内钉到末条 .top，再无动画露出（无 320ms 转圈、无漂移）
    private func beginPaneSwitchTransition() {
        paneSwitchGeneration &+= 1
        let gen = paneSwitchGeneration
        var hide = Transaction()
        hide.disablesAnimations = true
        withTransaction(hide) {
            paneContentOpacity = 0
            showPaneSwitchSpinner = false
            pinBottomOnNextScroll()
            if let last = displayMessages.last {
                lastScrollTargetId = "\(paneThreadId ?? "")-\(last.id)"
            }
        }
        Task { @MainActor in
            await Task.yield()
            guard gen == paneSwitchGeneration else { return }
            bottomPinTick &+= 1
            await Task.yield()
            guard gen == paneSwitchGeneration else { return }
            var reveal = Transaction()
            reveal.disablesAnimations = true
            withTransaction(reveal) {
                paneContentOpacity = 1
            }
        }
    }

    /// 定稿 JSON 就绪后的一键转任务条
    private var transferConfirmBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("确认转任务")
                        .font(.system(size: 12, weight: .medium))
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
                Button("展开编辑") {
                    model.openTransferSheet(projectId: window.projectId, threadId: window.threadId)
                }
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
            if model.hubSyncing {
                ProgressView()
                    .controlSize(.mini)
                Text("Hub 同步")
                    .font(.system(size: 10))
                    .foregroundStyle(CCCTheme.faint)
            }
            if let phase = model.transferDelivery(for: paneThreadId),
               phase != .draft {
                Text(phase.label)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(deliveryPhaseForeground(phase))
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(
                        Capsule().fill(deliveryPhaseBackground(phase))
                    )
                    .accessibilityLabel("投递态 \(phase.label)")
                    .accessibilityValue(phase.rawValue)
            }
            if model.agentWarming {
                Text("预热中")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(CCCTheme.secondary)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(CCCTheme.hover, in: Capsule())
                    .accessibilityLabel("本机 Agent 预热中")
            }
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
            if let fail = model.lastTurnFailure,
               fail.threadId == paneThreadId,
               !paneStreaming {
                Button("重试") { model.retryLastFailedTurn(threadId: paneThreadId) }
                    .buttonStyle(.plain)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(CCCTheme.accent)
                    .help(fail.message)
                    .accessibilityLabel("重试本条失败对话")
                Button("清槽") { model.healThreadSlot(threadId: paneThreadId) }
                    .buttonStyle(.plain)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(CCCTheme.secondary)
                    .help("回收本会话 Agent live 槽后重发")
                    .accessibilityLabel("清理本会话 Agent 槽")
            }
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
            if !displayMessages.isEmpty {
                let tok = model.sessionTokenCount(for: paneThreadId ?? "")
                if tok > 0 {
                    HStack(spacing: 2) {
                        Image(systemName: "bolt")
                            .font(.system(size: 8))
                        Text("本会话 \(tok) tok")
                            .font(.system(size: 10))
                    }
                    .foregroundStyle(CCCTheme.faint)
                    .help("本会话 token（sidecar cost）；顶栏「今日/5s」是 Agent 调用次数")
                }
            }
            Button("上下文") { model.isContextPanelPresented = true }
                .buttonStyle(.plain)
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.faint)
                .disabled((paneThreadId ?? "").isEmpty)
            Menu("导出") {
                Button("Markdown 到剪贴板") {
                    model.exportThreadToPasteboard(threadId: paneThreadId)
                }
                Button("会话 JSON 到剪贴板") {
                    model.exportThreadJSONToPasteboard(threadId: paneThreadId)
                }
            }
            .buttonStyle(.plain)
            .font(.system(size: 11))
            .foregroundStyle(CCCTheme.faint)
            .disabled(displayMessages.isEmpty)
        }
        .padding(.horizontal, 24)
        .padding(.top, 8)
        .padding(.bottom, 4)
        .sheet(isPresented: $model.isContextPanelPresented) {
            ContextPanelSheet(threadId: paneThreadId ?? "")
                .environmentObject(model)
                .environmentObject(window)
        }
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
                    LazyVStack(alignment: .leading, spacing: CCCTheme.messageStackSpacing) {
                        if displayMessages.isEmpty {
                            VStack(alignment: .leading, spacing: 14) {
                                Spacer().frame(height: 48)
                                Text("有什么可以帮忙的？")
                                    .font(CCCTheme.title)
                                    .foregroundStyle(CCCTheme.ink)
                                    .frame(maxWidth: .infinity, alignment: .center)
                                Text("按主路径推进，不必选角色：")
                                    .font(.system(size: 13))
                                    .foregroundStyle(CCCTheme.faint)
                                    .frame(maxWidth: .infinity, alignment: .center)
                                VStack(alignment: .leading, spacing: 10) {
                                    emptyStep(num: "1", title: "聊透目标", detail: "说清要解决什么、怎样算验收成功")
                                    emptyStep(num: "2", title: "点「定稿」", detail: "快捷条生成可转任务的契约包")
                                    emptyStep(num: "3", title: "确认转任务", detail: "写入待办后，右侧展开本对话编排")
                                }
                                .padding(16)
                                .frame(maxWidth: 420)
                                .frame(maxWidth: .infinity)
                                .background(
                                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                                        .fill(CCCTheme.surface)
                                )
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                                        .stroke(CCCTheme.border, lineWidth: 1)
                                )
                                Button("打开用法说明") { model.isHelpPresented = true }
                                    .buttonStyle(.plain)
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundStyle(CCCTheme.accent)
                                    .frame(maxWidth: .infinity)
                                    .padding(.top, 4)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.bottom, 24)
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel("空对话引导：聊透目标，定稿，确认转任务")
                        }
                        ForEach(displayMessages) { msg in
                            CodexMessageRow(message: msg)
                                // 固定 id：toolSteps 变化靠 Hashable diff 刷新轨，勿重建整行 Markdown
                                .id("\(paneThreadId ?? "")-\(msg.id)")
                                .environmentObject(model)
                                .contextMenu {
                                    Button("复制") { model.copyMessage(msg.content) }
                                    if msg.role == "user" {
                                        Button("编辑") {
                                            model.editUserMessage(
                                                msg,
                                                projectId: paneProjectId,
                                                threadId: paneThreadId
                                            )
                                        }
                                    }
                                    if msg.role == "assistant", !msg.isStreaming {
                                        Button("重新生成") {
                                            model.regenerateAssistant(
                                                after: msg,
                                                projectId: paneProjectId,
                                                threadId: paneThreadId
                                            )
                                        }
                                        Button("预览") { model.previewMessage(msg.content) }
                                        if model.canTransfer {
                                            Button("转任务") {
                                                model.openTransfer(
                                                    fromAssistantContent: msg.content,
                                                    projectId: paneProjectId,
                                                    threadId: paneThreadId
                                                )
                                            }
                                        }
                                    }
                                }
                        }
                        // tip：布局锚点；滚动禁止 scrollTo(tip, .bottom)（会把空槽钉满视口）
                        Color.clear
                            .frame(height: 1)
                            .id(bottomAnchorId)
                        // Cursor 式底部空槽：最新内容偏上，下方留给流式回复
                        Spacer().frame(height: max(geometry.size.height * 0.55, 220))
                    }
                    .frame(maxWidth: CCCTheme.chatMaxWidth)
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 28)
                    .padding(.top, 8)
                }
                .onAppear {
                    // 窗体重入 / 首次进入：瞬移最新，勿从上往下刷
                    pinBottomOnNextScroll()
                    scroll(proxy)
                }
                .onChange(of: bottomPinTick) { _ in scroll(proxy) }
                .onChange(of: displayMessages.count) { _ in scroll(proxy) }
                .onChange(of: displayMessages.last?.content) { _ in scroll(proxy) }
                .onChange(of: displayMessages.last?.toolSteps.count) { _ in scroll(proxy) }
                // 仅消息修订触发滚动；勿绑 flow 修订（已从 threadRevision 拆出）
                .onChange(of: model.threadRevision[paneThreadId ?? ""]) { _ in scroll(proxy) }
                .onChange(of: model.pendingScrollMessageId) { mid in
                    guard let mid,
                          let msg = displayMessages.first(where: { $0.id.uuidString.caseInsensitiveCompare(mid) == .orderedSame })
                    else { return }
                    let id = "\(paneThreadId ?? "")-\(msg.id)"
                    withAnimation(.easeOut(duration: 0.2)) {
                        proxy.scrollTo(id, anchor: .center)
                    }
                    model.pendingScrollMessageId = nil
                }
                // 禁止订阅全局 selectedThreadId：他窗切项会清掉本窗滚动钉，导致切回时动画扫历史
            }
        }
    }

    private func emptyStep(num: String, title: String, detail: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text(num)
                .font(.system(size: 12, weight: .bold, design: .rounded))
                .foregroundStyle(Color.white)
                .frame(width: 22, height: 22)
                .background(Circle().fill(CCCTheme.accent))
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(CCCTheme.ink)
                Text(detail)
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.secondary)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("第\(num)步：\(title)。\(detail)")
    }

    private var bottomAnchorId: String {
        "\(paneThreadId ?? "none")-bottom"
    }

    private func messageRowId(_ msg: ChatMessage) -> String {
        "\(paneThreadId ?? "")-\(msg.id)"
    }

    /// 本轮 user：last 是 user，或 last 是 assistant 时取其前一条 user
    private func currentTurnUserMessage() -> ChatMessage? {
        let msgs = displayMessages
        guard let last = msgs.last else { return nil }
        if last.role == "user" { return last }
        guard let idx = msgs.indices.last, idx > 0 else { return nil }
        for i in stride(from: idx - 1, through: 0, by: -1) {
            if msgs[i].role == "user" { return msgs[i] }
        }
        return nil
    }

    /// 刚发送 / 等首包：钉本轮 user 顶部，下方空槽留给回复
    private func shouldPinCurrentUserToTop(_ last: ChatMessage) -> Bool {
        if last.role == "user" { return true }
        if last.role == "assistant", last.isStreaming,
           last.content.isEmpty, last.toolSteps.isEmpty {
            return true
        }
        return false
    }

    /// Cursor 式滚动：user/末条 `.top`；流式跟消息 `.bottom`；禁止 tip+`.bottom`
    private func scroll(_ proxy: ScrollViewProxy) {
        guard let last = displayMessages.last else { return }
        let lastId = messageRowId(last)

        // 1) 切会话 / 重入：末条贴顶，下方空槽自然露出（无动画）
        if needsInstantBottomPin {
            needsInstantBottomPin = false
            lastScrollTargetId = lastId
            var t = Transaction()
            t.disablesAnimations = true
            withTransaction(t) {
                proxy.scrollTo(lastId, anchor: .top)
            }
            return
        }

        // 2) 刚发送 / 等首包：钉本轮 user 顶部
        if shouldPinCurrentUserToTop(last) {
            guard let user = currentTurnUserMessage() else { return }
            let userId = messageRowId(user)
            if userId == lastScrollTargetId { return }
            lastScrollTargetId = userId
            var t = Transaction()
            t.disablesAnimations = true
            withTransaction(t) {
                proxy.scrollTo(userId, anchor: .top)
            }
            return
        }

        // 3) assistant 流式：正文仍短或主要在跑工具 → 保持 user 在上；变长后再跟滚
        if last.isStreaming, last.role == "assistant" {
            let keepUserTop = last.content.count < 480
            if keepUserTop {
                if let user = currentTurnUserMessage() {
                    let userId = messageRowId(user)
                    if userId != lastScrollTargetId {
                        lastScrollTargetId = userId
                        var t = Transaction()
                        t.disablesAnimations = true
                        withTransaction(t) {
                            proxy.scrollTo(userId, anchor: .top)
                        }
                    }
                }
                return
            }
            // 节流：同目标时约每 120 字或 toolStep 变化才滚
            let bucket = last.content.count / 120 + last.toolSteps.count * 1_000
            if lastId == lastScrollTargetId, bucket == lastStreamScrollBucket {
                return
            }
            lastScrollTargetId = lastId
            lastStreamScrollBucket = bucket
            var t = Transaction()
            t.disablesAnimations = true
            withTransaction(t) {
                proxy.scrollTo(lastId, anchor: .bottom)
            }
            return
        }

        // 4) 非流式（历史加载完成等）：末条贴顶
        if lastId == lastScrollTargetId { return }
        lastScrollTargetId = lastId
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) {
            proxy.scrollTo(lastId, anchor: .top)
        }
    }

    /// 矮输入条；草稿用本地 @State，避免 SSE 冲焦点
    private var composerDock: some View {
        VStack(spacing: 6) {
            quickActionBar

            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Button {
                    model.openTransferSheet(projectId: window.projectId, threadId: window.threadId)
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
                .help("把定稿方案写入待办大卡；右侧展开本对话编排")
                .accessibilityLabel("转任务")
                .accessibilityHint("确认门禁后投递 epic")

                Picker("", selection: $model.preferredModel) {
                    ForEach(StreamSessionController.modelPickerOptions, id: \.id) { opt in
                        Text(opt.label).tag(opt.id)
                    }
                }
                .labelsHidden()
                .frame(width: 118)
                .help("对话模型（请求级）。现网出口均为 MiniMax 直连；逻辑名 flash/code/sonnet/haiku 映射同一上游。不改 shell / 个人 Claude。")
                .onChange(of: model.preferredModel) { newValue in
                    let name = StreamSessionController.modelDisplayName(newValue)
                    model.showToast("对话模型：\(name)")
                }

                Button {
                    model.requestEngineerMode()
                } label: {
                    Text(model.preferredToolMode == "engineer" ? "工程师" : "讨论")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(
                            model.preferredToolMode == "engineer"
                                ? CCCTheme.nodeFail
                                : CCCTheme.secondary
                        )
                }
                .buttonStyle(.plain)
                .help("讨论=只读探查；工程师=仅平台仓 ccc 可本机改文件；业务仓请定稿转任务")

                Button {
                    pickComposerAttachment()
                } label: {
                    Image(systemName: "paperclip")
                        .font(.system(size: 12))
                        .foregroundStyle(CCCTheme.secondary)
                }
                .buttonStyle(.plain)
                .help("附加本地文件路径到本条消息")

                if let hint = model.transferGateHint(projectId: window.projectId, threadId: paneThreadId) {
                    Text(hint)
                        .font(.system(size: 10.5))
                        .foregroundStyle(CCCTheme.faint)
                        .lineLimit(2)
                } else if model.transferDraft(for: paneThreadId) == nil, !displayMessages.isEmpty {
                    Text("方案成熟后点「定稿」，再确认转任务")
                        .font(.system(size: 10.5))
                        .foregroundStyle(CCCTheme.faint)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
            }
            .frame(maxWidth: CCCTheme.chatMaxWidth)
            .frame(maxWidth: .infinity)

            if !model.composerAttachments.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(model.composerAttachments) { att in
                            HStack(spacing: 4) {
                                Image(systemName: att.isImage ? "photo" : "doc")
                                    .font(.system(size: 9))
                                Text((att.path as NSString).lastPathComponent)
                                    .font(.system(size: 10))
                                    .lineLimit(1)
                                Button {
                                    model.removeComposerAttachment(id: att.id)
                                } label: {
                                    Image(systemName: "xmark.circle.fill")
                                        .font(.system(size: 10))
                                }
                                .buttonStyle(.plain)
                            }
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(CCCTheme.hover, in: Capsule())
                            .foregroundStyle(CCCTheme.secondary)
                        }
                    }
                }
                .frame(maxWidth: CCCTheme.chatMaxWidth)
                .frame(maxWidth: .infinity, alignment: .leading)
            }

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
                .accessibilityLabel("消息输入框")
                .onDrop(of: [.fileURL], isTargeted: nil) { providers in
                    handleComposerDrop(providers)
                }

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
                .accessibilityLabel(showStopInsteadOfSend ? "停止生成" : "发送消息")
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
            .confirmationDialog(
                "开启工程师模式？",
                isPresented: $model.confirmEngineerMode,
                titleVisibility: .visible
            ) {
                Button("开启（可改本机文件）", role: .destructive) {
                    model.confirmEnableEngineerMode()
                }
                Button("取消", role: .cancel) {}
            } message: {
                Text("默认讨论模式只读探查。工程师模式仅允许在平台仓 ccc 修改本机文件；业务仓请定稿转任务。")
            }
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

    private func pickComposerAttachment() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.begin { resp in
            guard resp == .OK else { return }
            for url in panel.urls {
                model.addComposerAttachment(path: url.path)
            }
        }
    }

    private func handleComposerDrop(_ providers: [NSItemProvider]) -> Bool {
        var handled = false
        for p in providers {
            _ = p.loadObject(ofClass: URL.self) { url, _ in
                guard let url else { return }
                DispatchQueue.main.async {
                    model.addComposerAttachment(path: url.path)
                }
            }
            handled = true
        }
        return handled
    }

    private var quickActionBar: some View {
        VStack(alignment: .leading, spacing: 6) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    quickChip(
                        "对齐基线",
                        help: "像 Cursor 一样核实 git/文档后，白话说明定位、风险与最佳下一步"
                    ) {
                        Task {
                            await model.alignBaseline(
                                projectId: paneProjectId,
                                threadId: paneThreadId
                            )
                        }
                    }
                    quickChip(
                        "刷新看板",
                        help: "经 Hub 只读透镜 live 读权威仓在飞任务（覆盖过期记忆）"
                    ) {
                        model.applyQuickPrompt(
                            QuickPrompts.refreshBoard,
                            uiLabel: "刷新看板",
                            projectId: paneProjectId,
                            threadId: paneThreadId
                        )
                    }
                    quickChip(
                        "下一步",
                        help: "结合会话与仓库，给出最多三条带取舍的下一步（含最佳项）"
                    ) {
                        model.applyQuickPrompt(
                            QuickPrompts.nextStep,
                            uiLabel: "下一步",
                            projectId: paneProjectId,
                            threadId: paneThreadId
                        )
                    }
                    quickChip(
                        "定稿",
                        help: "核实可行性后生成 ccc-transfer 契约包，便于确认转任务"
                    ) {
                        model.applyQuickPrompt(
                            QuickPrompts.finalize,
                            uiLabel: "定稿",
                            projectId: paneProjectId,
                            threadId: paneThreadId
                        )
                    }
                    quickChip(
                        "扫风险",
                        help: "按严重度列出场景/发布/下达风险，并判断能否转任务"
                    ) {
                        model.applyQuickPrompt(
                            QuickPrompts.scanRisks,
                            uiLabel: "扫风险",
                            projectId: paneProjectId,
                            threadId: paneThreadId
                        )
                    }
                    if !model.customPrompts.isEmpty {
                        ForEach(model.customPrompts, id: \.title) { item in
                            quickChip(item.title, help: "自定义快捷提示：\(item.title)") {
                                model.applyQuickPrompt(
                                    item.prompt,
                                    uiLabel: item.title,
                                    projectId: paneProjectId,
                                    threadId: paneThreadId
                                )
                            }
                        }
                    }
                }
            }
            if let action = model.activeQuickAction, !action.isEmpty {
                HStack(spacing: 6) {
                    ProgressView()
                        .controlSize(.mini)
                    Text("正在执行：\(action)")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.accent)
                    Spacer(minLength: 0)
                }
                .accessibilityLabel("正在执行 \(action)")
            }
        }
        .frame(maxWidth: CCCTheme.chatMaxWidth)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func quickChip(_ title: String, help: String, action: @escaping () -> Void) -> some View {
        let busy = model.activeQuickAction == title
        let blocked = !model.canChat || (model.activeQuickAction != nil && !busy) || paneStreaming
        return Button {
            NSHapticFeedbackManager.defaultPerformer.perform(.generic, performanceTime: .now)
            action()
        } label: {
            HStack(spacing: 5) {
                if busy {
                    ProgressView()
                        .controlSize(.mini)
                }
                Text(title)
                    .font(.system(size: 11.5, weight: busy ? .medium : .regular))
                    .foregroundStyle(busy ? CCCTheme.accent : CCCTheme.secondary)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(
                Capsule(style: .continuous)
                    .fill(busy ? CCCTheme.accent.opacity(0.16) : CCCTheme.hover)
            )
            .overlay(
                Capsule(style: .continuous)
                    .stroke(busy ? CCCTheme.accent.opacity(0.45) : Color.clear, lineWidth: 1)
            )
            .scaleEffect(busy ? 0.98 : 1)
            .animation(.easeOut(duration: 0.12), value: busy)
        }
        .buttonStyle(.plain)
        .disabled(blocked)
        .opacity(blocked && !busy ? 0.45 : 1)
        .help(help)
        .accessibilityLabel(title)
        .accessibilityHint(help)
        .accessibilityAddTraits(busy ? .updatesFrequently : [])
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
        let atts = model.composerAttachments
        guard !text.isEmpty || !atts.isEmpty else { return }
        // 立刻清空本地输入；不要经 model.draft，避免 onChange 回填
        composerText = ""
        model.sendUserMessage(
            text,
            projectId: paneProjectId,
            threadId: paneThreadId,
            stopAndSend: true,
            attachments: atts
        )
        model.composerAttachments = []
    }
}

struct CodexMessageRow: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    let message: ChatMessage
    @State private var isEditing = false
    @State private var editText: String = ""

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
        let body = message.visibleContent.isEmpty && message.isStreaming && message.toolSteps.isEmpty
            ? "…"
            : message.visibleContent
        let showActions = !message.isStreaming && !body.isEmpty && body != "…"
        return VStack(alignment: .trailing, spacing: 4) {
            HStack(alignment: .top, spacing: 0) {
                Spacer(minLength: 80)
                if isEditing {
                    VStack(spacing: 6) {
                        TextEditor(text: $editText)
                            .font(CCCTheme.body)
                            .frame(minHeight: 60)
                            .scrollContentBackground(.hidden)
                            .padding(6)
                            .background(
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(CCCTheme.surface)
                            )
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(CCCTheme.border, lineWidth: 1)
                            )
                        HStack(spacing: 8) {
                            Button("取消") {
                                isEditing = false
                            }
                            .buttonStyle(.plain)
                            .font(.system(size: 11))
                            .foregroundStyle(CCCTheme.faint)
                            Button("保存") {
                                let tid = window.threadId ?? ""
                                model.updateMessage(threadId: tid, messageId: message.id, newContent: editText)
                                isEditing = false
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(CCCTheme.accent)
                            .controlSize(.small)
                        }
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(CCCTheme.bubbleUser)
                    )
                } else {
                    Text(body)
                        .font(CCCTheme.body)
                        .foregroundStyle(CCCTheme.ink)
                        .lineSpacing(CCCTheme.bodyLineSpacing)
                        .textSelection(.enabled)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .fill(CCCTheme.bubbleUser)
                        )
                }
            }
            if showActions {
                MessageActionBar(role: "user", content: body, message: message,
                                 onEdit: {
                    editText = message.content
                    isEditing = true
                })
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
                    // 仅整轮结束后才 finished（绿勾）；流式中一律过程态
                    finished: !message.isStreaming,
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
                Group {
                    if message.isStreaming {
                        // 流式中用纯文本：避免 Markdown 块结构每 token 重组导致闪烁/跳动
                        Text(body)
                            .font(CCCTheme.body)
                            .foregroundStyle(CCCTheme.ink)
                            .lineSpacing(CCCTheme.bodyLineSpacing)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    } else {
                        MarkdownText(source: body)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .animation(.easeOut(duration: 0.18), value: message.isStreaming)
            }
            if showActions {
                MessageActionBar(role: "assistant", content: body, message: message)
                if message.filesChanged > 0 || !message.changedFilePaths.isEmpty {
                    Button("查看改动") {
                        model.revealChangedFiles(message: message, projectId: window.projectId)
                    }
                    .buttonStyle(.plain)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.accent)
                    .accessibilityLabel("在 Finder 中查看本轮改动文件")
                }
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
    var onEdit: (() -> Void)? = nil

    var body: some View {
        HStack(spacing: 10) {
            actionBtn("复制") { model.copyMessage(content) }
            if role == "user" {
                actionBtn("编辑") {
                    if let onEdit {
                        onEdit()
                    } else {
                        model.editUserMessage(
                            message,
                            projectId: window.projectId,
                            threadId: window.threadId
                        )
                    }
                }
            } else {
                actionBtn("重新生成") {
                    model.regenerateAssistant(
                        after: message,
                        projectId: window.projectId,
                        threadId: window.threadId
                    )
                }
                actionBtn("预览") { model.previewMessage(content) }
                if model.canTransfer(projectId: window.projectId) {
                    actionBtn("转任务") {
                        model.openTransfer(
                            fromAssistantContent: content,
                            projectId: window.projectId,
                            threadId: window.threadId
                        )
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
        .accessibilityLabel(title)
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
        // 订阅 flow 修订号（与消息 threadRevision 分离，避免右栏 SSE 拖聊天重滚）
        if let tid = paneThreadId {
            _ = model.threadFlowRevision[tid]
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

            // Phase14：右栏只读本窗 threadFlow（snap），禁止回退全局 flow*（多窗串台）
            if (snap?.recentEpics ?? []).count > 1 {
                Menu {
                    ForEach(snap?.recentEpics ?? []) { epic in
                        Button {
                            Task { await model.selectEpic(epic.epic_id, projectId: window.projectId) }
                        } label: {
                            HStack {
                                Text(epic.title ?? epic.epic_id)
                                if epic.epic_id == snap?.epicId {
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

            if let hint = snap?.fanoutHint {
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

            if let stop = snap?.stopLossHint {
                VStack(alignment: .leading, spacing: 8) {
                    Text(stop)
                        .font(.system(size: 11.5, weight: .semibold))
                        .foregroundStyle(CCCTheme.nodeFail)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 10) {
                        Button("开运维") {
                            window.destination = .ops
                            model.selectDestination(.ops, projectId: window.projectId)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(CCCTheme.nodeFail)
                        .controlSize(.small)
                        Button("看板") {
                            window.destination = .board
                            model.selectDestination(.board, projectId: window.projectId)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        Button("忽略") {
                            model.clearStopLossHint(projectId: window.projectId)
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
                        .fill(CCCTheme.nodeFail.opacity(0.12))
                )
                .padding(.horizontal, 12)
                .padding(.bottom, 8)
            }

            FlowCanvasView(
                epic: snap?.epic,
                epicId: snap?.epicId,
                works: snap?.works ?? [],
                headline: snap?.headline ?? "",
                emptyMessage: snap?.emptyMessage
                    ?? "编排空闲·等定稿下达（与对话故障无关）",
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
                   (snap?.works ?? []).contains(where: { $0.workId == detail.id && $0.isFailed }) {
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
        let epics = snap?.recentEpics ?? []
        let eid = snap?.epicId
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
            Section {
                TextField("Hub 地址", text: $model.serverURLString)
                TextField("用户", text: $model.authUser)
                SecureField("密码", text: $model.authPass)
            } header: {
                Text("中心 Hub（转任务 / 看板 / 编排）")
            } footer: {
                Text("对话不经 Hub。Hub 只负责转任务、右栏流程与运维数据。")
            }

            Section {
                TextField("本机 Agent", text: $model.agentURLString)
                TextField("CCC 仓根（拉起 sidecar）", text: $model.cccHomePath)
                Picker("对话模型", selection: $model.preferredModel) {
                    ForEach(StreamSessionController.modelPickerOptions, id: \.id) { opt in
                        Text(opt.label).tag(opt.id)
                    }
                }
                .onChange(of: model.preferredModel) { newValue in
                    let name = StreamSessionController.modelDisplayName(newValue)
                    model.showToast("对话模型：\(name)")
                }
                Picker("默认工具模式", selection: $model.preferredToolMode) {
                    Text("讨论（只读）").tag("discuss")
                    Text("工程师（可写）").tag("engineer")
                }
                if !model.sidecarReportedModel.isEmpty {
                    Text("Sidecar 报告：\(model.sidecarReportedModel)")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
                if !model.sidecarRuntimeLabel.isEmpty || !model.sidecarLoopCodeVersion.isEmpty {
                    Text(
                        [
                            model.sidecarRuntimeLabel.isEmpty ? nil : "运行时 \(model.sidecarRuntimeLabel)",
                            model.sidecarLoopCodeVersion.isEmpty ? nil : "version \(model.sidecarLoopCodeVersion)",
                            model.sidecarConfigDir.isEmpty ? nil : model.sidecarConfigDir,
                        ]
                        .compactMap { $0 }
                        .joined(separator: " · ")
                    )
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
                }
            } header: {
                Text("本机对话 Agent")
            } footer: {
                Text("模型在 App 内选择（持久化 ccc.preferredModel），按请求传 sidecar。上游出口由 sidecar plist 固定 MiniMax；与个人 Claude Code / shell ANTHROPIC_* 无关。默认 MiniMax-M3（flash）。运行时 = vendor/loop-code（Phase1–5 配置切割）。")
            }

            Section {
                TextField(
                    "当前项目本机路径",
                    text: Binding(
                        get: { model.selectedProjectLocalPath },
                        set: { model.selectedProjectLocalPath = $0 }
                    )
                )
                TextField("全局工作区 fallback", text: $model.localWorkspacePath)
            } header: {
                Text("本机工作区")
            }

            Section {
                Button("重新连接") { Task { await model.reconnect() } }
                Button("打开用法说明") { model.isHelpPresented = true }
                Button("从剪贴板导入会话 JSON") {
                    Task { await model.importThreadJSONFromPasteboard(projectId: model.selectedProjectId) }
                }
            }
        }
        .formStyle(.grouped)
        .padding(12)
        .frame(width: 520, height: 480)
    }
}

// MARK: - Context panel

struct ContextPanelSheet: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    let threadId: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("本会话上下文")
                    .font(.system(size: 16, weight: .semibold))
                Spacer()
                Button("关闭") {
                    model.isContextPanelPresented = false
                    dismiss()
                }
            }
            let msgs = model.messagesForThread(threadId)
            let tok = model.sessionTokenCount(for: threadId)
            let est = LocalSessionStore.estimateTokens(msgs)
            Group {
                LabeledContent("消息数", value: "\(msgs.count)")
                LabeledContent("本会话 token", value: "\(tok)")
                LabeledContent("估算字符 token", value: "\(est)")
                LabeledContent("模型偏好", value: StreamSessionController.modelDisplayName(model.preferredModel))
                LabeledContent("工具模式", value: model.preferredToolMode)
                LabeledContent(
                    "Resume",
                    value: model.hasResume(for: threadId) ? "有" : "无"
                )
            }
            .font(.system(size: 12))

            Text("本会话 token 来自 sidecar cost；顶栏「今日 / 5s」是本机 Agent 大模型调用次数（每轮对话计 1）。")
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.secondary)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 12) {
                Button("压缩上下文") {
                    Task {
                        await model.manualCompact(threadId: threadId)
                        model.isContextPanelPresented = false
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(CCCTheme.accent)
                Button("导出 JSON") {
                    model.exportThreadJSONToPasteboard(threadId: threadId)
                }
                .buttonStyle(.plain)
            }
            Spacer(minLength: 0)
        }
        .padding(20)
        .frame(width: 420, height: 320)
        .background(CCCTheme.chatBg)
    }
}

// MARK: - Help

struct DesktopHelpSheet: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("CCC Desktop 用法")
                    .font(.system(size: 18, weight: .semibold))
                Spacer()
                Button("关闭") {
                    model.isHelpPresented = false
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)
            }

            Text("人定意图，系统自动编排。你不必选角色。")
                .font(.system(size: 13))
                .foregroundStyle(CCCTheme.secondary)

            VStack(alignment: .leading, spacing: 12) {
                helpRow("1", "选左侧业务项目", "进入该项目的方案对话（一项目可多会话）。")
                helpRow("2", "聊透目标与验收", "用白话说清楚；可用「对齐基线 / 下一步 / 扫风险」。")
                helpRow("3", "定稿", "点快捷条「定稿」，生成可投递的契约包。")
                helpRow("4", "转任务", "确认门禁后写入待办；右侧「本对话编排」展开进度。")
                helpRow("5", "看板 / 运维", "侧栏切换；看全局队列与集群健康，再「回对话」。")
            }

            Divider()

            VStack(alignment: .leading, spacing: 6) {
                Text("快捷键")
                    .font(.system(size: 12, weight: .semibold))
                Text("⌘N 新会话 · ⌘F 搜索 · ⌘1 对话 · ⌘2 看板 · ⌘3 运维 · ⌘⇧T 转任务 · 会话可分叉/存档/导出 JSON")
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.secondary)
            }

            Spacer(minLength: 0)
        }
        .padding(24)
        .frame(width: 480, height: 420)
        .background(CCCTheme.chatBg)
    }

    private func helpRow(_ n: String, _ title: String, _ detail: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text(n)
                .font(.system(size: 12, weight: .bold, design: .rounded))
                .foregroundStyle(Color.white)
                .frame(width: 22, height: 22)
                .background(Circle().fill(CCCTheme.accent))
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                Text(detail)
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.secondary)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(n). \(title)。\(detail)")
    }
}

// MARK: - Manual Epic Creation Sheet (Phase 2.1)

struct ManualEpicSheet: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState

    var body: some View {
        VStack(spacing: 16) {
            Text("创建新任务")
                .font(.headline)
            TextField("标题", text: $model.manualEpicForm.title)
                .textFieldStyle(.roundedBorder)
                .font(.system(size: 13))
            TextEditor(text: $model.manualEpicForm.goal)
                .font(.system(size: 13))
                .frame(height: 60)
                .scrollContentBackground(.hidden)
                .overlay(
                    Group {
                        if model.manualEpicForm.goal.isEmpty {
                            Text("目标")
                                .foregroundStyle(CCCTheme.faint)
                                .padding(6)
                                .allowsHitTesting(false)
                        }
                    },
                    alignment: .topLeading
                )
            TextEditor(text: $model.manualEpicForm.acceptance)
                .font(.system(size: 13))
                .frame(height: 80)
                .scrollContentBackground(.hidden)
                .overlay(
                    Group {
                        if model.manualEpicForm.acceptance.isEmpty {
                            Text("验收条件（每行一条）")
                                .foregroundStyle(CCCTheme.faint)
                                .padding(6)
                                .allowsHitTesting(false)
                        }
                    },
                    alignment: .topLeading
                )
            HStack(spacing: 12) {
                Picker("产线", selection: $model.manualEpicForm.pipeline) {
                    Text("dev").tag("dev")
                    Text("product").tag("product")
                    Text("ops").tag("ops")
                }
                .labelsHidden()
                Picker("复杂度", selection: $model.manualEpicForm.complexity) {
                    Text("低").tag("low")
                    Text("中").tag("medium")
                    Text("高").tag("high")
                }
                .labelsHidden()
            }
            HStack(spacing: 12) {
                Button("取消") {
                    model.isManualEpicPresented = false
                }
                .buttonStyle(.plain)
                .foregroundStyle(CCCTheme.faint)
                Button("从模板…") {
                    model.loadTemplates()
                    model.isTemplatePickerPresented = true
                }
                .buttonStyle(.plain)
                .foregroundStyle(CCCTheme.accent)
                Button("创建") {
                    guard let pid = window.projectId else { return }
                    Task { await model.createManualEpic(projectId: pid, form: model.manualEpicForm) }
                }
                .buttonStyle(.borderedProminent)
                .tint(CCCTheme.accent)
                .disabled(model.busy)
            }
        }
        .padding(24)
        .frame(width: 460)
    }
}

// MARK: - Template Picker Sheet (Phase 2.2)

struct TemplatePickerSheet: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 12) {
            Text("任务模板")
                .font(.headline)
            if model.templates.isEmpty {
                Text("暂无模板。可在转任务表单中保存当前方案为模板。")
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.faint)
                    .padding()
            } else {
                ScrollView {
                    LazyVStack(spacing: 6) {
                        ForEach(model.templates) { template in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(template.title)
                                        .font(.system(size: 12, weight: .medium))
                                    Text(template.goal.prefix(60))
                                        .font(.system(size: 11))
                                        .foregroundStyle(CCCTheme.faint)
                                        .lineLimit(1)
                                }
                                Spacer()
                                Button("应用") {
                                    model.applyTemplate(template)
                                    dismiss()
                                }
                                .buttonStyle(.borderedProminent)
                                .tint(CCCTheme.accent)
                                .controlSize(.small)
                                Button {
                                    model.deleteTemplate(title: template.title)
                                } label: {
                                    Image(systemName: "trash")
                                        .font(.system(size: 11))
                                }
                                .buttonStyle(.plain)
                                .foregroundStyle(CCCTheme.nodeFail)
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(CCCTheme.hover.opacity(0.5))
                            .cornerRadius(8)
                        }
                    }
                    .padding(8)
                }
            }
            Button("关闭") {
                dismiss()
            }
            .buttonStyle(.plain)
            .foregroundStyle(CCCTheme.faint)
        }
        .padding(20)
        .frame(width: 400, height: 360)
    }
}
