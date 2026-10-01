using System.Net;
using RestSharpTests.Api;
using RestSharpTests.Models;

namespace RestSharpTests.Tests;

/// <summary>
/// PUT /api/loads/{id}/status - the state machine.
/// Allowed:  Booked -> InTransit -> Delivered.
/// Everything else (backwards, skipping a step, from Available) must be rejected.
/// </summary>
[TestFixture]
public class StatusTransitionTests : ApiTestBase
{
    /// <summary>Creates a fresh load and walks it to the requested starting status.</summary>
    private async Task<LoadDto> LoadInStatus(LoadStatus status)
    {
        var load = await Api.CreateValidLoadAsync();
        if (status == LoadStatus.Available) return load;

        await Api.AssignCarrierAsync(load.Id, ActiveCarrierId);
        if (status == LoadStatus.Booked) return await Api.FetchLoadAsync(load.Id);

        await Api.UpdateStatusAsync(load.Id, "InTransit");
        if (status == LoadStatus.InTransit) return await Api.FetchLoadAsync(load.Id);

        await Api.UpdateStatusAsync(load.Id, "Delivered");
        return await Api.FetchLoadAsync(load.Id);
    }

    [Test]
    public async Task Booked_To_InTransit_IsAllowed()
    {
        var load = await LoadInStatus(LoadStatus.Booked);

        var response = await Api.UpdateStatusAsync(load.Id, "InTransit");

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK), response.Content);
        Assert.That(LoadBoardApiClient.Body<LoadDto>(response).Status, Is.EqualTo(LoadStatus.InTransit));
    }

    [Test]
    public async Task InTransit_To_Delivered_IsAllowed()
    {
        var load = await LoadInStatus(LoadStatus.InTransit);

        var response = await Api.UpdateStatusAsync(load.Id, "Delivered");

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK), response.Content);
        Assert.That(LoadBoardApiClient.Body<LoadDto>(response).Status, Is.EqualTo(LoadStatus.Delivered));
    }

    [Test]
    public async Task Booked_To_Delivered_SkippingInTransit_IsRejected()
    {
        // A load can't be delivered before it was ever picked up.
        var load = await LoadInStatus(LoadStatus.Booked);

        var response = await Api.UpdateStatusAsync(load.Id, "Delivered");

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest), response.Content);
        Assert.That((await Api.FetchLoadAsync(load.Id)).Status, Is.EqualTo(LoadStatus.Booked));
    }

    [TestCase(LoadStatus.InTransit, "Booked")]
    [TestCase(LoadStatus.Delivered, "InTransit")]
    [TestCase(LoadStatus.Delivered, "Booked")]
    public async Task MovingBackwards_IsRejected(LoadStatus from, string to)
    {
        var load = await LoadInStatus(from);

        var response = await Api.UpdateStatusAsync(load.Id, to);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest), response.Content);
        Assert.That(LoadBoardApiClient.Body<ErrorResponse>(response).Error, Does.Contain($"from {from} to {to}"));
        Assert.That((await Api.FetchLoadAsync(load.Id)).Status, Is.EqualTo(from), "status must be unchanged");
    }

    [TestCase("Booked")]
    [TestCase("InTransit")]
    public async Task AvailableLoad_CannotChangeStatusDirectly(string to)
    {
        // Available -> Booked only happens through the assign endpoint, which also records the carrier.
        var load = await LoadInStatus(LoadStatus.Available);

        var response = await Api.UpdateStatusAsync(load.Id, to);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest), response.Content);
    }

    [Test]
    public async Task SameStatus_IsRejected()
    {
        var load = await LoadInStatus(LoadStatus.Booked);

        var response = await Api.UpdateStatusAsync(load.Id, "Booked");

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
    }

    [Test]
    public async Task UnknownStatusValue_IsRejected()
    {
        var load = await LoadInStatus(LoadStatus.Booked);

        var response = await Api.UpdateStatusAsync(load.Id, "Teleported");

        // The JSON can't be bound to the enum, so ASP.NET answers 400 before our code runs.
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
    }

    [Test]
    public async Task UpdateStatus_WithoutApiKey_Returns401()
    {
        var load = await LoadInStatus(LoadStatus.Booked);

        var response = await Api.UpdateStatusAsync(load.Id, "InTransit", apiKey: null);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Unauthorized));
    }
}
