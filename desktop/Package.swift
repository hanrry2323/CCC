// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CCCDesktop",
    platforms: [.macOS(.v15)],
    products: [
        .executable(name: "CCCDesktop", targets: ["CCCDesktop"]),
    ],
    dependencies: [
        .package(url: "https://github.com/gonzalezreal/textual.git", branch: "main")
    ],
    targets: [
        .executableTarget(
            name: "CCCDesktop",
            dependencies: [
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
