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

/// 每窗一个 WindowChatState；共享 AppModel。新窗不抢第一窗可见历史。
private struct WindowRootView: View {
    @EnvironmentObject var model: AppModel
    @StateObject private var window = WindowChatState()

    var body: some View {
        ContentView()
            .environmentObject(model)
            .environmentObject(window)
            .onAppear {
                bindWindowProjectIfNeeded()
            }
            .task {
                await model.bootstrap()
                bindWindowProjectIfNeeded()
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
}
