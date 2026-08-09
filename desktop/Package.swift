// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CCCDesktop",
    platforms: [.macOS(.v15)],
    products: [
        .executable(name: "CCCDesktop", targets: ["CCCDesktop"]),
    ],
    dependencies: [
        .package(url: "https://github.com/SwiftUIX/SwiftUIX.git", branch: "master"),
        .package(url: "https://github.com/siteline/swiftui-introspect.git", from: "1.3.0"),
        .package(url: "https://github.com/gonzalezreal/textual.git", from: "0.1.0"),
    ],
    targets: [
        .executableTarget(
            name: "CCCDesktop",
            dependencies: [
                .product(name: "SwiftUIX", package: "SwiftUIX"),
                .product(name: "SwiftUIIntrospect", package: "swiftui-introspect"),
                .product(name: "Textual", package: "textual")
            ],
            path: "Sources/CCCDesktop"
        ),
        .testTarget(
            name: "CCCDesktopTests",
            dependencies: ["CCCDesktop"]
        ),
    ]
)
