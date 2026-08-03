import XCTest
@testable import CCCDesktop

// MARK: - MockURLProtocol（注入 APIClient 两个 URLSession，serving /session + /conversation SSE）

final class MockURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (Int, Data, [String: String]))?
    static var requestLog: [URLRequest] = []
    /// 非空 → 按该序列切片分块下发（模拟网络分块边界）；空 → 一次性下发
    static var chunkSizes: [Int] = []
    /// ≥0 → 只下发前 N 字节后挂起（不 finish），用于取消测试
    static var hangAfterBytes: Int = -1

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        MockURLProtocol.requestLog.append(request)
        guard let handler = MockURLProtocol.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
            return
        }
        do {
            let (code, body, headers) = try handler(request)
            let resp = HTTPURLResponse(
                url: request.url!, statusCode: code, httpVersion: "HTTP/1.1", headerFields: headers
            )!
            client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
            let hang = MockURLProtocol.hangAfterBytes
            if hang >= 0 {
                let n = min(hang, body.count)
                if n > 0 {
                    client?.urlProtocol(self, didLoad: body.subdata(in: 0..<n))
                }
                return
            }
            let sizes = MockURLProtocol.chunkSizes
            if sizes.isEmpty {
                client?.urlProtocol(self, didLoad: body)
            } else {
                var offset = 0
                var i = 0
                while offset < body.count {
                    let take = min(sizes[i % sizes.count], body.count - offset)
                    client?.urlProtocol(self, didLoad: body.subdata(in: offset..<(offset + take)))
                    offset += take
                    i += 1
                }
            }
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }
    override func stopLoading() {}
}

private func makeClient() -> APIClient {
    APIClient(
        baseURL: URL(string: "http://localhost:7788/")!,
        user: "ccc",
        password: "ccc",
        urlProtocolClasses: [MockURLProtocol.self]
    )
}

/// 标准 handler：/session 换 token；/conversation 走闭包
private func defaultHandler(
    conversation: @escaping () throws -> (Int, Data)
) -> (URLRequest) throws -> (Int, Data, [String: String]) {
    { req in
        let path = req.url?.path ?? ""
        if path.contains("session") {
            let body = #"{"token":"tok-123","expires_at":"2099-01-01T00:00:00Z","ttl_s":3600}"#
            return (200, Data(body.utf8), ["Content-Type": "application/json"])
        }
        let (code, data) = try conversation()
        return (code, data, ["Content-Type": "text/event-stream"])
    }
}

private func sse(_ event: String, _ json: String) -> String {
    "event: \(event)\ndata: \(json)\n\n"
}

// MARK: - 打字机句读分片（AppModel.takeStreamFragment）

@MainActor
final class StreamFragmentTests: XCTestCase {

    func testEmpty() {
        let r = AppModel.takeStreamFragment("")
        XCTAssertEqual(r.reveal, "")
        XCTAssertEqual(r.rest, "")
    }

    func testShortRevealsAll() {
        let r = AppModel.takeStreamFragment("hello")
        XCTAssertEqual(r.reveal, "hello")
        XCTAssertEqual(r.rest, "")
    }

    func testChinesePunctuationCut() {
        let r = AppModel.takeStreamFragment("今天完成心智升级。随后进入拆卡阶段。")
        XCTAssertEqual(r.reveal, "今天完成心智升级。")
        XCTAssertEqual(r.rest, "随后进入拆卡阶段。")
    }

    func testEnglishPunctuationCut() {
        let r = AppModel.takeStreamFragment("First planning step. Then dispatch tasks.")
        XCTAssertEqual(r.reveal, "First planning step.")
        XCTAssertEqual(r.rest, " Then dispatch tasks.")
    }

    func testNewlineIsPunctuation() {
        let r = AppModel.takeStreamFragment("line one\nline two longer than twelve")
        XCTAssertEqual(r.reveal, "line one\n")
        XCTAssertEqual(r.rest, "line two longer than twelve")
    }

