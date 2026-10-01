namespace MiniLoadBoard.Api.Models;

/// <summary>
/// The lifecycle of a load. The happy path is:
/// Available -> Booked -> InTransit -> Delivered
/// </summary>
public enum LoadStatus
{
    Available,
    Booked,
    InTransit,
    Delivered
}

/// <summary>
/// A shipment that a shipper needs moved from Origin to Destination.
/// </summary>
public class Load
{
    public int Id { get; set; }

    /// <summary>Pickup city, e.g. "Dallas, TX".</summary>
    public string Origin { get; set; } = string.Empty;

    /// <summary>Delivery city, e.g. "Atlanta, GA".</summary>
    public string Destination { get; set; } = string.Empty;

    /// <summary>The day the truck must pick the freight up (no time component).</summary>
    public DateOnly PickupDate { get; set; }

    /// <summary>Weight in pounds. A standard dry van legally carries up to about 48,000 lbs.</summary>
    public int Weight { get; set; }

    /// <summary>What the shipper pays for the move, in US dollars.</summary>
    public decimal Rate { get; set; }

    public LoadStatus Status { get; set; } = LoadStatus.Available;

    /// <summary>Null until a carrier is assigned (booked).</summary>
    public int? CarrierId { get; set; }

    /// <summary>Navigation property so EF Core can join to the Carriers table.</summary>
    public Carrier? Carrier { get; set; }
}
