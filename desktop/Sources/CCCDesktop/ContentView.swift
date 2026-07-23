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
        // 顶栏用量：accessory 自带 1s timer，勿用 .id(tick) 拖整窗重挂
        .background(
            TitlebarUsageAccessory(model: model)
                .frame(width: 0, height: 0)
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
            Text(model.canChat ? model.hubRetryStatusPhrase : "本机 Agent 未就绪")
                .font(.system(size: 13, weight: .medium))
            Text(
                model.canChat
                    ? "可继续聊；转任务可确认排队。Hub 恢复后后台自动投递（每 4s 探活）。"
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
        let tid = thread.thread_id
        // 先水合再绑 window.threadId，避免一帧 displayMessages=[]（冲刷感）
        model.ensureThreadHydrated(threadId: tid)
        window.projectId = projectId
        window.threadId = tid
        window.destination = .chat
        model.selectedThreadId = tid
        model.selectedProjectId = projectId
        model.clearThreadUnread(tid)
        Task {
            await model.openThread(tid)
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
    /// 用于抓「有内容→变空」瞬间（H6）
    @State private var lastDisplayMsgCount: Int = -1
    /// 同 tid 下 count→0 才报 H6；跨线程切换不算冲刷
    @State private var lastH6ThreadId: String = ""
    /// 上一帧有内容时切 tid 禁止 opacity→0
    @State private var lastNonEmptyMsgCount: Int = 0
    @FocusState private var composerFocused: Bool

    /// 本窗唯一项目焦点；首帧未绑定时短暂回落全局，避免闪空（H5）
    private var paneProjectId: String? {
        if let pid = window.projectId, !pid.isEmpty { return pid }
        return model.selectedProjectId
    }

    /// 本窗线程；首帧 window.threadId 未写入前用 model.selectedThreadId（H5）
    private var paneThreadId: String? {
        if let tid = window.threadId, !tid.isEmpty { return tid }
        if window.projectId == nil || window.projectId == model.selectedProjectId,
           let tid = model.selectedThreadId, !tid.isEmpty {
            return tid
        }
        return nil
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

            // hydrating：tid 已定但 RAM 尚未登记 → 转圈，禁止 offlineCenter / 空欢迎冲刷
            let paneHydrating =
                paneThreadId.map { !model.hasHydratedThread($0) } ?? false

            if paneHydrating {
                VStack(spacing: 10) {
                    Spacer()
                    ProgressView()
                        .controlSize(.regular)
                    Text("加载对话…")
                        .font(.system(size: 12, weight: .light))
                        .foregroundStyle(CCCTheme.faint)
                    Spacer()
                }
                .frame(maxWidth: .infinity)
            } else if paneThreadId == nil {
                // 首帧 window 未绑定时禁止整页 offline（H5）
                VStack(spacing: 10) {
                    Spacer()
                    ProgressView()
                        .controlSize(.regular)
                    Text("加载对话…")
                        .font(.system(size: 12, weight: .light))
                        .foregroundStyle(CCCTheme.faint)
                    Spacer()
                }
                .frame(maxWidth: .infinity)
            } else {
                // 已绑 thread：始终挂 messageArea（含空会话欢迎）；离线只顶 banner，禁止整页卸列表（H1）
                VStack(spacing: 0) {
                    if !model.canChat {
                        offlineBanner
                    }
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
        }
        .background(CCCTheme.chatBg)
        .onAppear {
            // #region agent log
            DebugAgentLog.log(
                hypothesisId: "H5",
                location: "CodexChatPane.onAppear",
                message: "chat pane appear",
                data: [
                    "windowThreadId": window.threadId ?? "",
                    "paneThreadId": paneThreadId ?? "",
                    "msgCount": displayMessages.count,
                    "agentMode": model.agentMode,
                    "destination": String(describing: window.destination),
                ],
                runId: "post-fix"
            )
            // #endregion
            if window.projectId == nil {
                window.projectId = model.selectedProjectId
            }
            if window.threadId == nil, let tid = model.selectedThreadId,
               window.projectId == nil || LocalSessionStore.projectId(fromThreadId: tid) == window.projectId {
                window.threadId = tid
            }
            if let tid = window.threadId ?? paneThreadId {
                model.ensureThreadHydrated(threadId: tid)
            } else if let pid = window.projectId {
                model.ensureThreadHydrated(projectId: pid)
            }
            NSApp.activate(ignoringOtherApps: true)
            composerFocused = true
            lastDisplayMsgCount = displayMessages.count
        }
        .onChange(of: window.projectId) { pid in
            if let pid {
                model.ensureThreadHydrated(projectId: pid)
            }
        }
        .onChange(of: window.threadId) { newTid in
            // #region agent log
            DebugAgentLog.log(
                hypothesisId: "H2",
                location: "CodexChatPane.onChange.threadId",
                message: "window.threadId changed",
                data: [
                    "threadId": newTid ?? "",
                    "msgCount": model.messagesForThread(newTid).count,
                    "projectId": window.projectId ?? "",
                ],
                runId: "post-fix"
            )
            // #endregion
            if let newTid, !newTid.isEmpty {
                model.ensureThreadHydrated(threadId: newTid)
            }
            // 消息源只跟 thread；以 thread 切换驱动过渡，避免与 project 双触发叠闪
            beginPaneSwitchTransition()
        }
        .onChange(of: model.agentMode) { mode in
            // #region agent log
            DebugAgentLog.log(
                hypothesisId: "H1",
                location: "CodexChatPane.onChange.agentMode",
                message: "agentMode changed",
                data: [
                    "agentMode": mode,
                    "canChat": model.canChat,
                    "threadId": paneThreadId ?? "",
                    "msgCount": model.messagesForThread(paneThreadId).count,
                ],
                runId: "post-fix"
            )
            // #endregion
        }
        .onChange(of: displayMessages.count) { newCount in
            let tid = paneThreadId ?? ""
            // #region agent log
            // 仅同一 threadId 下 count→0 才算冲刷；跨线程切换会误报
            if lastDisplayMsgCount > 0, newCount == 0, !tid.isEmpty, tid == lastH6ThreadId {
                DebugAgentLog.log(
                    hypothesisId: "H6",
                    location: "CodexChatPane.onChange.displayMessages",
                    message: "displayMessages dropped to empty",
                    data: [
                        "prev": lastDisplayMsgCount,
                        "threadId": tid,
                        "windowThreadId": window.threadId ?? "",
                        "agentMode": model.agentMode,
                        "canChat": model.canChat,
                        "destination": String(describing: window.destination),
                        "opacity": paneContentOpacity,
                    ],
                    runId: "post-fix"
                )
            }
            // #endregion
            lastDisplayMsgCount = newCount
            if !tid.isEmpty { lastH6ThreadId = tid }
            if newCount > 0 { lastNonEmptyMsgCount = newCount }
        }
        .onChange(of: window.destination) { dest in
            // #region agent log
            DebugAgentLog.log(
                hypothesisId: "H7",
                location: "CodexChatPane.onChange.destination",
                message: "destination changed",
                data: [
                    "destination": String(describing: dest),
                    "threadId": paneThreadId ?? "",
                    "msgCount": displayMessages.count,
                ],
                runId: "post-fix"
            )
            // #endregion
        }
        .onChange(of: scenePhase) { phase in
            // A→B→A：窗体未必销毁，onAppear 不跑；激活时仍要瞬移最新，禁止扫历史
            if phase == .active {
                // #region agent log
                DebugAgentLog.log(
                    hypothesisId: "H8",
                    location: "CodexChatPane.onChange.scenePhase",
                    message: "scene became active",
                    data: [
                        "threadId": paneThreadId ?? "",
                        "msgCount": displayMessages.count,
                        "agentMode": model.agentMode,
                    ],
                    runId: "post-fix"
                )
                // #endregion
                pinBottomOnNextScroll()
                bottomPinTick &+= 1
                model.onForegroundResume()
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
                Text("四段主路径")
                    .font(.system(size: 12, weight: .medium))
                Text("① 聊透/对齐基线（可选）→ ②「下一步」会核实仓况 → ③「定稿」锁方案 → ④ 转任务仅改标题备注。侧栏「用法」可开。")
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

    /// 切项目/会话：有内容时禁止 opacity 清零（启动/探活卡顿会空白数秒，H4）
    private func beginPaneSwitchTransition() {
        paneSwitchGeneration &+= 1
        let gen = paneSwitchGeneration
        let msgCount = displayMessages.count
        let hasContent = msgCount > 0 || lastNonEmptyMsgCount > 0
        // #region agent log
        DebugAgentLog.log(
            hypothesisId: "H4",
            location: "CodexChatPane.beginPaneSwitchTransition",
            message: hasContent ? "skip opacity hide (has content)" : "opacity→0",
            data: [
                "gen": gen,
                "threadId": paneThreadId ?? "",
                "msgCount": msgCount,
                "lastNonEmpty": lastNonEmptyMsgCount,
                "hasContent": hasContent,
            ],
            runId: "post-fix"
        )
        // #endregion
        if hasContent {
            var pin = Transaction()
            pin.disablesAnimations = true
            withTransaction(pin) {
                paneContentOpacity = 1
                showPaneSwitchSpinner = false
                pinBottomOnNextScroll()
            }
            Task { @MainActor in
                await Task.yield()
                guard gen == paneSwitchGeneration else { return }
                bottomPinTick &+= 1
            }
            return
        }
        var hide = Transaction()
        hide.disablesAnimations = true
        withTransaction(hide) {
            paneContentOpacity = 0
            showPaneSwitchSpinner = false
            pinBottomOnNextScroll()
        }
        Task { @MainActor in
            await Task.yield()
            guard gen == paneSwitchGeneration else {
                // #region agent log
                DebugAgentLog.log(
                    hypothesisId: "H4",
                    location: "CodexChatPane.beginPaneSwitchTransition",
                    message: "reveal aborted after yield1",
                    data: ["gen": gen, "current": paneSwitchGeneration],
                    runId: "post-fix"
                )
                // #endregion
                return
            }
            bottomPinTick &+= 1
            await Task.yield()
            guard gen == paneSwitchGeneration else {
                // #region agent log
                DebugAgentLog.log(
                    hypothesisId: "H4",
                    location: "CodexChatPane.beginPaneSwitchTransition",
                    message: "reveal aborted after yield2",
                    data: ["gen": gen, "current": paneSwitchGeneration],
                    runId: "post-fix"
                )
                // #endregion
                return
            }
            var reveal = Transaction()
            reveal.disablesAnimations = true
            withTransaction(reveal) {
                paneContentOpacity = 1
            }
            // #region agent log
            DebugAgentLog.log(
                hypothesisId: "H4",
                location: "CodexChatPane.beginPaneSwitchTransition",
                message: "opacity→1",
                data: [
                    "gen": gen,
                    "threadId": paneThreadId ?? "",
                    "msgCount": displayMessages.count,
                ],
                runId: "post-fix"
            )
            // #endregion
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
            } else if !model.hubReachable {
                Text(model.hubRetryStatusPhrase)
                    .font(.system(size: 10))
                    .foregroundStyle(CCCTheme.secondary)
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
                if phase == .failed {
                    Button("后台再试") {
                        model.retryFailedTransfersInBackground()
                    }
                    .buttonStyle(.plain)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(CCCTheme.accent)
                    .accessibilityLabel("投递失败后台再试")
                }
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

    /// Agent 短暂未就绪：顶条提示，禁止卸掉已有消息（H1）
    private var offlineBanner: some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 11))
                .foregroundStyle(CCCTheme.nodeFail)
            Text("本机 Agent 暂未就绪 · 历史仍在，恢复后可继续发")
                .font(.system(size: 11.5))
                .foregroundStyle(CCCTheme.secondary)
                .lineLimit(2)
            Spacer(minLength: 0)
            Button("重试") { Task { await model.reconnect() } }
                .buttonStyle(.bordered)
                .controlSize(.mini)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(CCCTheme.nodeFail.opacity(0.08))
        .accessibilityLabel("本机 Agent 未就绪")
    }

    private var messageArea: some View {
        GeometryReader { geometry in
            ScrollViewReader { proxy in
                ScrollView(showsIndicators: false) {
                    LazyVStack(alignment: .leading, spacing: CCCTheme.messageStackSpacing) {
                        if displayMessages.isEmpty {
                            if lastNonEmptyMsgCount > 0 {
                                // 切 tid 瞬间仍空：转圈，勿把「冲刷」画成空欢迎
                                VStack(spacing: 10) {
                                    Spacer().frame(height: 80)
                                    ProgressView()
                                        .controlSize(.regular)
                                    Text("加载对话…")
                                        .font(.system(size: 12, weight: .light))
                                        .foregroundStyle(CCCTheme.faint)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.bottom, 24)
                            } else {
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
                                    emptyStep(num: "1", title: "聊透 / 下一步", detail: "对齐基线可选；下一步会核实仓况再定方案")
                                    emptyStep(num: "2", title: "点「定稿」", detail: "生成契约并锁方案（二级卡不可改正文）")
                                    emptyStep(num: "3", title: "确认转任务", detail: "仅可改标题与备注；右侧展开编排")
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
                        // 失败提示：在消息流末尾显式给「重试 / 清槽」按钮，避免状态栏太隐蔽
                        if let fail = model.lastTurnFailure,
                           fail.threadId == paneThreadId,
                           !paneStreaming {
                            HStack(spacing: 10) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.system(size: 12))
                                    .foregroundStyle(CCCTheme.nodeFail)
                                Text("本条失败：\(fail.shortLabel)")
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundStyle(CCCTheme.nodeFail)
                                Spacer(minLength: 0)
                                Button("重试") { model.retryLastFailedTurn(threadId: paneThreadId) }
                                    .buttonStyle(.plain)
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundStyle(CCCTheme.accent)
                                    .help(fail.message)
                                Button("清槽") { model.healThreadSlot(threadId: paneThreadId) }
                                    .buttonStyle(.plain)
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundStyle(CCCTheme.secondary)
                                    .help("回收本会话 Agent live 槽后重发")
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                            .background(CCCTheme.nodeFail.opacity(0.08))
                            .overlay(
                                RoundedRectangle(cornerRadius: 10, style: .continuous)
                                    .stroke(CCCTheme.nodeFail.opacity(0.25), lineWidth: 1)
                            )
                            .cornerRadius(10)
                            .padding(.top, 8)
                            .frame(maxWidth: CCCTheme.chatMaxWidth)
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel("本条失败：\(fail.shortLabel)，可重试或清槽")
                        }
                        // tip：钉在视口 y=2/3；下方 Spacer(≈1/3 高) 正好留白
                        Color.clear
                            .frame(height: 1)
                            .id(bottomAnchorId)
                        // 底部约 1/3 空槽：最新轮偏上，流式向下长时内容上推、留白保持
                        Spacer().frame(
                            height: max(geometry.size.height * Self.chatBottomReserveFraction, 120)
                        )
                    }
                    .frame(maxWidth: CCCTheme.chatMaxWidth)
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 28)
                    .padding(.top, 8)
                }
                .onAppear {
                    // 窗体重入 / 首次进入：瞬移跟随位，勿从上往下刷
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
                        // 定位到该条时仍靠上，下方留给上下文
                        proxy.scrollTo(id, anchor: UnitPoint(x: 0.5, y: 0.25))
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

    /// 对话栏底部留白比例（视口高度）
    private static let chatBottomReserveFraction: CGFloat = 1.0 / 3.0

    /// tip 落在视口 2/3 处 → 下方正好约 1/3 空白
    private static var chatFollowAnchor: UnitPoint {
        UnitPoint(x: 0.5, y: 1 - chatBottomReserveFraction)
    }

    /// 底部留约 1/3：钉 tip 到 y=2/3；禁止 tip+.bottom（会吃掉留白）
    private func scroll(_ proxy: ScrollViewProxy) {
        guard !displayMessages.isEmpty else { return }
        let tip = bottomAnchorId
        let last = displayMessages.last

        func pinTip(animated: Bool = false) {
            if animated {
                withAnimation(.easeOut(duration: 0.18)) {
                    proxy.scrollTo(tip, anchor: Self.chatFollowAnchor)
                }
            } else {
                var t = Transaction()
                t.disablesAnimations = true
                withTransaction(t) {
                    proxy.scrollTo(tip, anchor: Self.chatFollowAnchor)
                }
            }
        }

        // 1) 切会话 / 重入：瞬移到跟随位
        if needsInstantBottomPin {
            needsInstantBottomPin = false
            lastScrollTargetId = tip
            lastStreamScrollBucket = -1
            pinTip()
            return
        }

        // 2) 流式：节流跟滚，始终保持底部约 1/3 空
        if let last, last.isStreaming, last.role == "assistant" {
            let bucket = last.content.count / 80 + last.toolSteps.count * 1_000
            if lastScrollTargetId == tip, bucket == lastStreamScrollBucket {
                return
            }
            lastScrollTargetId = tip
            lastStreamScrollBucket = bucket
            pinTip()
            return
        }

        // 3) 新 user / 回合结束：钉 tip（上留历史，下留 1/3）
        let fingerprint = "\(displayMessages.count)-\(last?.id.uuidString ?? "")-settled"
        if fingerprint == lastScrollTargetId { return }
        lastScrollTargetId = fingerprint
        lastStreamScrollBucket = -1
        pinTip()
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
                    Text(model.preferredToolMode == "engineer" ? "工程师" : "规划")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(
                            model.preferredToolMode == "engineer"
                                ? CCCTheme.nodeFail
                                : CCCTheme.secondary
                        )
                }
                .buttonStyle(.plain)
                .help("规划=Plan 全智力只读（不可改码）；工程师=仅平台仓 ccc 可本机改文件；业务仓请定稿转任务")

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
                Text("默认规划模式（Plan）：全智力只读，可检索/子代理调研，不可改码。工程师模式仅允许在平台仓 ccc 修改本机文件；业务仓请定稿转任务。")
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
                        help: "深对齐：Hub 快照+透镜；可选，不是「下一步/定稿」的硬门槛"
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
                        help: "先 lens 核实 board/git 再给最佳方案；未 ready 只谈板务，不必先点对齐基线"
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
                        help: "核实后生成契约并锁方案；转任务二级卡仅可改标题与备注"
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
            // 禁用态仍要反馈：SwiftUI .disabled 会吞掉点击，用户以为「没反应」
            if blocked {
                if !model.canChat {
                    model.showToast("本机 Agent 未就绪，无法执行「\(title)」")
                } else if paneStreaming {
                    model.showToast("请先停止当前生成，再点「\(title)」")
                } else if let running = model.activeQuickAction, !running.isEmpty {
                    model.showToast("请等待「\(running)」完成")
                } else {
                    model.showToast("暂时无法执行「\(title)」")
                }
                return
            }
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
        let raw = message.content
        let transferJSON = message.isStreaming ? nil : TransferDraftParser.transferFenceJSON(from: raw)
        let body: String = {
            if message.content.isEmpty && message.isStreaming && message.toolSteps.isEmpty {
                return "…"
            }
            if message.isStreaming {
                // 流式中仍可能半截 fence；尽量不把半截 JSON 当结论
                return TransferDraftParser.humanVisibleMarkdown(from: raw).isEmpty
                    ? (raw.contains("```ccc-transfer") ? "正在生成定稿结论…" : raw)
                    : TransferDraftParser.humanVisibleMarkdown(from: raw)
            }
            let human = TransferDraftParser.humanVisibleMarkdown(from: raw)
            return human.isEmpty && transferJSON != nil ? "已定稿（见下方确认转任务）" : human
        }()
        let showActions = !message.isStreaming && !raw.isEmpty && body != "…"
        return VStack(alignment: .leading, spacing: 8) {
            if message.isStreaming || !message.toolSteps.isEmpty {
                ToolProgressRail(
                    steps: message.toolSteps,
                    filesChanged: message.filesChanged,
                    // 仅整轮结束后才 finished（绿勾）；流式中一律过程态
                    finished: !message.isStreaming,
                    placeholder: message.toolSteps.isEmpty ? "正在思考 / 调用工具…" : nil,
                    statusHint: message.isStreaming ? model.streamStatus(for: window.threadId) : nil
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
            if let json = transferJSON, !message.isStreaming {
                DisclosureGroup("转任务契约（给 Engine）") {
                    Text(json)
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(CCCTheme.secondary)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.top, 4)
                }
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(CCCTheme.faint)
                .padding(.horizontal, 2)
            }
            if showActions {
                MessageActionBar(role: "assistant", content: raw, message: message)
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

// MARK: - Flow rail（跟左侧项目绑定）

struct FlowRail: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState

    /// 右栏跟本窗项目，不跟单个会话
    private var paneProjectId: String? {
        if let pid = window.projectId, !pid.isEmpty { return pid }
        return model.selectedProjectId
    }

    private var snap: FlowThreadSnapshot? {
        if let pid = paneProjectId {
            _ = model.projectFlowRevision[pid]
        }
        return model.flowSnapshot(forProject: paneProjectId)
    }

    private static let boardChipCols: [(key: String, label: String)] = [
        ("backlog", "待办"),
        ("planned", "规划"),
        ("in_progress", "进行"),
        ("testing", "验收"),
        ("abnormal", "异常"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Color.clear.frame(height: 8)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("本项目态势")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(CCCTheme.ink)
                    Spacer(minLength: 0)
                    Button("看板") {
                        window.destination = .board
                        model.selectDestination(.board, projectId: paneProjectId)
                    }
                    .buttonStyle(.plain)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(CCCTheme.accent)
                }
                Text(model.orchestrationSyncLabel(forProject: paneProjectId))
                    .font(.system(size: 10))
                    .foregroundStyle(CCCTheme.faint)
                    .accessibilityLabel("编排同步态")
                if let title = boundEpicTitle {
                    Text(title)
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.secondary)
                        .lineLimit(2)
                } else if paneProjectId == nil {
                    Text("先选左侧项目")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.faint)
                } else {
                    Text("定稿下达后显示编排")
                        .font(.system(size: 11))
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            .padding(.horizontal, 14)
            .padding(.top, 4)
            .padding(.bottom, 8)

            boardStrip
                .padding(.horizontal, 12)
                .padding(.bottom, 10)

            if !(snap?.recentEpics ?? []).isEmpty {
                taskStack
                    .padding(.horizontal, 12)
                    .padding(.bottom, 8)
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
                            model.selectDestination(.ops, projectId: paneProjectId)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(CCCTheme.accent)
                        .controlSize(.small)
                        Button("忽略") {
                            model.clearFanoutHint(projectId: paneProjectId, threadId: nil)
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
                            model.selectDestination(.ops, projectId: paneProjectId)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(CCCTheme.nodeFail)
                        .controlSize(.small)
                        Button("看板") {
                            window.destination = .board
                            model.selectDestination(.board, projectId: paneProjectId)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        Button("忽略") {
                            model.clearStopLossHint(projectId: paneProjectId, threadId: nil)
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
                projectId: paneProjectId,
                threadId: nil,
                onOpenOps: {
                    window.destination = .ops
                    model.selectDestination(.ops, projectId: paneProjectId)
                },
                onSelectNode: { model.openNodeDetail(id: $0, projectId: paneProjectId) }
            )
        }
        .background(CCCTheme.sidebar)
        .task(id: paneProjectId) {
            guard let pid = paneProjectId else { return }
            await model.bindFlowToProject(projectId: pid)
        }
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
                        model.selectDestination(.ops, projectId: paneProjectId)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(CCCTheme.accent)
                }
            }
            .padding(22)
            .frame(width: 420, height: 360)
        }
    }

    private var boardStrip: some View {
        let counts = model.boardCounts(forProject: paneProjectId)
        let deltas = model.boardCountsDelta(forProject: paneProjectId)
        return VStack(alignment: .leading, spacing: 6) {
            Text("看板")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(CCCTheme.faint)
            HStack(spacing: 6) {
                ForEach(Self.boardChipCols, id: \.key) { col in
                    let n = counts[col.key] ?? 0
                    let d = deltas[col.key] ?? 0
                    VStack(spacing: 2) {
                        HStack(spacing: 2) {
                            Text("\(n)")
                                .font(.system(size: 13, weight: .semibold, design: .rounded))
                                .foregroundStyle(col.key == "abnormal" && n > 0 ? CCCTheme.nodeFail : CCCTheme.ink)
                            if d != 0 {
                                Text(d > 0 ? "↑\(d)" : "↓\(-d)")
                                    .font(.system(size: 9, weight: .medium))
                                    .foregroundStyle(d > 0 ? CCCTheme.accent : CCCTheme.faint)
                            }
                        }
                        Text(col.label)
                            .font(.system(size: 9))
                            .foregroundStyle(CCCTheme.faint)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                    .background(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .fill(CCCTheme.chatBg)
                    )
                }
            }
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

    /// 纵向任务栈：当前展开条 + 历史折叠条（项目级大卡）
    private var taskStack: some View {
        let epics = snap?.recentEpics ?? []
        let currentId = snap?.epicId
        let current = epics.first(where: { $0.epic_id == currentId })
            ?? (currentId.map {
                FlowEpicRef(
                    epic_id: $0,
                    title: snap?.epic?.title,
                    updated_at: nil,
                    thread_id: nil,
                    user_stage: snap?.epic?.user_stage
                )
            })
        let history = epics.filter { $0.epic_id != currentId }

        return VStack(alignment: .leading, spacing: 6) {
            Text("大卡")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(CCCTheme.faint)
            if let cur = current {
                taskStackRow(cur, expanded: true)
            }
            if !history.isEmpty {
                Text("排队 / 历史")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(CCCTheme.faint)
                    .padding(.top, 4)
                ForEach(history) { epic in
                    Button {
                        Task {
                            await model.selectEpic(
                                epic.epic_id,
                                projectId: paneProjectId,
                                threadId: nil
                            )
                        }
                    } label: {
                        taskStackRow(epic, expanded: false)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func taskStackRow(_ epic: FlowEpicRef, expanded: Bool) -> some View {
        let stage = (epic.user_stage ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let stageLabel = stage.isEmpty ? (expanded ? "进行中" : "") : stage
        let done = stage.lowercased() == "done"
        return HStack(alignment: .center, spacing: 8) {
            Image(systemName: expanded ? "chevron.down" : "circle")
                .font(.system(size: expanded ? 9 : 7, weight: .semibold))
                .foregroundStyle(done ? CCCTheme.faint : (expanded ? CCCTheme.accent : CCCTheme.secondary))
                .frame(width: 12)
            VStack(alignment: .leading, spacing: 2) {
                Text(epic.title ?? epic.epic_id)
                    .font(.system(size: 11, weight: expanded ? .semibold : .regular))
                    .foregroundStyle(done ? CCCTheme.faint : CCCTheme.ink)
                    .lineLimit(expanded ? 2 : 1)
                if !stageLabel.isEmpty {
                    Text(stageLabel)
                        .font(.system(size: 10))
                        .foregroundStyle(done ? CCCTheme.faint : CCCTheme.secondary)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, expanded ? 8 : 6)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(expanded
                      ? CCCTheme.accent.opacity(0.08)
                      : CCCTheme.faint.opacity(done ? 0.06 : 0.04))
        )
        .opacity(done && !expanded ? 0.72 : 1)
    }
}

// MARK: - Sheets

struct TransferSheet: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) private var dismiss
    let threadId: String
    /// 本地草稿：打字不碰 AppModel @Published，避免背后聊天全树重绘卡顿
    @State private var draft = TransferFormState()
    @State private var planExpanded = false
    @State private var rejectNote: String = ""
    @State private var showRejectNote: Bool = false
    @State private var didLoad = false

    /// 正式定稿契约：方案锁死，仅标题/备注可改
    private var planLocked: Bool { draft.source == "ccc-transfer" }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("转任务")
                    .font(.system(size: 20, weight: .semibold))
                    .tracking(-0.4)
                Spacer()
                if !draft.source.isEmpty {
                    Text(draft.source == "ccc-transfer" ? "来源定稿" : "启发式预填")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(CCCTheme.faint)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(CCCTheme.faint.opacity(0.12), in: Capsule())
                }
            }
            Text(
                planLocked
                    ? "定稿方案已锁；仅可改标题与备注（含定时说明）。改方案请退回对话重定稿。"
                    : "启发式预填可改意图；建议先点「定稿」锁方案。纠错：退回对话重定稿。"
            )
                .font(CCCTheme.callout)
                .foregroundStyle(CCCTheme.faint)

            Form {
                Section(planLocked ? "意图（标题可改 · 方案已锁）" : "意图（可改）") {
                    TextField("标题", text: $draft.title)
                    if planLocked {
                        LabeledContent("目标") {
                            Text(draft.goal.isEmpty ? "—" : draft.goal)
                                .font(.system(size: 13))
                                .foregroundStyle(CCCTheme.secondary)
                                .frame(maxWidth: .infinity, alignment: .trailing)
                                .textSelection(.enabled)
                        }
                        LabeledContent("验收") {
                            Text(draft.acceptance.isEmpty ? "—" : draft.acceptance)
                                .font(.system(size: 12))
                                .foregroundStyle(CCCTheme.secondary)
                                .frame(maxWidth: .infinity, alignment: .trailing)
                                .textSelection(.enabled)
                        }
                        DisclosureGroup(isExpanded: $planExpanded) {
                            if planExpanded {
                                Text(draft.planMd.isEmpty ? "（无方案正文）" : draft.planMd)
                                    .font(.system(size: 12))
                                    .foregroundStyle(CCCTheme.secondary)
                                    .textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        } label: {
                            Text(planExpanded ? "方案正文（只读）" : planMdSummaryLocked)
                                .font(.system(size: 13))
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    } else {
                        TextField("目标", text: $draft.goal, axis: .vertical)
                            .lineLimit(3...6)
                        TextField("验收（每行一条）", text: $draft.acceptance, axis: .vertical)
                            .lineLimit(3...8)
                        DisclosureGroup(isExpanded: $planExpanded) {
                            if planExpanded {
                                TextField("方案正文", text: $draft.planMd, axis: .vertical)
                                    .lineLimit(4...12)
                            }
                        } label: {
                            Text(planExpanded ? "方案正文" : planMdSummary)
                                .font(.system(size: 13))
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    }
                }
                Section(planLocked ? "执行偏好（已锁）" : "执行偏好（可改）") {
                    if planLocked {
                        LabeledContent("产线", value: draft.pipeline.isEmpty ? "—" : draft.pipeline)
                        LabeledContent("执行面", value: executorLabel(draft.executor))
                        LabeledContent("复杂度", value: draft.complexity)
                        LabeledContent("升 VERSION", value: draft.bumpVersion ? "是" : "否")
                    } else {
                        TextField("产线", text: $draft.pipeline)
                        Picker("执行面", selection: $draft.executor) {
                            Text("写码").tag("opencode")
                            Text("脚本/board").tag("python")
                            Text("ollama").tag("ollama")
                            Text("cli").tag("cli")
                            Text("auto").tag("auto")
                        }
                        Picker("复杂度", selection: $draft.complexity) {
                            Text("small").tag("small")
                            Text("medium").tag("medium")
                            Text("large").tag("large")
                        }
                        Toggle("发布时升 VERSION", isOn: $draft.bumpVersion)
                    }
                    TextField(
                        planLocked ? "备注（可选：定时说明等，随卡投递）" : "备注（可选，随卡投递）",
                        text: $draft.humanNote,
                        axis: .vertical
                    )
                    .lineLimit(2...4)
                }
                Section("门禁（只读）") {
                    if draft.feasibility == "ok" || planLocked {
                        LabeledContent(
                            "可行性",
                            value: draft.feasibility == "ok"
                                ? "可执行（锁死）"
                                : "阻塞：\(draft.feasibilityReason.isEmpty ? "—" : draft.feasibilityReason)"
                        )
                    } else {
                        Picker("可行性", selection: $draft.feasibility) {
                            Text("可执行").tag("ok")
                            Text("阻塞").tag("blocked")
                        }
                        TextField("阻塞原因", text: $draft.feasibilityReason, axis: .vertical)
                            .lineLimit(2...4)
                    }
                    LabeledContent("会话", value: threadId)
                }
            }
            .formStyle(.grouped)

            if let err = draft.error {
                Text(err)
                    .font(CCCTheme.callout)
                    .foregroundStyle(CCCTheme.nodeFail)
            }

            if showRejectNote {
                TextField("退回备注", text: $rejectNote, axis: .vertical)
                    .lineLimit(2...4)
            }

            HStack(spacing: 10) {
                Button("退回对话") {
                    if showRejectNote {
                        model.commitTransferForm(threadId, draft)
                        model.rejectTransferBackToChat(threadId: threadId, note: rejectNote)
                        dismiss()
                    } else {
                        showRejectNote = true
                    }
                }
                .foregroundStyle(CCCTheme.secondary)
                Spacer()
                Button("重新预填") {
                    model.prefillTransferFromChat(threadId: threadId)
                    loadDraftFromModel()
                }
                .foregroundStyle(CCCTheme.secondary)
                Button("确认转任务") {
                    model.commitTransferForm(threadId, draft)
                    Task { await model.submitTransfer(threadId: threadId) }
                }
                .buttonStyle(.borderedProminent)
                .tint(CCCTheme.accent)
                .disabled(model.busy)
            }
        }
        .padding(24)
        .frame(width: 560, height: 720)
        .onAppear {
            guard !didLoad else { return }
            didLoad = true
            loadDraftFromModel()
        }
    }

    private var planMdSummary: String {
        let t = draft.planMd.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return "方案正文（可展开编辑）" }
        let preview = String(t.prefix(48)).replacingOccurrences(of: "\n", with: " ")
        return "方案正文 · \(preview)…"
    }

    private var planMdSummaryLocked: String {
        let t = draft.planMd.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return "方案正文（只读）" }
        let preview = String(t.prefix(48)).replacingOccurrences(of: "\n", with: " ")
        return "方案正文（只读）· \(preview)…"
    }

    private func executorLabel(_ raw: String) -> String {
        switch raw.lowercased() {
        case "python": return "脚本/board"
        case "opencode": return "写码"
        case "ollama": return "ollama"
        case "cli": return "cli"
        case "auto": return "auto"
        default: return raw.isEmpty ? "—" : raw
        }
    }

    private func loadDraftFromModel() {
        draft = model.transferForm(for: threadId)
        planExpanded = false
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
                    Text("规划（Plan · 不可改码）").tag("discuss")
                    Text("工程师（可写 · 仅 ccc）").tag("engineer")
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
                helpRow("2", "对齐基线（可选）/ 下一步", "对齐基线=深对齐，非硬门槛；「下一步」会 live 核实后再定方案。自由聊这两段都可。")
                helpRow("3", "定稿", "点「定稿」生成契约并锁方案（目标/验收/正文不可在二级卡改）。")
                helpRow("4", "转任务", "二级卡仅可改标题与备注；确认后写入待办，右侧看编排。")
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