    func testSpaceFallbackAfterLongWord() {
        let s = "aaaaaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbbbbb"
        let r = AppModel.takeStreamFragment(s)
        XCTAssertEqual(r.reveal, "aaaaaaaaaaaaaaaaaaa ")
        XCTAssertEqual(r.rest, "bbbbbbbbbbbbbbbbbbb")
    }

    func testFixedWindowNoPunct() {
        let s = String(repeating: "x", count: 40)
        let r = AppModel.takeStreamFragment(s)
        XCTAssertEqual(r.reveal.count, 28)
        XCTAssertEqual(r.rest.count, 12)
    }

    func testPunctuationAtStartAdvances() {
        let r = AppModel.takeStreamFragment("。abcdefghijklmno")
        XCTAssertEqual(r.reveal, "。")
        XCTAssertEqual(r.rest, "abcdefghijklmno")
    }

    func testProgressiveReassemblyNoLoss() {
        let src = "今天完成心智升级。随后拆卡、验收与看板维护。最后复盘。"
        var pending = src
        var out = ""
        var steps = 0
        while !pending.isEmpty && steps < 100 {
            let (r, rest) = AppModel.takeStreamFragment(pending)
            out += r
            pending = rest
            steps += 1
        }
        XCTAssertEqual(out, src)
        XCTAssertLessThan(steps, 20)
    }
}

// MARK: - tool_use → 进度条 label（ToolProgressHelper.labelForToolUse）

final class ToolProgressLabelTests: XCTestCase {

    func testCommandPreferred() {
        let l = ToolProgressHelper.labelForToolUse(name: "bash", input: ["command": "ls -la /tmp"])
        XCTAssertEqual(l, "bash · ls -la /tmp")
    }

    func testFilePathFallback() {
        let l = ToolProgressHelper.labelForToolUse(name: "read", input: ["file_path": "server/web/brain.py"])
        XCTAssertEqual(l, "read · server/web/brain.py")
    }

    func testPathPrecedesPattern() {
        // 优先级：command > file_path > path > pattern > query > description
        let l = ToolProgressHelper.labelForToolUse(
            name: "grep", input: ["pattern": "def foo", "path": "/x/y"]
        )
        XCTAssertEqual(l, "grep · /x/y")
    }

    func testQueryAndDescriptionFallback() {
        XCTAssertEqual(
            ToolProgressHelper.labelForToolUse(name: "search", input: ["query": "streaming sse"]),
            "search · streaming sse"
        )
        XCTAssertEqual(
            ToolProgressHelper.labelForToolUse(name: "webfetch", input: ["description": "fetch docs"]),
            "webfetch · fetch docs"
        )
    }

    func testTruncate40WithEllipsis() {
        let long = String(repeating: "a", count: 60)
        let l = ToolProgressHelper.labelForToolUse(name: "bash", input: ["command": long])
        XCTAssertEqual(l, "bash · " + String(repeating: "a", count: 39) + "…")
    }

    func testWhitespaceCollapse() {
        let l = ToolProgressHelper.labelForToolUse(name: "bash", input: ["command": "a  b\n c"])
        XCTAssertEqual(l, "bash · a b c")
    }

    func testNoDetailUsesName() {
        XCTAssertEqual(ToolProgressHelper.labelForToolUse(name: "bash", input: [:]), "bash")
        XCTAssertEqual(ToolProgressHelper.labelForToolUse(name: "", input: [:]), "tool")
    }
}

// MARK: - APIClient.streamConversation SSE 消费（MockURLProtocol）

final class StreamConversationTests: XCTestCase {

