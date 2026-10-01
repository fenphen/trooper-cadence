using System.Net;
using RestSharpTests.Api;
using RestSharpTests.Models;

namespace RestSharpTests.Tests;

[TestFixture]
public class CarriersTests : ApiTestBase
{
    [Test]
    public async Task GetCarriers_ReturnsFiveSeededCarriers_WithValidRatings()
    {
        var response = await Api.GetCarriersAsync();

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK));
        var carriers = LoadBoardApiClient.Body<List<CarrierDto>>(response);

        Assert.Multiple(() =>
        {
            Assert.That(carriers, Has.Count.EqualTo(5));
            Assert.That(carriers.Select(c => c.Rating), Is.All.InRange(1, 5));
            Assert.That(carriers.Select(c => c.McNumber), Is.All.Match(@"^MC-\d{6}$"));
            Assert.That(carriers.Count(c => !c.IsActive), Is.EqualTo(1), "exactly one inactive carrier is seeded");
        });
    }
}
