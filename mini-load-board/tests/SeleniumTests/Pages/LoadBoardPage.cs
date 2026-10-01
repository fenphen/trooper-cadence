using OpenQA.Selenium;
using OpenQA.Selenium.Support.UI;

namespace SeleniumTests.Pages;

/// <summary>Page object for the load board (index.html).</summary>
public class LoadBoardPage : BasePage
{
    public LoadBoardPage(IWebDriver driver, string baseUrl) : base(driver, baseUrl) { }

    private static readonly By Rows = TestId("load-row");
    private static readonly By ResultCount = TestId("result-count");
    private static readonly By StatusFilter = TestId("status-filter");
    private static readonly By OriginSearch = TestId("origin-search");

    public LoadBoardPage Open()
    {
        Driver.Navigate().GoToUrl(BaseUrl + "/");
        // The table is populated by JS; wait for the count label rather than sleeping.
        WaitForTextContains(ResultCount, "load");
        return this;
    }

    public int RowCount => Driver.FindElements(Rows).Count;

    public string ResultCountText => Driver.FindElement(ResultCount).Text;

    public void FilterByStatus(string status)
    {
        var before = ResultCountText;
        new SelectElement(Driver.FindElement(StatusFilter)).SelectByValue(status);
        // The count label changes when the filtered data arrives.
        Wait.Until(d => d.FindElement(ResultCount).Text != before);
    }

    public void SearchByOrigin(string text)
    {
        var before = ResultCountText;
        var box = Driver.FindElement(OriginSearch);
        box.Clear();
        box.SendKeys(text);
        Wait.Until(d => d.FindElement(ResultCount).Text != before);
    }

    public IReadOnlyList<string> VisibleStatuses() =>
        Driver.FindElements(By.CssSelector("[data-testid='load-row'] [data-testid='load-status']"))
              .Select(e => e.Text.Trim()).ToList();

    public IReadOnlyList<string> VisibleOrigins() =>
        Driver.FindElements(By.CssSelector("[data-testid='load-row'] [data-testid='load-origin']"))
              .Select(e => e.Text.Trim()).ToList();
}
