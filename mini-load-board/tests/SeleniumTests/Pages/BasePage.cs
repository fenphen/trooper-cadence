using OpenQA.Selenium;
using OpenQA.Selenium.Support.UI;

namespace SeleniumTests.Pages;

/// <summary>
/// Shared plumbing for all page objects: the driver, the base URL and a set of
/// explicit-wait helpers.
///
/// Why explicit waits? Our pages fill themselves in with JavaScript after the
/// HTML loads, so an element may exist but not yet hold the final text.
/// WebDriverWait polls a condition until it is true (or times out) - unlike
/// Thread.Sleep it never waits longer than necessary and never too little.
/// </summary>
public abstract class BasePage
{
    protected readonly IWebDriver Driver;
    protected readonly string BaseUrl;
    protected readonly WebDriverWait Wait;

    protected BasePage(IWebDriver driver, string baseUrl)
    {
        Driver = driver;
        BaseUrl = baseUrl;
        Wait = new WebDriverWait(driver, TimeSpan.FromSeconds(10));
        // Elements re-render while we poll; ignore the exceptions that causes.
        Wait.IgnoreExceptionTypes(typeof(NoSuchElementException), typeof(StaleElementReferenceException));
    }

    /// <summary>Locator for our stable data-testid hooks - the Selenium equivalent of Playwright's getByTestId.</summary>
    protected static By TestId(string id) => By.CssSelector($"[data-testid='{id}']");

    /// <summary>Waits until the element exists AND is displayed, then returns it.</summary>
    protected IWebElement WaitForVisible(By by) =>
        Wait.Until(d =>
        {
            var element = d.FindElement(by);
            return element.Displayed ? element : null;
        })!;

    /// <summary>Waits until an element's text matches the expected value.</summary>
    protected void WaitForText(By by, string expected) =>
        Wait.Until(d => d.FindElement(by).Text.Trim() == expected);

    /// <summary>Waits until the element's text contains the given fragment.</summary>
    protected void WaitForTextContains(By by, string fragment) =>
        Wait.Until(d => d.FindElement(by).Text.Contains(fragment, StringComparison.OrdinalIgnoreCase));

    protected void WaitForHidden(By by) =>
        Wait.Until(d =>
        {
            var elements = d.FindElements(by);
            return elements.Count == 0 || !elements[0].Displayed;
        });
}
