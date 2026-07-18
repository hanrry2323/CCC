import AppKit
import SwiftUI

/// Codex 三栏 + 系统材质侧栏 + 隐藏标题栏（高级感主来源）
struct ContentView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        ZStack(alignment: .top) {
            HStack(spacing: 0) {
                CodexSidebar()
                    .frame(width: 260)
                    .cccHairline(.trailing)

                CodexChatPane()
                    .frame(minWidth: 480)

                FlowRail()
                    .frame(minWidth: 280, idealWidth: 320, maxWidth: 380)
                    .cccHairline(.leading)
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

                SoftRow(title: "看板", icon: "square.grid.2x2") {
                    model.selectDestination(.hub)
                }
                SoftRow(title: "运维", icon: "wrench.and.screwdriver") {
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
        .background(VibrancyBackground(material: .sidebar))
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
                        selected: on
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

// MARK: - Chat

struct CodexChatPane: View {
    @EnvironmentObject var model: AppModel
    @FocusState private var composerFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Circle()
                    .fill(model.connected ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                    .frame(width: 6, height: 6)
                Text(model.connected ? model.statusText : "未连接")
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.faint)
                Spacer(minLength: 0)
                if model.busy {
                    ProgressView().controlSize(.mini)
                }
            }
            .padding(.horizontal, 28)
            .padding(.top, 10)
            .padding(.bottom, 6)

            if !model.connected {
                Spacer()
                VStack(spacing: 8) {
                    Text("连接后开始对话")
                        .font(CCCTheme.title)
                        .tracking(-0.8)
                    Text("在设置中配置 Server")
                        .font(.system(size: 14))
                        .foregroundStyle(CCCTheme.faint)
                    Button("重试") { Task { await model.reconnect() } }
                        .buttonStyle(.borderedProminent)
                        .tint(CCCTheme.accent)
                        .controlSize(.small)
                        .padding(.top, 6)
                }
                Spacer()
            } else {
                ScrollViewReader { proxy in
                    ScrollView(showsIndicators: false) {
                        LazyVStack(alignment: .leading, spacing: 26) {
                            if model.messages.isEmpty {
                                emptyHero
                            }
                            ForEach(model.messages) { msg in
                                CodexMessageRow(message: msg).id(msg.id)
                            }
                        }
                        .frame(maxWidth: CCCTheme.chatMaxWidth)
                        .frame(maxWidth: .infinity)
                        .padding(.horizontal, 40)
                        .padding(.top, 4)
                        .padding(.bottom, 28)
                    }
                    .onChange(of: model.messages.count) { _ in scroll(proxy) }
                    .onChange(of: model.messages.last?.content) { _ in scroll(proxy) }
                }

                composer
            }
        }
        .background(CCCTheme.chatBg)
    }

    private func scroll(_ proxy: ScrollViewProxy) {
        guard let last = model.messages.last else { return }
        withAnimation(.easeOut(duration: 0.14)) {
            proxy.scrollTo(last.id, anchor: .bottom)
        }
    }

    private var emptyHero: some View {
        VStack(spacing: 10) {
            Spacer().frame(height: 120)
            Text("有什么可以帮忙的？")
                .font(CCCTheme.title)
                .tracking(-0.9)
                .foregroundStyle(CCCTheme.ink)
            Text("说明目标与验收，再转任务给编排引擎。")
                .font(.system(size: 14))
                .foregroundStyle(CCCTheme.faint)
            Spacer().frame(height: 56)
        }
        .frame(maxWidth: .infinity)
    }

