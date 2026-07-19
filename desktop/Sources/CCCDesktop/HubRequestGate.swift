import Foundation

/// Hub 短请求闸门：限制并发，避免把单进程 uvicorn 打满
actor HubRequestGate {
    static let shared = HubRequestGate()

    private let maxConcurrent = 2
    private var inFlight = 0
    /// 环形队列：head 前进代替 removeFirst，避免 O(n) 搬移
    private var waiters: [CheckedContinuation<Void, Never>] = []
    private var waiterHead = 0

    func withPermit<T: Sendable>(_ body: @Sendable () async throws -> T) async throws -> T {
        await acquire()
        defer { release() }
        return try await body()
    }

    private func acquire() async {
        if inFlight < maxConcurrent {
            inFlight += 1
            return
        }
        await withCheckedContinuation { cont in
            waiters.append(cont)
        }
        inFlight += 1
    }

    private func release() {
        inFlight = max(0, inFlight - 1)
        if waiterHead < waiters.count {
            let w = waiters[waiterHead]
            waiterHead += 1
            if waiterHead > 32, waiterHead * 2 >= waiters.count {
                waiters.removeFirst(waiterHead)
                waiterHead = 0
            }
            w.resume()
        }
    }
}
