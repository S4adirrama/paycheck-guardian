// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "PaycheckGuardianCore",
    platforms: [
        .iOS(.v17),
        .macOS(.v13),
    ],
    products: [
        .library(name: "PaycheckGuardianCore", targets: ["PaycheckGuardianCore"]),
        .executable(name: "PaycheckGuardianEvaluation", targets: ["PaycheckGuardianEvaluation"]),
    ],
    targets: [
        .target(
            name: "PaycheckGuardianCore",
            resources: [.process("Resources")]
        ),
        .executableTarget(
            name: "PaycheckGuardianEvaluation",
            dependencies: ["PaycheckGuardianCore"]
        ),
        .testTarget(
            name: "PaycheckGuardianCoreTests",
            dependencies: ["PaycheckGuardianCore"]
        ),
    ]
)