    private let fullSSE =
        sse("meta", #"{"model":"loop/code","tools":["bash","read"],"mcp_servers":[],"skills":[]}"#)
        + sse("thinking", #"{"data":"正在思考…"}"#)
        + sse("text", #"{"text":"你好，我是大脑"}"#)
        + sse("tool_use", #"{"id":"tu1","name":"bash","input":{"command":"ls -la"}}"#)
        + sse("tool_result", #"{"tool_use_id":"tu1","content":"total 0"}"#)
        + sse("done", #"{"is_error":false,"text":"你好，我是大脑","error":""}"#)

    override func setUp() {
        super.setUp()
        MockURLProtocol.handler = nil
        MockURLProtocol.requestLog = []
        MockURLProtocol.chunkSizes = []
        MockURLProtocol.hangAfterBytes = -1
    }

    private func loginAndStream(
        _ conversation: @escaping () throws -> (Int, Data)
    ) async throws -> APIClient {
        MockURLProtocol.handler = defaultHandler(conversation: conversation)
        let client = makeClient()
        await client.configureNewServer(url: URL(string: "http://localhost:7788/"))
        _ = try await client.loginToNewServer(username: "ccc", password: "ccc")
        return client
    }

    private func collect(
        _ stream: AsyncThrowingStream<BrainStreamEvent, Error>
    ) async throws -> [BrainStreamEvent] {
        var events: [BrainStreamEvent] = []
        for try await e in stream { events.append(e) }
        return events
    }

    func testParsesFullEventSequenceInOrder() async throws {
        let client = try await loginAndStream {
            (200, Data(self.fullSSE.utf8))
        }
        let events = try await collect(await client.streamConversation(message: "hi"))

        XCTAssertEqual(events.count, 6)
        guard events.count == 6 else { return }
        XCTAssertEqual(
            events[0],
            .meta([
                "model": "loop/code", "tools": ["bash", "read"],
                "mcp_servers": [], "skills": [],
            ])
        )
        XCTAssertEqual(events[1], .thinking("正在思考…"))
        XCTAssertEqual(events[2], .text("你好，我是大脑"))
        XCTAssertEqual(events[3], .toolUse(id: "tu1", name: "bash", input: ["command": "ls -la"]))
        XCTAssertEqual(events[4], .toolResult(toolUseID: "tu1", content: "total 0"))
        XCTAssertEqual(events[5], .done(isError: false, text: "你好，我是大脑", error: ""))
    }

    func testChunkBoundariesOneByte() async throws {
        MockURLProtocol.chunkSizes = [1]
        let client = try await loginAndStream {
            (200, Data(self.fullSSE.utf8))
        }
        let events = try await collect(await client.streamConversation(message: "hi"))
        XCTAssertEqual(events.count, 6)
        XCTAssertEqual(events[2], .text("你好，我是大脑"))
        XCTAssertEqual(events[5], .done(isError: false, text: "你好，我是大脑", error: ""))
    }

    func testChunkBoundariesSplitInsideJson() async throws {
        MockURLProtocol.chunkSizes = [7, 3]
        let client = try await loginAndStream {
            (200, Data(self.fullSSE.utf8))
        }
        let events = try await collect(await client.streamConversation(message: "hi"))
        XCTAssertEqual(events.count, 6)
        XCTAssertEqual(events[3], .toolUse(id: "tu1", name: "bash", input: ["command": "ls -la"]))
    }

    func testRequestCarriesStreamBodyAndAuth() async throws {
        let client = try await loginAndStream {
            (200, Data(self.fullSSE.utf8))
        }
        _ = try await collect(await client.streamConversation(message: "hi"))

        guard let req = MockURLProtocol.requestLog.last else {
            return XCTFail("无 /conversation 请求")
        }
        XCTAssertEqual(req.url?.path, "/conversation")
        XCTAssertEqual(req.httpMethod, "POST")
        XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer tok-123")
        let bodyObj = try JSONSerialization.jsonObject(
            with: requestBody(req)
        ) as? [String: Any]
        XCTAssertEqual(bodyObj?["message"] as? String, "hi")
        XCTAssertEqual(bodyObj?["stream"] as? Bool, true)
    }

    private func requestBody(_ req: URLRequest) -> Data {
        if let body = req.httpBody { return body }
        guard let stream = req.httpBodyStream else { return Data() }
        stream.open()
        defer { stream.close() }
        var data = Data()
        var buf = [UInt8](repeating: 0, count: 1024)
        while stream.hasBytesAvailable {
            let n = stream.read(&buf, maxLength: buf.count)
            if n <= 0 { break }
            data.append(buf, count: n)
        }
        return data
    }

    func test401ThrowsAndClearsToken() async throws {
        let client = try await loginAndStream {
            (401, Data("unauthorized".utf8))
        }
        do {
            _ = try await collect(await client.streamConversation(message: "hi"))
            XCTFail("应抛 401")
        } catch let err as APIError {
            XCTAssertEqual(err.httpStatus, 401)
        }
    }

    func test500ThrowsWithBody() async throws {
        let client = try await loginAndStream {
            (500, Data("brain exploded".utf8))
        }
        do {
            _ = try await collect(await client.streamConversation(message: "hi"))
            XCTFail("应抛 500")
        } catch let err as APIError {
            XCTAssertEqual(err.httpStatus, 500)
            XCTAssertEqual(err.errorDescription, "HTTP 500: brain exploded")
        }
    }

    func testDoneIsErrorParsing() async throws {
        let sseBody =
            sse("text", #"{"text":"partial"}"#)
            + sse("done", #"{"is_error":true,"text":"","error":"brain failed"}"#)
        let client = try await loginAndStream {
            (200, Data(sseBody.utf8))
        }
        let events = try await collect(await client.streamConversation(message: "hi"))
        XCTAssertEqual(events.count, 2)
        XCTAssertEqual(events[1], .done(isError: true, text: "", error: "brain failed"))
    }

    func testErrorEventParsing() async throws {
        let client = try await loginAndStream {
            (200, Data(sse("error", #"{"status":504,"message":"brain timeout"}"#).utf8))
        }
        let events = try await collect(await client.streamConversation(message: "hi"))
        XCTAssertEqual(events, [.error(status: 504, message: "brain timeout")])
    }

    func testUnknownEventSkipped() async throws {
        let sseBody =
            sse("ping", #"{"x":1}"#)
            + sse("text", #"{"text":"ok"}"#)
            + sse("done", #"{"is_error":false,"text":"ok","error":""}"#)
        let client = try await loginAndStream {
            (200, Data(sseBody.utf8))
        }
        let events = try await collect(await client.streamConversation(message: "hi"))
        XCTAssertEqual(events.count, 2)
        XCTAssertEqual(events[0], .text("ok"))
    }

    func testEmptyBodyNoEvents() async throws {
        let client = try await loginAndStream {
            (200, Data())
        }
        let events = try await collect(await client.streamConversation(message: "hi"))
        XCTAssertTrue(events.isEmpty)
    }

    func testCancellationFinishesWithoutError() async throws {
        // 先登录（hang 关闭），再对 /conversation 挂起不 finish → 取消不得抛错
        let client = try await loginAndStream {
            (200, Data())
        }
        MockURLProtocol.handler = defaultHandler {
            (200, Data(self.fullSSE.utf8))
        }
        MockURLProtocol.hangAfterBytes = Int.max
        let stream = await client.streamConversation(message: "hi")
        let task = Task {
            var events: [BrainStreamEvent] = []
            do {
                for try await e in stream { events.append(e) }
                return (events, nil as Error?)
            } catch {
                return (events, error)
            }
        }
        try await Task.sleep(nanoseconds: 200_000_000)
        task.cancel()
        let (events, error) = await task.value
        XCTAssertNil(error, "取消不应抛错，实际: \(String(describing: error))")
        XCTAssertTrue(events.isEmpty || events.first == .meta([
            "model": "loop/code", "tools": ["bash", "read"],
            "mcp_servers": [], "skills": [],
        ]))
    }
}
