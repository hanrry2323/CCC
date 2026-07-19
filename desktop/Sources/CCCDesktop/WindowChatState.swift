import Foundation
import SwiftUI

/// 每个 macOS 窗口独立的项目焦点（多窗可同时看不同项目、并行流式）。
/// 对齐 OpenCode：UI 按 sessionID 绑定；共享 AppModel 的 `threadMessages[tid]` map，
/// 本对象只绑「本窗在看谁」。禁止用全局 `chat.messages` 当显示源。
@MainActor
final class WindowChatState: ObservableObject {
    @Published var projectId: String?
    /// 每窗独立导航（对话 / 看板 / 运维），禁止全局 destination 串窗
    @Published var destination: SidebarDestination = .chat

    var threadId: String? {
        projectId.map { LocalSessionStore.conversationThreadId(for: $0) }
    }
}
