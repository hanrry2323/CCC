import AppKit
import Combine
import SwiftUI

/// 顶栏右侧纯文字：单排、无胶囊；自绘 + Timer，保证用量刷新不依赖 SwiftUI 树
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
            // NSTitlebarAccessory 不在 SwiftUI 布局树：用 tick + 1s 兜底强制重绘
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

                let host = NSView(frame: NSRect(x: 0, y: 0, width: 520, height: 28))
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
            let warn = NSColor(calibratedRed: 0.78, green: 0.35, blue: 0.18, alpha: 1)
            let sepC = NSColor(calibratedRed: 0.165, green: 0.145, blue: 0.125, alpha: 0.30)

            let font = NSFont.monospacedSystemFont(ofSize: 13, weight: .medium)
            let fontReg = NSFont.monospacedSystemFont(ofSize: 13, weight: .regular)
            let fontSemi = NSFont.monospacedSystemFont(ofSize: 13, weight: .semibold)
            let out = NSMutableAttributedString()

            let unhealthy = model.routerUsageUnhealthy
            if unhealthy {
                out.append(NSAttributedString(
                    string: "! ",
                    attributes: [.font: fontSemi, .foregroundColor: warn]
                ))
            }

            for (i, tier) in ["flash", "code", "pro"].enumerated() {
                if i > 0 {
                    out.append(NSAttributedString(
                        string: "  ·  ",
                        attributes: [.font: fontReg, .foregroundColor: sepC]
                    ))
                }
                let total = model.routerRequestCount(tier)
                let live = model.routerLiveCount(tier)
                out.append(NSAttributedString(string: tier, attributes: [.font: font, .foregroundColor: mute]))
                out.append(NSAttributedString(
                    string: " \(total) ",
                    attributes: [.font: fontReg, .foregroundColor: unhealthy ? warn : ink]
                ))
                out.append(NSAttributedString(
                    string: live > 0 ? "+\(live)" : "·",
                    attributes: [
                        .font: fontSemi,
                        .foregroundColor: live > 0 ? green : mute,
                    ]
                ))
            }
            label.attributedText = out

            var tip = "今日总量 · +后为近一轮窗口新增（无新增显示 ·）"
            if let at = model.routerUsageFetchedAt {
                let fmt = DateFormatter()
                fmt.dateFormat = "HH:mm:ss"
                tip += " · 更新 \(fmt.string(from: at))"
            } else {
                tip += " · 尚未拉到 Hub 用量"
            }
            if let err = model.routerUsageError, !err.isEmpty {
                tip += " · \(err)"
            }
            label.toolTip = tip
            lastPaintedTick = model.routerUsageTick

            let w = ceil(out.size().width) + 20
            accessory?.view.setFrameSize(NSSize(width: max(320, w), height: 28))
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
        guard size.width > 0, size.height > 0 else { return }
        let x = max(0, bounds.width - size.width)
        let y = max(0, (bounds.height - size.height) / 2)
        attributedText.draw(at: NSPoint(x: x, y: y))
    }
}
