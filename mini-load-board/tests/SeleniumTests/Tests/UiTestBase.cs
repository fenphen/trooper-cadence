using OpenQA.Selenium;
using SeleniumTests.Drivers;
using SeleniumTests.Support;

namespace SeleniumTests.Tests;

/// <summary>
/// Opens a fresh browser before each test and closes it afterwards, so tests
/// never leak state (cookies, open pages) into each other.
///
/// ---------------------------------------------------------------------------
/// Selenium vs Playwright - the short version for an interview:
///
///  * Waiting. Selenium finds elements immediately and you add explicit waits
///    (WebDriverWait) where the page is still changing. Playwright "auto-waits":
///    every action and every expect() retries until the element is ready, so
///    most waits disappear from the test code.
///  * Locators. Selenium gives you By.CssSelector/XPath/Id; role- and text-based
///    lookups mean hand-written XPath. Playwright ships getByRole/getByTestId/
///    getByText, which track how users and screen readers perceive the page.
///  * Driver setup. Selenium speaks the W3C WebDriver protocol to a separate
///    chromedriver process (Selenium Manager now downloads it for you).
///    Playwright talks to the browser directly over the DevTools protocol and
///    bundles its own browser builds - faster start-up, fewer version mismatches.
///  * Ecosystem. Selenium is the 15-year-old standard with bindings in every
///    language and the broadest grid/cloud support (Selenium Grid, BrowserStack,
///    Sauce Labs). Playwright includes its own test runner, tracing, parallel
///    workers, API testing and HTML reports out of the box.
///  * Browser-side state. Playwright can intercept network requests and run
///    tests in isolated browser contexts; Selenium 4 added BiDi/CDP support but
///    it is less mature.
///
/// Both drive real browsers and both can use the Page Object Model - compare
/// this folder with tests/playwright/pages to see the same pages in each style.
/// ---------------------------------------------------------------------------
/// </summary>
public abstract class UiTestBase
{
    protected static readonly string BaseUrl =
        Environment.GetEnvironmentVariable("LOADBOARD_URL") ?? "http://localhost:5000";

    protected IWebDriver Driver = null!;
    protected ApiHelper Api = null!;

    [SetUp]
    public void StartBrowser()
    {
        Driver = WebDriverFactory.CreateChrome();
        Api = new ApiHelper(BaseUrl);
    }

    [TearDown]
    public void StopBrowser()
    {
        // On failure, save a screenshot next to the test results - the first
        // thing you want when a UI test fails in CI.
        if (TestContext.CurrentContext.Result.Outcome.Status == NUnit.Framework.Interfaces.TestStatus.Failed)
        {
            try
            {
                var dir = Path.Combine(TestContext.CurrentContext.WorkDirectory, "screenshots");
                Directory.CreateDirectory(dir);
                var file = Path.Combine(dir, $"{TestContext.CurrentContext.Test.Name}.png");
                ((ITakesScreenshot)Driver).GetScreenshot().SaveAsFile(file);
                TestContext.AddTestAttachment(file);
            }
            catch { /* never let screenshot problems hide the real failure */ }
        }

        Driver.Quit();   // Closes every window AND ends the chromedriver process.
        Driver.Dispose();
    }
}
