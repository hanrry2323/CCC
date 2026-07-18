import Foundation

/// Hub 短请求闸门：限制并发，避免把单进程 uvicorn 打满
actor HubRequestGate {
    static let shared = HubRequestGate()

    private let maxConcurrent = 2
    private var inFlight = 0
    private var waiters: [CheckedContinuation<Void, Never>] = []

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
        if !waiters.isEmpty {
            let w = waiters.removeFirst()
            w.resume()
        }
    }
}