    private var composer: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 0) {
                // 工具条藏进输入框上沿——少一层「胶囊按钮」廉价感
                HStack(spacing: 12) {
                    Button {
                        model.openTransferSheet()
                    } label: {
                        Text("转任务")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(
                                model.selectedProject?.isDispatchable == true
                                    ? CCCTheme.secondary
                                    : CCCTheme.faint
                            )
                    }
                    .buttonStyle(.plain)
                    .disabled(model.selectedProject?.isDispatchable != true)

                    if model.busy {
                        ProgressView().controlSize(.mini)
                    }
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 2)

                HStack(alignment: .bottom, spacing: 10) {
                    ZStack(alignment: .topLeading) {
                        if model.draft.isEmpty {
                            Text("问任何问题…")
                                .font(CCCTheme.body)
                                .foregroundStyle(CCCTheme.faint)
                                .padding(.top, 10)
                                .padding(.leading, 5)
                                .allowsHitTesting(false)
                        }
                        TextEditor(text: $model.draft)
                            .font(CCCTheme.body)
                            .focused($composerFocused)
                            .frame(minHeight: 44, maxHeight: 140)
                            .padding(.vertical, 6)
                            .scrollContentBackground(.hidden)
                    }

                    Button {
                        Task { await model.sendMessage() }
                    } label: {
                        Image(systemName: "arrow.up")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundStyle(canSend ? Color(nsColor: .textBackgroundColor) : CCCTheme.faint)
                            .frame(width: 30, height: 30)
                            .background(
                                Circle().fill(canSend ? CCCTheme.accent : CCCTheme.hover)
                            )
                    }
                    .buttonStyle(.plain)
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(!canSend)
                    .padding(.bottom, 10)
                    .padding(.trailing, 10)
                    .animation(.easeOut(duration: 0.12), value: canSend)
                }
                .padding(.leading, 12)
            }
            .background(
                RoundedRectangle(cornerRadius: CCCTheme.radiusComposer, style: .continuous)
                    .fill(Color(nsColor: .controlBackgroundColor))
            )
            .overlay(
                RoundedRectangle(cornerRadius: CCCTheme.radiusComposer, style: .continuous)
                    .stroke(
                        composerFocused ? CCCTheme.borderStrong : CCCTheme.border,
                        lineWidth: 1
                    )
            )
            .shadow(color: .black.opacity(composerFocused ? 0.07 : 0.04), radius: composerFocused ? 28 : 18, y: 8)
            .animation(.easeOut(duration: 0.15), value: composerFocused)
            .frame(maxWidth: CCCTheme.chatMaxWidth)
            .frame(maxWidth: .infinity)
        }
        .padding(.horizontal, 40)
        .padding(.bottom, 22)
        .padding(.top, 6)
    }

    private var canSend: Bool {
        !model.busy && !model.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}

struct CodexMessageRow: View {
    let message: ChatMessage

    var body: some View {
        let isUser = message.role == "user"
        HStack(alignment: .top, spacing: 0) {
            if isUser {
                Spacer(minLength: 64)
                Text(message.content)
                    .font(CCCTheme.body)
                    .lineSpacing(3.5)
                    .textSelection(.enabled)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .fill(CCCTheme.bubbleUser)
                    )
            } else {
                Text(message.content.isEmpty && message.isStreaming ? "…" : message.content)
                    .font(CCCTheme.body)
                    .lineSpacing(4.5)
                    .textSelection(.enabled)
                    .foregroundStyle(CCCTheme.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if message.isStreaming {
                    ProgressView().controlSize(.mini).padding(.leading, 6)
                }
                Spacer(minLength: 40)
            }
        }
    }
}

// MARK: - Flow rail

struct FlowRail: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Color.clear.frame(height: CCCTheme.trafficLightInset - 16)

            if !model.recentEpics.isEmpty {
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
                    HStack(spacing: 6) {
                        Text(currentEpicLabel)
                            .font(.system(size: 12))
                            .lineLimit(1)
                        Image(systemName: "chevron.down")
                            .font(.system(size: 8, weight: .semibold))
                            .foregroundStyle(CCCTheme.faint)
                        Spacer(minLength: 0)
                    }
                    .foregroundStyle(CCCTheme.secondary)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 6)
                }
            }

            FlowCanvasView(
                epic: model.flowEpic,
                epicId: model.currentEpicId,
                works: model.flowWorks,
                headline: model.flowHeadline,
                emptyMessage: model.flowEmptyMessage,
                onOpenOps: { model.openHubInBrowser(route: "#/ops") },
                onSelectNode: { model.openNodeDetail(id: $0) }
            )
        }
        .background(VibrancyBackground(material: .sidebar))
        .sheet(item: $model.selectedNodeDetail) { detail in
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(detail.kind == "epic" ? "大卡" : "步骤")
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
                    Button("在 Hub 运维中查看") {
                        model.dismissNodeDetail()
                        model.openHubInBrowser(route: "#/ops")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(CCCTheme.accent)
                }
            }
            .padding(22)
            .frame(width: 420, height: 360)
        }
    }

    private var currentEpicLabel: String {
        if let cur = model.recentEpics.first(where: { $0.epic_id == model.currentEpicId }) {
            return cur.title ?? cur.epic_id
        }
        return model.flowEpic?.title ?? model.currentEpicId ?? "选择编排"
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
            TextField("Server", text: $model.serverURLString)
            TextField("用户", text: $model.authUser)
            SecureField("密码", text: $model.authPass)
            Button("重新连接") { Task { await model.reconnect() } }
        }
        .padding(20)
        .frame(width: 400, height: 200)
    }
}
