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

/// 每窗一个 WindowChatState；共享 AppModel
private struct WindowRootView: View {
    @EnvironmentObject var model: AppModel
    @StateObject private var window = WindowChatState()

    var body: some View {
        ContentView()
            .environmentObject(model)
            .environmentObject(window)
            .task {
                await model.bootstrap()
                if window.projectId == nil {
                    window.projectId = model.selectedProjectId
                }
            }
    }
}
