using System.Net;
using RestSharpTests.Api;
using RestSharpTests.Models;

namespace RestSharpTests.Tests;

/// <summary>
/// POST /api/loads: positive, negative (validation + auth) and boundary tests.
/// </summary>
[TestFixture]
public class LoadsPostTests : ApiTestBase
{
    // ---- Positive ------------------------------------------------------

    [Test]
    public async Task CreateLoad_Valid_Returns201WithLocationAndBody()
    {
        var body = CreateLoadRequest.Valid();

        var response = await Api.CreateLoadAsync(body);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Created), response.Content);
        var created = LoadBoardApiClient.Body<LoadDto>(response);
        Assert.Multiple(() =>
        {
            Assert.That(created.Id, Is.GreaterThan(0));
            Assert.That(created.Status, Is.EqualTo(LoadStatus.Available), "new loads start as Available");
            Assert.That(created.CarrierId, Is.Null);
            Assert.That(created.Origin, Is.EqualTo(body.Origin));
            Assert.That(created.Weight, Is.EqualTo(body.Weight));
            Assert.That(created.Rate, Is.EqualTo(body.Rate));
            // REST convention: 201 Created tells you where the new resource lives.
            Assert.That(response.Headers?.FirstOrDefault(h => h.Name == "Location")?.Value?.ToString(),
                Is.EqualTo($"/api/loads/{created.Id}"));
        });

        // And it really is persisted.
        var fetched = await Api.FetchLoadAsync(created.Id);
        Assert.That(fetched.Origin, Is.EqualTo(body.Origin));
    }

    [Test]
    public async Task CreateLoad_PickupToday_IsAllowed()
    {
        // "Not in the past" means today is still fine (boundary on the date rule).
        var response = await Api.CreateLoadAsync(CreateLoadRequest.Valid(daysFromToday: 0));

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Created), response.Content);
    }

    // ---- Negative: validation -----------------------------------------

    [Test]
    public async Task CreateLoad_EmptyBody_ReturnsErrorForEveryRequiredField()
    {
        var response = await Api.CreateLoadAsync(new CreateLoadRequest());

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        var problem = LoadBoardApiClient.Body<ValidationProblem>(response);
        Assert.That(problem.Errors.Keys, Is.EquivalentTo(new[] { "Origin", "Destination", "PickupDate", "Weight", "Rate" }));
        Assert.That(problem.Errors["Origin"], Is.EqualTo(new[] { "Origin is required." }));
    }

    [Test]
    public async Task CreateLoad_WhitespaceOrigin_IsTreatedAsMissing()
    {
        var body = CreateLoadRequest.Valid();
        body.Origin = "   ";

        var response = await Api.CreateLoadAsync(body);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(LoadBoardApiClient.Body<ValidationProblem>(response).Errors, Contains.Key("Origin"));
    }

    [Test]
    public async Task CreateLoad_PickupDateInPast_Returns400()
    {
        var response = await Api.CreateLoadAsync(CreateLoadRequest.Valid(daysFromToday: -1));

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        var problem = LoadBoardApiClient.Body<ValidationProblem>(response);
        Assert.That(problem.Errors["PickupDate"], Is.EqualTo(new[] { "Pickup date cannot be in the past." }));
    }

    [TestCase(0)]
    [TestCase(-100)]
    public async Task CreateLoad_RateNotPositive_Returns400(decimal rate)
    {
        var body = CreateLoadRequest.Valid();
        body.Rate = rate;

        var response = await Api.CreateLoadAsync(body);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(LoadBoardApiClient.Body<ValidationProblem>(response).Errors["Rate"],
            Is.EqualTo(new[] { "Rate must be greater than 0." }));
    }

    [Test]
    public async Task CreateLoad_BadWeight_Returns400WithRangeMessage()
    {
        var body = CreateLoadRequest.Valid();
        body.Weight = 100000;

        var response = await Api.CreateLoadAsync(body);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(LoadBoardApiClient.Body<ValidationProblem>(response).Errors["Weight"].Single(),
            Does.Contain("between 1 and 48,000"));
    }

    // ---- Boundary: weight ---------------------------------------------
    // Boundary Value Analysis: bugs cluster at the edges of a valid range,
    // so test just outside, on, and just inside each boundary.

    [TestCase(0, HttpStatusCode.BadRequest, TestName = "Weight_0_IsRejected")]
    [TestCase(1, HttpStatusCode.Created, TestName = "Weight_1_IsAccepted")]
    [TestCase(48000, HttpStatusCode.Created, TestName = "Weight_48000_IsAccepted")]
    [TestCase(48001, HttpStatusCode.BadRequest, TestName = "Weight_48001_IsRejected")]
    public async Task CreateLoad_WeightBoundaries(int weight, HttpStatusCode expected)
    {
        var body = CreateLoadRequest.Valid();
        body.Weight = weight;

        var response = await Api.CreateLoadAsync(body);

        Assert.That(response.StatusCode, Is.EqualTo(expected), $"weight {weight}: {response.Content}");
    }

    // ---- Negative: authentication -------------------------------------

    [Test]
    public async Task CreateLoad_WithoutApiKey_Returns401()
    {
        var response = await Api.CreateLoadAsync(CreateLoadRequest.Valid(), apiKey: null);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Unauthorized));
        Assert.That(LoadBoardApiClient.Body<ErrorResponse>(response).Error, Does.Contain("X-Api-Key"));
    }

    [Test]
    public async Task CreateLoad_WithWrongApiKey_Returns401()
    {
        var response = await Api.CreateLoadAsync(CreateLoadRequest.Valid(), apiKey: "wrong-key");

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Unauthorized));
    }

    [Test]
    public async Task CreateLoad_UnauthorizedRequest_DoesNotCreateAnything()
    {
        var before = LoadBoardApiClient.Body<List<LoadDto>>(await Api.GetLoadsAsync()).Count;

        await Api.CreateLoadAsync(CreateLoadRequest.Valid(), apiKey: null);

        var after = LoadBoardApiClient.Body<List<LoadDto>>(await Api.GetLoadsAsync()).Count;
        Assert.That(after, Is.EqualTo(before));
    }
}
