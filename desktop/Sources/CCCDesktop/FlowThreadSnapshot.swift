import Foundation

/// 单会话右栏编排快照（本地缓存，与对话消息隔离）
struct FlowThreadSnapshot {
    var epicId: String?
    var epic: FlowEpic?
    var works: [FlowWork]
    var headline: String
    var recentEpics: [FlowEpicRef]
    var emptyMessage: String
    var fanoutHint: String?
}
