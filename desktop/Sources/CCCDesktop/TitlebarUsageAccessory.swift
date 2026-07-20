import AppKit
import Combine
import SwiftUI

/// 顶栏右侧：本机 Agent 大模型调用 — 今日总量 · 近 5 秒
struct TitlebarUsageAccessory: NSViewRepresentable {
    @ObservedObject var model: AppModel

    func makeCoordinator() -> Coordinator { Coordinator(model: model) }

    func makeNSView(context: Context) -> NSView {
        let anchor = NSView(frame: .zero)
        anchor.isHidden = true
        context.coordinator.model = model
        context.coordinator.installIfNeeded(from: anchor)
        context.coordinator.startObserving()
        return anchor
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        context.coordinator.model = model
        context.coordinator.installIfNeeded(from: nsView)
        context.coordinator.refresh()
    }

    static func dismantleNSView(_ nsView: NSView, coordinator: Coordinator) {
        coordinator.stopObserving()
    }

    @MainActor
    final class Coordinator {
        var model: AppModel
        private weak var accessory: NSTitlebarAccessoryViewController?
        private weak var label: VerticallyCenteredTextView?
        private var timer: Timer?
        private var cancellable: AnyCancellable?
        private var lastPaintedTick: UInt64 = 0

        init(model: AppModel) { self.model = model }

        func startObserving() {
            stopObserving()
            cancellable = model.objectWillChange
                .receive(on: RunLoop.main)
                .sink { [weak self] _ in
                    self?.refresh()
                }
            timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    self?.refresh()
                }
            }
            if let timer {
                RunLoop.main.add(timer, forMode: .common)
            }
        }

        func stopObserving() {
            timer?.invalidate()
            timer = nil
            cancellable?.cancel()
            cancellable = nil
        }

        func installIfNeeded(from anchor: NSView) {
            if accessory != nil, label != nil { return }
            DispatchQueue.main.async { [weak self, weak anchor] in
                guard let self, let anchor, let window = anchor.window else { return }
                if self.accessory != nil, self.label != nil {
                    self.refresh()
                    return
                }

                while !window.titlebarAccessoryViewControllers.isEmpty {
                    window.removeTitlebarAccessoryViewController(at: 0)
                }

                let field = VerticallyCenteredTextView(frame: .zero)
                field.setContentHuggingPriority(.required, for: .horizontal)

                let host = NSView(frame: NSRect(x: 0, y: 0, width: 280, height: 28))
                host.addSubview(field)
                field.translatesAutoresizingMaskIntoConstraints = false
                NSLayoutConstraint.activate([
                    field.leadingAnchor.constraint(equalTo: host.leadingAnchor),
                    field.trailingAnchor.constraint(equalTo: host.trailingAnchor, constant: -8),
                    field.topAnchor.constraint(equalTo: host.topAnchor),
                    field.bottomAnchor.constraint(equalTo: host.bottomAnchor),
                ])

                let vc = NSTitlebarAccessoryViewController()
                vc.view = host
                vc.layoutAttribute = .right
                window.addTitlebarAccessoryViewController(vc)
                self.accessory = vc
                self.label = field
                self.refresh()
            }
        }

        func refresh() {
            guard let label else { return }
            let ink = NSColor(calibratedRed: 0.165, green: 0.145, blue: 0.125, alpha: 0.82)
            let mute = NSColor(calibratedRed: 0.42, green: 0.38, blue: 0.34, alpha: 1)
            let green = NSColor(calibratedRed: 0.28, green: 0.58, blue: 0.38, alpha: 1)
            let sepC = NSColor(calibratedRed: 0.165, green: 0.145, blue: 0.125, alpha: 0.30)

            let font = NSFont.monospacedSystemFont(ofSize: 13, weight: .medium)
            let fontReg = NSFont.monospacedSystemFont(ofSize: 13, weight: .regular)
            let fontSemi = NSFont.monospacedSystemFont(ofSize: 13, weight: .semibold)
            let out = NSMutableAttributedString()

            let daily = model.agentLLMDailyCount
            let recent = model.agentLLMRecent5s

            out.append(NSAttributedString(string: "今日", attributes: [.font: font, .foregroundColor: mute]))
            out.append(NSAttributedString(
                string: " \(daily)",
                attributes: [.font: fontReg, .foregroundColor: ink]
            ))
            out.append(NSAttributedString(
                string: "  ·  ",
                attributes: [.font: fontReg, .foregroundColor: sepC]
            ))
            out.append(NSAttributedString(string: "5s", attributes: [.font: font, .foregroundColor: mute]))
            out.append(NSAttributedString(
                string: " \(recent)",
                attributes: [
                    .font: fontSemi,
                    .foregroundColor: recent > 0 ? green : ink,
                ]
            ))
            label.attributedText = out

            var tip = "本机 Agent 大模型调用（sidecar → MiniMax）· 每发起一轮对话计 1 次（含自动重试）"
            tip += " · 今日 \(daily) · 近 5 秒 \(recent)"
            label.toolTip = tip
            lastPaintedTick = model.agentUsageTick

            let w = ceil(out.size().width) + 20
            accessory?.view.setFrameSize(NSSize(width: max(160, w), height: 28))
        }
    }
}

/// 在 bounds 内水平右对齐、垂直居中绘制
private final class VerticallyCenteredTextView: NSView {
    var attributedText: NSAttributedString = NSAttributedString() {
        didSet { needsDisplay = true }
    }

    override var isFlipped: Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        let size = attributedText.size()
        let x = max(0, bounds.width - size.width)
        let y = max(0, (bounds.height - size.height) / 2)
        attributedText.draw(at: NSPoint(x: x, y: y))
    }
}
