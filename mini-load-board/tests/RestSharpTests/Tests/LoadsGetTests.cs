using System.Net;
using RestSharpTests.Api;
using RestSharpTests.Models;

namespace RestSharpTests.Tests;

/// <summary>Read-only tests for GET /api/loads and GET /api/loads/{id}.</summary>
[TestFixture]
public class LoadsGetTests : ApiTestBase
{
    [Test]
    public async Task GetLoads_ReturnsSeededLoads()
    {
        var response = await Api.GetLoadsAsync();

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK));
        Assert.That(response.ContentType, Does.Contain("application/json"));

        var loads = LoadBoardApiClient.Body<List<LoadDto>>(response);
        Assert.That(loads, Has.Count.GreaterThanOrEqualTo(SeededLoadCount));

        // Spot-check the first seeded record is mapped correctly onto the DTO.
        var first = loads.Single(l => l.Id == 1);
        Assert.Multiple(() =>
        {
            Assert.That(first.Origin, Is.EqualTo("Dallas, TX"));
            Assert.That(first.Destination, Is.EqualTo("Atlanta, GA"));
            Assert.That(first.Weight, Is.EqualTo(42000));
            Assert.That(first.Rate, Is.EqualTo(2450m));
        });
    }

    [TestCase("Available")]
    [TestCase("Booked")]
    [TestCase("InTransit")]
    [TestCase("Delivered")]
    public async Task GetLoads_FilterByStatus_ReturnsOnlyThatStatus(string status)
    {
        var response = await Api.GetLoadsAsync(status: status);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK));
        var loads = LoadBoardApiClient.Body<List<LoadDto>>(response);
        Assert.That(loads, Is.Not.Empty, $"Seed data should contain at least one {status} load");
        Assert.That(loads.Select(l => l.Status.ToString()), Is.All.EqualTo(status));
    }

    [Test]
    public async Task GetLoads_FilterByStatus_IsCaseInsensitive()
    {
        var response = await Api.GetLoadsAsync(status: "booked");

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK));
        var loads = LoadBoardApiClient.Body<List<LoadDto>>(response);
        Assert.That(loads, Is.Not.Empty);
        Assert.That(loads.Select(l => l.Status), Is.All.EqualTo(LoadStatus.Booked));
    }

    [Test]
    public async Task GetLoads_UnknownStatus_Returns400()
    {
        var response = await Api.GetLoadsAsync(status: "Lost");

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(LoadBoardApiClient.Body<ErrorResponse>(response).Error, Does.Contain("Unknown status"));
    }

    [Test]
    public async Task GetLoads_FilterByOrigin_MatchesPartialText()
    {
        var response = await Api.GetLoadsAsync(origin: "Dallas");

        var loads = LoadBoardApiClient.Body<List<LoadDto>>(response);
        Assert.That(loads, Is.Not.Empty);
        Assert.That(loads.Select(l => l.Origin), Is.All.Contains("Dallas"));
    }

    [Test]
    public async Task GetLoads_FilterByOrigin_IsCaseInsensitive()
    {
        // Dispatchers type "dallas", "DALLAS" and "Dallas" - all should match the same loads.
        var upper = LoadBoardApiClient.Body<List<LoadDto>>(await Api.GetLoadsAsync(origin: "Dallas"));
        var lower = LoadBoardApiClient.Body<List<LoadDto>>(await Api.GetLoadsAsync(origin: "dallas"));

        Assert.That(lower.Select(l => l.Id), Is.EquivalentTo(upper.Select(l => l.Id)));
    }

    [Test]
    public async Task GetLoad_ById_IncludesCarrierDetails()
    {
        // Seed load 6 is Booked with Great Lakes Freight (carrier 2).
        var response = await Api.GetLoadAsync(6);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK));
        var load = LoadBoardApiClient.Body<LoadDto>(response);
        Assert.Multiple(() =>
        {
            Assert.That(load.Status, Is.EqualTo(LoadStatus.Booked));
            Assert.That(load.CarrierId, Is.EqualTo(2));
            Assert.That(load.Carrier?.Name, Is.EqualTo("Great Lakes Freight"));
        });
    }

    [Test]
    public async Task GetLoad_UnknownId_Returns404WithMessage()
    {
        var response = await Api.GetLoadAsync(999999);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
        Assert.That(LoadBoardApiClient.Body<ErrorResponse>(response).Error, Is.EqualTo("Load 999999 not found."));
    }
}
