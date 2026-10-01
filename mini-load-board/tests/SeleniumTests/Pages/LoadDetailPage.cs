using OpenQA.Selenium;
using OpenQA.Selenium.Support.UI;

namespace SeleniumTests.Pages;

/// <summary>Page object for load.html?id=N.</summary>
public class LoadDetailPage : BasePage
{
    public LoadDetailPage(IWebDriver driver, string baseUrl) : base(driver, baseUrl) { }

    private static readonly By Title = TestId("load-title");
    private static readonly By Status = TestId("detail-status");
    private static readonly By Carrier = TestId("detail-carrier");
    private static readonly By CarrierSelect = TestId("carrier-select");
    private static readonly By AssignButton = TestId("assign-button");
    private static readonly By InTransitButton = TestId("mark-in-transit");
    private static readonly By DeliveredButton = TestId("mark-delivered");
    private static readonly By ActionMessage = TestId("action-message");

    public LoadDetailPage Open(int loadId)
    {
        Driver.Navigate().GoToUrl($"{BaseUrl}/load.html?id={loadId}");
        WaitForText(Title, $"Load #{loadId}");
        return this;
    }

    public string StatusText => Driver.FindElement(Status).Text.Trim();
    public string CarrierText => Driver.FindElement(Carrier).Text.Trim();
    public bool InTransitEnabled => Driver.FindElement(InTransitButton).Enabled;
    public bool DeliveredEnabled => Driver.FindElement(DeliveredButton).Enabled;
    public bool AssignSectionVisible => Driver.FindElement(TestId("assign-section")).Displayed;

    public void AssignCarrier(string carrierNameFragment)
    {
        var select = new SelectElement(WaitForVisible(CarrierSelect));
        var option = select.Options.First(o => o.Text.Contains(carrierNameFragment));
        select.SelectByValue(option.GetAttribute("value")!);
        Driver.FindElement(AssignButton).Click();
    }

    public void MarkInTransit() => Driver.FindElement(InTransitButton).Click();
    public void MarkDelivered() => Driver.FindElement(DeliveredButton).Click();

    public void WaitForStatus(string expected) => WaitForText(Status, expected);
    public string WaitForActionMessage()
    {
        WaitForVisible(ActionMessage);
        return Driver.FindElement(ActionMessage).Text;
    }
}
