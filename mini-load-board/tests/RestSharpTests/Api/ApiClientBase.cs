using System.Text.Json;
using RestSharp;

namespace RestSharpTests.Api;

/// <summary>
/// Base class every API client inherits from. It owns the two things all
/// requests have in common - the base URL and the API key header - so the
/// individual test classes never repeat them.
///
/// Configuration comes from environment variables with sensible defaults, which
/// is how the same tests run unchanged on a laptop and in GitHub Actions.
/// </summary>
public abstract class ApiClientBase : IDisposable
{
    public const string ApiKeyHeader = "X-Api-Key";
    public const string ValidApiKey = "test-key-123";

    /// <summary>Where the app is running. Override with LOADBOARD_URL=http://host:port.</summary>
    public static string BaseUrl =>
        Environment.GetEnvironmentVariable("LOADBOARD_URL") ?? "http://localhost:5000";

    protected readonly RestClient Client;

    /// <summary>JSON options matching the API: camelCase property names, enums as strings.</summary>
    protected static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    protected ApiClientBase()
    {
        Client = new RestClient(new RestClientOptions(BaseUrl)
        {
            // Don't throw on 4xx/5xx - tests want to assert on those status codes.
            ThrowOnAnyError = false,
            Timeout = TimeSpan.FromSeconds(30)
        });
    }

    /// <summary>
    /// Builds a request. Pass <paramref name="apiKey"/> = null to send no key at all
    /// (for 401 tests) or a wrong value to test an invalid key.
    /// </summary>
    protected static RestRequest BuildRequest(string path, Method method, string? apiKey = ValidApiKey)
    {
        var request = new RestRequest(path, method);
        request.AddHeader("Accept", "application/json");
        if (apiKey is not null)
            request.AddHeader(ApiKeyHeader, apiKey);
        return request;
    }

    /// <summary>Sends the request and returns the raw response (status code, headers, body).</summary>
    protected Task<RestResponse> SendAsync(RestRequest request) => Client.ExecuteAsync(request);

    /// <summary>Deserializes a response body into T. Fails the test with a helpful message if it can't.</summary>
    protected static T ReadBody<T>(RestResponse response)
    {
        Assert.That(response.Content, Is.Not.Null.And.Not.Empty,
            $"Expected a JSON body from {response.Request?.Method} {response.ResponseUri} (status {(int)response.StatusCode})");
        return JsonSerializer.Deserialize<T>(response.Content!, JsonOptions)
               ?? throw new InvalidOperationException($"Could not deserialize response as {typeof(T).Name}: {response.Content}");
    }

    public void Dispose() => Client.Dispose();
}
