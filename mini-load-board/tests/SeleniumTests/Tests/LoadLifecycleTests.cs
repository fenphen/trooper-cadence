using SeleniumTests.Pages;

namespace SeleniumTests.Tests;

[TestFixture]
public class LoadLifecycleTests : UiTestBase
{
    [Test]
    public void AssignCarrier_ThenMoveThroughStatuses()
    {
        // Arrange through the API: a brand-new Available load.
        var load = Api.CreateLoadAsync(origin: "Waco, TX").GetAwaiter().GetResult();

        var page = new LoadDetailPage(Driver, BaseUrl).Open(load.Id);
        Assert.That(page.StatusText, Is.EqualTo("Available"));
        Assert.That(page.CarrierText, Is.EqualTo("Unassigned"));

        // Act 1: assign an active carrier.
        page.AssignCarrier("Rocky Mountain Movers");
        page.WaitForStatus("Booked");
        Assert.Multiple(() =>
        {
            Assert.That(page.CarrierText, Does.Contain("Rocky Mountain Movers"));
            Assert.That(page.AssignSectionVisible, Is.False, "assign controls hide once booked");
            Assert.That(page.InTransitEnabled, Is.True);
            Assert.That(page.DeliveredEnabled, Is.False, "can't deliver before pickup");
        });

        // Act 2: dispatch.
        page.MarkInTransit();
        page.WaitForStatus("InTransit");
        Assert.That(page.DeliveredEnabled, Is.True);

        // Act 3: deliver.
        page.MarkDelivered();
        page.WaitForStatus("Delivered");
        Assert.That(page.WaitForActionMessage(), Does.Contain("delivered").IgnoreCase);

        // Verify the server agrees with what the browser shows.
        var final = Api.GetLoadAsync(load.Id).GetAwaiter().GetResult();
        Assert.That(final!.Status, Is.EqualTo("Delivered"));
    }
}
