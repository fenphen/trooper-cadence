using System.Net;
using RestSharpTests.Api;
using RestSharpTests.Models;

namespace RestSharpTests.Tests;

/// <summary>PUT /api/loads/{id}/assign/{carrierId}</summary>
[TestFixture]
public class AssignCarrierTests : ApiTestBase
{
    [Test]
    public async Task Assign_ActiveCarrierToAvailableLoad_BooksTheLoad()
    {
        var load = await Api.CreateValidLoadAsync();

        var response = await Api.AssignCarrierAsync(load.Id, ActiveCarrierId);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK), response.Content);
        var booked = LoadBoardApiClient.Body<LoadDto>(response);
        Assert.Multiple(() =>
        {
            Assert.That(booked.Status, Is.EqualTo(LoadStatus.Booked));
            Assert.That(booked.CarrierId, Is.EqualTo(ActiveCarrierId));
            Assert.That(booked.Carrier?.Name, Is.EqualTo("Lone Star Logistics"));
        });
    }

    [Test]
    public async Task Assign_InactiveCarrier_Returns400AndLeavesLoadAvailable()
    {
        var load = await Api.CreateValidLoadAsync();

        var response = await Api.AssignCarrierAsync(load.Id, InactiveCarrierId);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(LoadBoardApiClient.Body<ErrorResponse>(response).Error, Does.Contain("inactive"));

        var after = await Api.FetchLoadAsync(load.Id);
        Assert.That(after.Status, Is.EqualTo(LoadStatus.Available));
        Assert.That(after.CarrierId, Is.Null);
    }

    [Test]
    public async Task Assign_LoadThatIsAlreadyBooked_Returns400()
    {
        var load = await Api.CreateValidLoadAsync();
        await Api.AssignCarrierAsync(load.Id, ActiveCarrierId);

        // Try to double-book with a different carrier.
        var response = await Api.AssignCarrierAsync(load.Id, 2);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(LoadBoardApiClient.Body<ErrorResponse>(response).Error, Does.Contain("Only Available loads"));

        var after = await Api.FetchLoadAsync(load.Id);
        Assert.That(after.CarrierId, Is.EqualTo(ActiveCarrierId), "the original carrier must be kept");
    }

    [Test]
    public async Task Assign_UnknownCarrier_Returns404()
    {
        var load = await Api.CreateValidLoadAsync();

        var response = await Api.AssignCarrierAsync(load.Id, 999999);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
    }

    [Test]
    public async Task Assign_UnknownLoad_Returns404()
    {
        var response = await Api.AssignCarrierAsync(999999, ActiveCarrierId);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
    }

    [Test]
    public async Task Assign_WithoutApiKey_Returns401()
    {
        var load = await Api.CreateValidLoadAsync();

        var response = await Api.AssignCarrierAsync(load.Id, ActiveCarrierId, apiKey: null);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Unauthorized));
    }
}
