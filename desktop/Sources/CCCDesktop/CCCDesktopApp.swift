import SwiftUI

@main
struct CCCDesktopApp: App {
    @StateObject private var appModel = AppModel()

    var body: some Scene {
        WindowGroup("CCC") {
            ContentView()
                .environmentObject(appModel)
                .frame(minWidth: 1100, minHeight: 640)
        }
        .defaultSize(width: 1280, height: 800)

        Settings {
            SettingsView()
                .environmentObject(appModel)
        }
    }
}
