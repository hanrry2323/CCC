// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CCCDesktop",
    platforms: [.macOS(.v15)],
    products: [
        .executable(name: "CCCDesktop", targets: ["CCCDesktop"]),
    ],
    targets: [
        .executableTarget(
            name: "CCCDesktop",
            path: "Sources/CCCDesktop"
        ),
        .testTarget(
            name: "CCCDesktopTests",
            dependencies: ["CCCDesktop"]
        ),
    ]
)
