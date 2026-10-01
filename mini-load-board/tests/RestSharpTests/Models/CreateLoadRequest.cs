namespace RestSharpTests.Models;

/// <summary>
/// Body for POST /api/loads. Everything is nullable so negative tests can leave
/// fields out (a null is serialized as JSON null, which the API treats as "missing").
/// </summary>
public class CreateLoadRequest
{
    public string? Origin { get; set; }
    public string? Destination { get; set; }
    public DateOnly? PickupDate { get; set; }
    public int? Weight { get; set; }
    public decimal? Rate { get; set; }

    /// <summary>A known-good load, N days in the future. Tests tweak one field at a time.</summary>
    public static CreateLoadRequest Valid(int daysFromToday = 7) => new()
    {
        Origin = "Austin, TX",
        Destination = "Tulsa, OK",
        PickupDate = DateOnly.FromDateTime(DateTime.UtcNow).AddDays(daysFromToday),
        Weight = 30000,
        Rate = 1500m
    };
}
