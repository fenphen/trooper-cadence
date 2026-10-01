namespace RestSharpTests.Models;

/// <summary>Simple business-rule error: { "error": "Only Available loads can be deleted..." }</summary>
public class ErrorResponse
{
    public string Error { get; set; } = "";
}

/// <summary>
/// RFC 7807 validation problem details, as returned by Results.ValidationProblem():
/// { "title": "...", "status": 400, "errors": { "Weight": ["Weight must be ..."] } }
/// </summary>
public class ValidationProblem
{
    public string Title { get; set; } = "";
    public int Status { get; set; }
    public Dictionary<string, string[]> Errors { get; set; } = new();
}
