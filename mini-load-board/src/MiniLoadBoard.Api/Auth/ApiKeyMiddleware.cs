namespace MiniLoadBoard.Api.Auth;

/// <summary>
/// A deliberately simple, FAKE authentication scheme for practice.
///
/// Any request that changes data (POST, PUT, DELETE) to /api/* must send the header
///     X-Api-Key: test-key-123
/// otherwise we return 401 Unauthorized. Read-only GET requests are public.
///
/// Real apps would use something like OAuth/JWT bearer tokens, but the testing
/// ideas are the same: test with a valid key, a wrong key, and no key at all.
/// </summary>
public class ApiKeyMiddleware(RequestDelegate next)
{
    public const string HeaderName = "X-Api-Key";
    public const string ValidKey = "test-key-123";

    private static readonly string[] ProtectedMethods = ["POST", "PUT", "DELETE"];

    public async Task InvokeAsync(HttpContext context)
    {
        var isApiCall = context.Request.Path.StartsWithSegments("/api");
        var isWrite = ProtectedMethods.Contains(context.Request.Method);

        if (isApiCall && isWrite)
        {
            var providedKey = context.Request.Headers[HeaderName].ToString();
            if (providedKey != ValidKey)
            {
                context.Response.StatusCode = StatusCodes.Status401Unauthorized;
                await context.Response.WriteAsJsonAsync(new { error = $"Missing or invalid {HeaderName} header." });
                return; // Stop here - don't call the endpoint.
            }
        }

        await next(context);
    }
}
