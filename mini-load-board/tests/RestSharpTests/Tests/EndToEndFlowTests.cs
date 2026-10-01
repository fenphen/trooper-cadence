using System.Net;
using RestSharpTests.Api;
using RestSharpTests.Models;

namespace RestSharpTests.Tests;

/// <summary>
/// One scenario that follows a load through its whole life, the way a broker
/// would: post it, cover it with a carrier, dispatch it, deliver it.
/// Each step verifies the server state before moving on, so a failure points
/// at exactly which step broke.
/// </summary>
[TestFixture]
public class EndToEndFlowTests : ApiTestBase
{
    [Test]
    public async Task Load_GoesFromPostedToDelivered()
    {
        // 1. Post a load.
        var request = CreateLoadRequest.Valid();
        request.Origin = "El Paso, TX";
        request.Destination = "Oklahoma City, OK";
        request.Weight = 41000;
        request.Rate = 1975.50m;

        var createResponse = await Api.CreateLoadAsync(request);
        Assert.That(createResponse.StatusCode, Is.EqualTo(HttpStatusCode.Created), createResponse.Content);
        var load = LoadBoardApiClient.Body<LoadDto>(createResponse);
        Assert.That(load.Status, Is.EqualTo(LoadStatus.Available));

        // 2. It shows up on the board under the Available filter.
        var available = LoadBoardApiClient.Body<List<LoadDto>>(await Api.GetLoadsAsync(status: "Available"));
        Assert.That(available.Select(l => l.Id), Does.Contain(load.Id));

        // 3. Assign a carrier -> Booked.
        var assignResponse = await Api.AssignCarrierAsync(load.Id, ActiveCarrierId);
        Assert.That(assignResponse.StatusCode, Is.EqualTo(HttpStatusCode.OK), assignResponse.Content);
        load = await Api.FetchLoadAsync(load.Id);
        Assert.Multiple(() =>
        {
            Assert.That(load.Status, Is.EqualTo(LoadStatus.Booked));
            Assert.That(load.CarrierId, Is.EqualTo(ActiveCarrierId));
            Assert.That(load.Carrier?.IsActive, Is.True);
        });

        // 4. Truck picks up -> InTransit.
        var transitResponse = await Api.UpdateStatusAsync(load.Id, "InTransit");
        Assert.That(transitResponse.StatusCode, Is.EqualTo(HttpStatusCode.OK), transitResponse.Content);
        load = await Api.FetchLoadAsync(load.Id);
        Assert.That(load.Status, Is.EqualTo(LoadStatus.InTransit));

        // 5. Delivered.
        var deliveredResponse = await Api.UpdateStatusAsync(load.Id, "Delivered");
        Assert.That(deliveredResponse.StatusCode, Is.EqualTo(HttpStatusCode.OK), deliveredResponse.Content);
        load = await Api.FetchLoadAsync(load.Id);
        Assert.Multiple(() =>
        {
            Assert.That(load.Status, Is.EqualTo(LoadStatus.Delivered));
            Assert.That(load.CarrierId, Is.EqualTo(ActiveCarrierId), "carrier stays on the record after delivery");
            Assert.That(load.Rate, Is.EqualTo(1975.50m), "money is not rounded along the way");
        });

        // 6. A delivered load is final: it can't be deleted or changed any more.
        Assert.That((await Api.DeleteLoadAsync(load.Id)).StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That((await Api.UpdateStatusAsync(load.Id, "InTransit")).StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));

        // 7. And it no longer appears under Available.
        var stillAvailable = LoadBoardApiClient.Body<List<LoadDto>>(await Api.GetLoadsAsync(status: "Available"));
        Assert.That(stillAvailable.Select(l => l.Id), Does.Not.Contain(load.Id));
    }
}
