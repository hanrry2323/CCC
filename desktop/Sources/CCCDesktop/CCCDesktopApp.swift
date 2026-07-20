import SwiftUI

@main
struct CCCDesktopApp: App {
    @StateObject private var appModel = AppModel()

    var body: some Scene {
        WindowGroup {
            WindowRootView()
                .environmentObject(appModel)
                .frame(minWidth: 1180, minHeight: 700)
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unifiedCompact(showsTitle: false))
        .defaultSize(width: 1360, height: 860)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("新会话") { appModel.requestNewThread() }
                    .keyboardShortcut("n", modifiers: [.command])
            }
            CommandGroup(after: .newItem) {
                Button("搜索消息") { appModel.requestSearchFocus() }
                    .keyboardShortcut("f", modifiers: [.command])
                Button("转任务…") { appModel.requestOpenTransfer() }
                    .keyboardShortcut("t", modifiers: [.command, .shift])
                Divider()
                Button("对话") { appModel.requestDestination(.chat) }
                    .keyboardShortcut("1", modifiers: [.command])
                Button("看板") { appModel.requestDestination(.board) }
                    .keyboardShortcut("2", modifiers: [.command])
                Button("运维") { appModel.requestDestination(.ops) }
                    .keyboardShortcut("3", modifiers: [.command])
                Divider()
                Button("用法说明") { appModel.isHelpPresented = true }
                    .keyboardShortcut("/", modifiers: [.command, .shift])
            }
        }

        Settings {
            SettingsView()
                .environmentObject(appModel)
        }
    }
}

/// 每窗一个 WindowChatState；共享 AppModel。
/// 聊天列表 / 流式态 / 定稿条 / 右栏均按 window.threadId 隔离。
private struct WindowRootView: View {
    @EnvironmentObject var model: AppModel
    @StateObject private var window = WindowChatState()
    /// 已向 AppModel 登记的焦点（用于 refcount 差分）
    @State private var registeredFocus: String?
    @State private var registeredThread: String?

    var body: some View {
        ContentView()
            .environmentObject(model)
            .environmentObject(window)
            .onAppear {
                bindWindowProjectIfNeeded()
                syncWindowFocus()
                syncWindowThreadFocus()
            }
            .onDisappear {
                model.setWindowFocus(from: registeredFocus, to: nil)
                registeredFocus = nil
                model.setWindowThreadFocus(from: registeredThread, to: nil)
                registeredThread = nil
            }
            .onChange(of: window.projectId) { _ in
                syncWindowFocus()
            }
            .onChange(of: window.threadId) { _ in
                syncWindowThreadFocus()
            }
            .task {
                await model.bootstrap()
                bindWindowProjectIfNeeded()
                syncWindowFocus()
                syncWindowThreadFocus()
            }
    }

    private func bindWindowProjectIfNeeded() {
        if window.projectId == nil, let pid = model.selectedProjectId {
            window.projectId = pid
        }
        if let pid = window.projectId {
            let threads = ConversationStore.listThreads(projectId: pid)
            window.bindProject(pid, availableThreads: threads)
            model.ensureThreadHydrated(threadId: window.threadId ?? "")
        }
    }

    private func syncWindowFocus() {
        let next = window.projectId
        guard registeredFocus != next else { return }
        model.setWindowFocus(from: registeredFocus, to: next)
        registeredFocus = next
    }

    private func syncWindowThreadFocus() {
        let next = window.threadId
        guard registeredThread != next else { return }
        model.setWindowThreadFocus(from: registeredThread, to: next)
        registeredThread = next
    }
}
