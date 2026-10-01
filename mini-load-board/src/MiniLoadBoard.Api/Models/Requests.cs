namespace MiniLoadBoard.Api.Models;

// Request bodies ("DTOs") the API accepts. Every property is nullable on
// purpose: if a client leaves a field out we want to return a friendly
// "X is required" message instead of a JSON parsing error.

/// <summary>Body for POST /api/loads.</summary>
public record CreateLoadRequest(
    string? Origin,
    string? Destination,
    DateOnly? PickupDate,
    int? Weight,
    decimal? Rate);

/// <summary>Body for PUT /api/loads/{id}/status, e.g. { "status": "InTransit" }.</summary>
public record UpdateStatusRequest(LoadStatus? Status);
