// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CCCDesktop",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "CCCDesktop", targets: ["CCCDesktop"]),
    ],
    targets: [
        .executableTarget(
            name: "CCCDesktop",
            path: "Sources/CCCDesktop"
        ),
    ]
)
