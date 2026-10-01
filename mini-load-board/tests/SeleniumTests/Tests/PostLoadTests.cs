using SeleniumTests.Pages;

namespace SeleniumTests.Tests;

[TestFixture]
public class PostLoadTests : UiTestBase
{
    private static string DaysFromToday(int days) =>
        DateTime.UtcNow.AddDays(days).ToString("yyyy-MM-dd");

    [Test]
    public void PostLoad_ValidData_ShowsSuccessAndLoadExists()
    {
        var page = new PostLoadPage(Driver, BaseUrl).Open();

        page.Fill(origin: "San Antonio, TX", destination: "Little Rock, AR",
                  pickupDate: DaysFromToday(4), weight: "36000", rate: "1725").Submit();

        var message = page.WaitForSuccess();
        Assert.That(message, Does.Match(@"Load #\d+ posted"));

        // Cross-check through the API that the UI really created it.
        var id = int.Parse(System.Text.RegularExpressions.Regex.Match(message, @"#(\d+)").Groups[1].Value);
        var load = Api.GetLoadAsync(id).GetAwaiter().GetResult();
        Assert.That(load, Is.Not.Null);
        Assert.That(load!.Origin, Is.EqualTo("San Antonio, TX"));
        Assert.That(load.Status, Is.EqualTo("Available"));
    }

    [Test]
    public void PostLoad_InvalidData_ShowsClientSideErrors()
    {
        var page = new PostLoadPage(Driver, BaseUrl).Open();

        // Origin left blank, overweight, free, and picked up yesterday.
        page.Fill(destination: "Little Rock, AR", pickupDate: DaysFromToday(-1),
                  weight: "48001", rate: "0").Submit();

        Assert.Multiple(() =>
        {
            Assert.That(page.FieldError("origin"), Is.EqualTo("Origin is required."));
            Assert.That(page.FieldError("weight"), Does.Contain("between 1 and 48,000"));
            Assert.That(page.FieldError("rate"), Is.EqualTo("Rate must be greater than 0."));
            Assert.That(page.FieldError("pickup-date"), Is.EqualTo("Pickup date cannot be in the past."));
            Assert.That(page.ServerErrorsVisible, Is.False, "nothing should reach the server");
        });
    }
}
