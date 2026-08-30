import SwiftUI

struct RootView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        ZStack {
            AppPalette.background.ignoresSafeArea()
            switch model.route {
            case .welcome:
                WelcomeView(model: model)
            case .setup:
                SetupView(model: model)
            case .analyzing:
                VStack(spacing: 18) {
                    ProgressView().controlSize(.large)
                    Text("Verifying the evidence…")
                        .font(.headline)
                    Text("Everything stays on this device.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .combine)
            case .plan:
                PlanView(model: model)
            case .trace:
                TraceView(model: model)
            }
        }
        .tint(AppPalette.blue)
        .animation(.easeInOut(duration: 0.22), value: model.route)
    }
}
