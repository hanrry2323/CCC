import AppKit
import SwiftUI

/// 顶栏右侧纯文字：单排、无胶囊；自绘以保证上下居中
struct TitlebarUsageAccessory: NSViewRepresentable {
    @ObservedObject var model: AppModel

    func makeCoordinator() -> Coordinator { Coordinator(model: model) }

    func makeNSView(context: Context) -> NSView {
        let anchor = NSView(frame: .zero)
        anchor.isHidden = true
        context.coordinator.installIfNeeded(from: anchor)
        return anchor
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        context.coordinator.model = model
        context.coordinator.installIfNeeded(from: nsView)
        context.coordinator.refresh()
    }

    @MainActor
    final class Coordinator {
        var model: AppModel
        private weak var accessory: NSTitlebarAccessoryViewController?
        private weak var label: VerticallyCenteredTextView?

        init(model: AppModel) { self.model = model }

        func installIfNeeded(from anchor: NSView) {
            guard accessory == nil else { return }
            DispatchQueue.main.async { [weak self, weak anchor] in
                guard let self, let anchor, let window = anchor.window else { return }
                guard self.accessory == nil else { return }

                while !window.titlebarAccessoryViewControllers.isEmpty {
                    window.removeTitlebarAccessoryViewController(at: 0)
                }

                let field = VerticallyCenteredTextView(frame: .zero)
                field.setContentHuggingPriority(.required, for: .horizontal)

                // height 交给系统顶栏；自绘视图在 bounds 内上下居中
                let host = NSView(frame: NSRect(x: 0, y: 0, width: 480, height: 28))
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
                out.append(NSAttributedString(string: " \(total) ", attributes: [.font: fontReg, .foregroundColor: ink]))
                out.append(NSAttributedString(
                    string: live > 0 ? "+\(live)" : "·",
                    attributes: [
                        .font: fontSemi,
                        .foregroundColor: live > 0 ? green : mute,
                    ]
                ))
            }
            label.attributedText = out
            label.toolTip = "今日总量 · +后为近 5 秒内新增（无新增显示 ·，非故障）"
            let w = ceil(out.size().width) + 20
            accessory?.view.setFrameSize(NSSize(width: max(300, w), height: 28))
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
