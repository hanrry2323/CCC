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

        Settings {
            SettingsView()
                .environmentObject(appModel)
        }
    }
}

/// 每窗一个 WindowChatState；共享 AppModel（OpenCode：共享 session map，每窗选自己的 session）。
/// 聊天列表 / 流式态 / 定稿条 / 右栏均按 window.projectId → `{id}::main` 隔离。
private struct WindowRootView: View {
    @EnvironmentObject var model: AppModel
    @StateObject private var window = WindowChatState()
    /// 已向 AppModel 登记的焦点（用于 refcount 差分）
    @State private var registeredFocus: String?

    var body: some View {
        ContentView()
            .environmentObject(model)
            .environmentObject(window)
            .onAppear {
                bindWindowProjectIfNeeded()
                syncWindowFocus()
            }
            .onDisappear {
                model.setWindowFocus(from: registeredFocus, to: nil)
                registeredFocus = nil
            }
            .onChange(of: window.projectId) { _ in
                syncWindowFocus()
            }
            .task {
                await model.bootstrap()
                bindWindowProjectIfNeeded()
                syncWindowFocus()
            }
    }

    private func bindWindowProjectIfNeeded() {
        // 仅本窗尚未绑定时落到全局选中；已有 projectId 的窗绝不被 bootstrap/他窗切项改写
        if window.projectId == nil, let pid = model.selectedProjectId {
            window.projectId = pid
        }
        if let pid = window.projectId {
            model.ensureThreadHydrated(projectId: pid)
        }
    }

    private func syncWindowFocus() {
        let next = window.projectId
        guard registeredFocus != next else { return }
        model.setWindowFocus(from: registeredFocus, to: next)
        registeredFocus = next
    }
}
