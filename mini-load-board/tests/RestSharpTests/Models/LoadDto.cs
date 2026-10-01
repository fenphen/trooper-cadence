using System.Text.Json.Serialization;

namespace RestSharpTests.Models;

/// <summary>The API sends statuses as strings ("Booked"); this converter maps them onto the enum.</summary>
[JsonConverter(typeof(JsonStringEnumConverter))]
public enum LoadStatus
{
    Available,
    Booked,
    InTransit,
    Delivered
}

/// <summary>Mirror of the API's Load JSON (a "Data Transfer Object").</summary>
public class LoadDto
{
    public int Id { get; set; }
    public string Origin { get; set; } = "";
    public string Destination { get; set; } = "";
    public DateOnly PickupDate { get; set; }
    public int Weight { get; set; }
    public decimal Rate { get; set; }
    public LoadStatus Status { get; set; }
    public int? CarrierId { get; set; }
    public CarrierDto? Carrier { get; set; }
}
