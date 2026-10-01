using RestSharpTests.Api;

namespace RestSharpTests.Tests;

/// <summary>
/// Shared setup for all API test fixtures: one client per fixture.
/// Seed data facts used across tests live here so they're defined once.
/// </summary>
public abstract class ApiTestBase
{
    protected LoadBoardApiClient Api = null!;

    // From SeedData.cs in the app.
    protected const int ActiveCarrierId = 1;    // Lone Star Logistics
    protected const int InactiveCarrierId = 5;  // Budget Trucking Co (IsActive = false)
    protected const int SeededLoadCount = 11;

    [OneTimeSetUp]
    public void CreateClient() => Api = new LoadBoardApiClient();

    [OneTimeTearDown]
    public void DisposeClient() => Api.Dispose();
}
