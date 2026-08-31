import XCTest

@MainActor
final class PaycheckGuardianUITests: XCTestCase {
    private func launchApp(arguments: [String] = ["--ui-testing", "--reset-demo"]) -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = arguments
        app.launch()
        return app
    }

    func testHackathonDemoEndToEnd() {
        let app = launchApp()
        let runDemo = app.buttons["run-demo"]
        XCTAssertTrue(runDemo.waitForExistence(timeout: 3))
        runDemo.tap()

        XCTAssertTrue(app.staticTexts["verified-plan-title"].waitForExistence(timeout: 10))
        app.buttons["recommendation-evidence-0"].tap()
        XCTAssertTrue(app.staticTexts["calculation-detail"].waitForExistence(timeout: 3))
        app.buttons["close-evidence"].tap()
        app.buttons["approve-recommendation-0"].tap()
        XCTAssertTrue(app.buttons["confirm-simulation"].waitForExistence(timeout: 3))
        app.buttons["confirm-simulation"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["simulation-confirmed"].waitForExistence(timeout: 3))
        app.buttons["show-agent-trace"].tap()
        XCTAssertTrue(app.staticTexts["agent-trace-title"].waitForExistence(timeout: 3))
    }

    func testDismissalUpdatesCardsAndTotal() {
        let app = launchApp()
        app.buttons["run-demo"].tap()
        XCTAssertTrue(app.staticTexts["verified-plan-title"].waitForExistence(timeout: 10))
        let total = app.staticTexts["next-paycheck-total"].label
        let cardsBefore = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'recommendation-evidence-'")).count

        app.buttons["dismiss-recommendation-0"].tap()

        XCTAssertLessThan(
            app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'recommendation-evidence-'")).count,
            cardsBefore
        )
        XCTAssertNotEqual(app.staticTexts["next-paycheck-total"].label, total)
    }

    func testSameDayPaycheckIsRejected() {
        let app = launchApp(arguments: ["--ui-testing", "--invalid-dates"])

        XCTAssertTrue(app.buttons["analyze-transactions"].waitForExistence(timeout: 3))
        app.buttons["analyze-transactions"].tap()

        XCTAssertTrue(app.staticTexts["validation-error"].waitForExistence(timeout: 3))
    }

    func testCaptureHackathonScreens() {
        let app = launchApp()
        attachScreen(named: "01-welcome")

        app.buttons["run-demo"].tap()
        XCTAssertTrue(app.staticTexts["verified-plan-title"].waitForExistence(timeout: 10))
        attachScreen(named: "02-verified-plan")

        app.buttons["recommendation-evidence-0"].tap()
        XCTAssertTrue(app.staticTexts["calculation-detail"].waitForExistence(timeout: 3))
        attachScreen(named: "03-evidence")
        app.buttons["close-evidence"].tap()

        app.buttons["approve-recommendation-0"].tap()
        app.buttons["confirm-simulation"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["simulation-confirmed"].waitForExistence(timeout: 3))
        attachScreen(named: "04-simulated-approval")

        app.buttons["show-agent-trace"].tap()
        XCTAssertTrue(app.staticTexts["agent-trace-title"].waitForExistence(timeout: 3))
        attachScreen(named: "05-agent-trace")
    }

    private func attachScreen(named name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
