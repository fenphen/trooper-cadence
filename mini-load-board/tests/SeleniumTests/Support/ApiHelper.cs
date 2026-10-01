using System.Net.Http.Json;

namespace SeleniumTests.Support;

/// <summary>
/// Minimal API helper so UI tests can ARRANGE their own data quickly
/// (create a load, book it) and only drive the browser for the part under test.
/// </summary>
public class ApiHelper
{
    private readonly HttpClient _http;

    public ApiHelper(string baseUrl)
    {
        _http = new HttpClient { BaseAddress = new Uri(baseUrl) };
        _http.DefaultRequestHeaders.Add("X-Api-Key", "test-key-123");
    }

    public record LoadSummary(int Id, string Origin, string Destination, string Status);

    public async Task<LoadSummary> CreateLoadAsync(string origin = "Austin, TX", string destination = "Tulsa, OK")
    {
        var body = new
        {
            origin,
            destination,
            pickupDate = DateOnly.FromDateTime(DateTime.UtcNow).AddDays(7).ToString("yyyy-MM-dd"),
            weight = 30000,
            rate = 1500
        };
        var response = await _http.PostAsJsonAsync("/api/loads", body);
        response.EnsureSuccessStatusCode();
        return (await response.Content.ReadFromJsonAsync<LoadSummary>())!;
    }

    public async Task AssignCarrierAsync(int loadId, int carrierId = 1)
    {
        var response = await _http.PutAsync($"/api/loads/{loadId}/assign/{carrierId}", null);
        response.EnsureSuccessStatusCode();
    }

    public async Task<LoadSummary?> GetLoadAsync(int loadId)
    {
        var response = await _http.GetAsync($"/api/loads/{loadId}");
        return response.IsSuccessStatusCode ? await response.Content.ReadFromJsonAsync<LoadSummary>() : null;
    }
}
