import SwiftUI

@main
struct CCCDesktopApp: App {
    @StateObject private var appModel = AppModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appModel)
                .frame(minWidth: 1180, minHeight: 700)
        }
        // hiddenTitleBar 在部分环境会抢键盘；改用统一标题栏保证可输入
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unifiedCompact(showsTitle: false))
        .defaultSize(width: 1360, height: 860)

        Settings {
            SettingsView()
                .environmentObject(appModel)
        }
    }
}
