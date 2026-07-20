import Foundation
import UserNotifications

@MainActor
enum NotificationManager {
    static let categoryTaskEvent = "ccc_task_event"

    static func requestAuthorization() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { granted, _ in
            if granted {
                Task { await registerCategories() }
            }
        }
    }

    private static func registerCategories() {
        let openAction = UNNotificationAction(
            identifier: "open_board",
            title: "打开看板",
            options: .foreground
        )
        let category = UNNotificationCategory(
            identifier: categoryTaskEvent,
            actions: [openAction],
            intentIdentifiers: []
        )
        UNUserNotificationCenter.current().setNotificationCategories([category])
    }

    static func notify(
        title: String,
        body: String,
        threadId: String? = nil,
        userInfo: [AnyHashable: Any] = [:]
    ) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        content.categoryIdentifier = categoryTaskEvent
        if !userInfo.isEmpty {
            content.userInfo = userInfo
        }
        let requestId = threadId ?? UUID().uuidString
        let request = UNNotificationRequest(
            identifier: "ccc-\(requestId)",
            content: content,
            trigger: nil
        )
        UNUserNotificationCenter.current().add(request)
    }

    static func notifyTaskCreated(title: String, projectId: String) {
        notify(
            title: "任务已创建",
            body: "「\(title)」已在 \(projectId) 中创建",
            userInfo: ["project_id": projectId]
        )
    }

    static func notifyWorkFailed(workTitle: String, epicTitle: String?) {
        notify(
            title: "Work 执行异常",
            body: "「\(epicTitle ?? "") → \(workTitle)」执行失败，请检查",
            userInfo: ["work": workTitle]
        )
    }

    static func notifyWorkCompleted(workTitle: String, epicTitle: String?) {
        notify(
            title: "Work 已完成",
            body: "「\(epicTitle ?? "") → \(workTitle)」已验收通过",
            userInfo: ["work": workTitle]
        )
    }
}
