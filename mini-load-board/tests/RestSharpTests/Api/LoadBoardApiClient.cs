using RestSharp;
using RestSharpTests.Models;

namespace RestSharpTests.Api;

/// <summary>
/// One typed method per endpoint. Tests call these instead of building raw
/// requests, so a URL change only needs fixing here.
///
/// Every method returns the full RestResponse so tests can check the status
/// code, then use ReadBody&lt;T&gt;() to parse the JSON they expect.
/// </summary>
public class LoadBoardApiClient : ApiClientBase
{
    // ---- Loads ---------------------------------------------------------

    public Task<RestResponse> GetLoadsAsync(string? status = null, string? origin = null)
    {
        var request = BuildRequest("/api/loads", Method.Get);
        if (status is not null) request.AddQueryParameter("status", status);
        if (origin is not null) request.AddQueryParameter("origin", origin);
        return SendAsync(request);
    }

    public Task<RestResponse> GetLoadAsync(int id) =>
        SendAsync(BuildRequest($"/api/loads/{id}", Method.Get));

    public Task<RestResponse> CreateLoadAsync(CreateLoadRequest body, string? apiKey = ValidApiKey)
    {
        var request = BuildRequest("/api/loads", Method.Post, apiKey);
        request.AddJsonBody(body);
        return SendAsync(request);
    }

    public Task<RestResponse> AssignCarrierAsync(int loadId, int carrierId, string? apiKey = ValidApiKey) =>
        SendAsync(BuildRequest($"/api/loads/{loadId}/assign/{carrierId}", Method.Put, apiKey));

    public Task<RestResponse> UpdateStatusAsync(int loadId, string status, string? apiKey = ValidApiKey)
    {
        var request = BuildRequest($"/api/loads/{loadId}/status", Method.Put, apiKey);
        request.AddJsonBody(new { status });
        return SendAsync(request);
    }

    public Task<RestResponse> DeleteLoadAsync(int loadId, string? apiKey = ValidApiKey) =>
        SendAsync(BuildRequest($"/api/loads/{loadId}", Method.Delete, apiKey));

    // ---- Carriers ------------------------------------------------------

    public Task<RestResponse> GetCarriersAsync() =>
        SendAsync(BuildRequest("/api/carriers", Method.Get));

    // ---- Convenience helpers for "arrange" steps -----------------------

    /// <summary>Creates a load and asserts it worked. Use this when the load is just test setup.</summary>
    public async Task<LoadDto> CreateValidLoadAsync(Action<CreateLoadRequest>? customize = null)
    {
        var body = CreateLoadRequest.Valid();
        customize?.Invoke(body);
        var response = await CreateLoadAsync(body);
        Assert.That(response.StatusCode, Is.EqualTo(System.Net.HttpStatusCode.Created), response.Content);
        return ReadBody<LoadDto>(response);
    }

    /// <summary>Reads the current state of a load from the server.</summary>
    public async Task<LoadDto> FetchLoadAsync(int id)
    {
        var response = await GetLoadAsync(id);
        Assert.That(response.StatusCode, Is.EqualTo(System.Net.HttpStatusCode.OK), response.Content);
        return ReadBody<LoadDto>(response);
    }

    /// <summary>Expose the deserializer to tests (it's protected in the base class).</summary>
    public static T Body<T>(RestResponse response) => ReadBody<T>(response);
}
