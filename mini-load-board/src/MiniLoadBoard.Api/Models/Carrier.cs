namespace MiniLoadBoard.Api.Models;

/// <summary>
/// A trucking company that can haul loads for the brokerage.
/// </summary>
public class Carrier
{
    public int Id { get; set; }

    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// The carrier's FMCSA Motor Carrier number, e.g. "MC-123456".
    /// Brokers check this to make sure a carrier is authorized to operate.
    /// </summary>
    public string McNumber { get; set; } = string.Empty;

    /// <summary>Internal performance rating from 1 (poor) to 5 (excellent).</summary>
    public int Rating { get; set; }

    /// <summary>Inactive carriers (expired insurance, bad safety record...) cannot be assigned loads.</summary>
    public bool IsActive { get; set; }
}
