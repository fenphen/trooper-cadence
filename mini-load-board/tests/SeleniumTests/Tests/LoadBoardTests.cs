using SeleniumTests.Pages;

namespace SeleniumTests.Tests;

[TestFixture]
public class LoadBoardTests : UiTestBase
{
    [Test]
    public void Board_ShowsSeededLoads_AndFiltersByStatus()
    {
        var board = new LoadBoardPage(Driver, BaseUrl).Open();

        Assert.That(board.RowCount, Is.GreaterThanOrEqualTo(11), "all seeded loads are listed");

        board.FilterByStatus("Delivered");

        var statuses = board.VisibleStatuses();
        Assert.That(statuses, Is.Not.Empty);
        Assert.That(statuses, Is.All.EqualTo("Delivered"));
    }

    [Test]
    public void Board_SearchByOrigin_IgnoresCase()
    {
        var board = new LoadBoardPage(Driver, BaseUrl).Open();

        board.SearchByOrigin("chicago");

        var origins = board.VisibleOrigins();
        Assert.That(origins, Is.Not.Empty, "lower-case search should still find 'Chicago, IL'");
        Assert.That(origins, Is.All.Contains("Chicago"));
    }
}
