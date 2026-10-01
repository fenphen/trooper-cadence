using System.Net;
using RestSharpTests.Api;
using RestSharpTests.Models;

namespace RestSharpTests.Tests;

/// <summary>DELETE /api/loads/{id} - only Available loads may be deleted.</summary>
[TestFixture]
public class DeleteLoadTests : ApiTestBase
{
    [Test]
    public async Task Delete_AvailableLoad_Returns204AndLoadIsGone()
    {
        var load = await Api.CreateValidLoadAsync();

        var response = await Api.DeleteLoadAsync(load.Id);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.NoContent));
        Assert.That(response.Content, Is.Null.Or.Empty, "204 must not have a body");
        Assert.That((await Api.GetLoadAsync(load.Id)).StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
    }

    [Test]
    public async Task Delete_BookedLoad_Returns400AndKeepsLoad()
    {
        var load = await Api.CreateValidLoadAsync();
        await Api.AssignCarrierAsync(load.Id, ActiveCarrierId);

        var response = await Api.DeleteLoadAsync(load.Id);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(LoadBoardApiClient.Body<ErrorResponse>(response).Error, Does.Contain("Only Available loads can be deleted"));
        Assert.That((await Api.GetLoadAsync(load.Id)).StatusCode, Is.EqualTo(HttpStatusCode.OK));
    }

    [Test]
    public async Task Delete_UnknownLoad_Returns404()
    {
        var response = await Api.DeleteLoadAsync(999999);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
    }

    [Test]
    public async Task Delete_WithoutApiKey_Returns401()
    {
        var load = await Api.CreateValidLoadAsync();

        var response = await Api.DeleteLoadAsync(load.Id, apiKey: null);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Unauthorized));
    }
}
