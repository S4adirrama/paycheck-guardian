import SwiftUI

@main
struct PaycheckGuardianAppEntry: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView(model: model)
        }
    }
}
