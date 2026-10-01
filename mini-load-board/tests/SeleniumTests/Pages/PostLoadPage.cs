using OpenQA.Selenium;

namespace SeleniumTests.Pages;

/// <summary>Page object for post-load.html.</summary>
public class PostLoadPage : BasePage
{
    public PostLoadPage(IWebDriver driver, string baseUrl) : base(driver, baseUrl) { }

    private static readonly By SuccessMessage = TestId("success-message");
    private static readonly By ServerErrors = TestId("server-errors");

    public PostLoadPage Open()
    {
        Driver.Navigate().GoToUrl(BaseUrl + "/post-load.html");
        WaitForVisible(TestId("post-load-form"));
        return this;
    }

    public PostLoadPage Fill(string? origin = null, string? destination = null, string? pickupDate = null,
                             string? weight = null, string? rate = null)
    {
        if (origin is not null) Type("origin-input", origin);
        if (destination is not null) Type("destination-input", destination);
        if (pickupDate is not null) TypeDate(pickupDate);
        if (weight is not null) Type("weight-input", weight);
        if (rate is not null) Type("rate-input", rate);
        return this;
    }

    public void Submit() =>
        // Selenium has no getByRole, but XPath can target a button by its visible text.
        Driver.FindElement(By.XPath("//button[normalize-space()='Post Load']")).Click();

    public string FieldError(string field) => Driver.FindElement(TestId($"{field}-error")).Text.Trim();

    public string WaitForSuccess()
    {
        WaitForVisible(SuccessMessage);
        return Driver.FindElement(SuccessMessage).Text;
    }

    public bool ServerErrorsVisible => Driver.FindElement(ServerErrors).Displayed;

    private void Type(string testId, string text)
    {
        var input = Driver.FindElement(TestId(testId));
        input.Clear();
        input.SendKeys(text);
    }

    /// <summary>
    /// Chrome's &lt;input type="date"&gt; ignores SendKeys of "2026-10-15" (it expects
    /// keystrokes in the user's locale format), so set the value through JavaScript
    /// and fire the events the page listens for.
    /// </summary>
    private void TypeDate(string isoDate)
    {
        var input = Driver.FindElement(TestId("pickup-date-input"));
        ((IJavaScriptExecutor)Driver).ExecuteScript(
            "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
            input, isoDate);
    }
}
