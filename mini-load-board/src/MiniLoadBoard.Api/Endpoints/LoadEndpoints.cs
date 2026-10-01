using Microsoft.EntityFrameworkCore;
using MiniLoadBoard.Api.Data;
using MiniLoadBoard.Api.Models;

namespace MiniLoadBoard.Api.Endpoints;

/// <summary>
/// All /api/loads endpoints. Minimal APIs map a URL + HTTP verb straight to a lambda.
/// The parameters of each lambda are filled in automatically:
///   - route values ({id}) by name,
///   - query string values (?status=) by name,
///   - the JSON body into a record type,
///   - services such as AppDbContext from dependency injection.
/// </summary>
public static class LoadEndpoints
{
    public const int MinWeight = 1;
    public const int MaxWeight = 48000;

    public static void MapLoadEndpoints(this WebApplication app)
    {
        var group = app.MapGroup("/api/loads").WithTags("Loads");

        // GET /api/loads?status=Available&origin=Dallas
        group.MapGet("/", async (string? status, string? origin, AppDbContext db) =>
        {
            IQueryable<Load> query = db.Loads.Include(l => l.Carrier);

            if (!string.IsNullOrWhiteSpace(status))
            {
                if (!Enum.TryParse<LoadStatus>(status, ignoreCase: true, out var parsedStatus))
                    return Results.BadRequest(new { error = $"Unknown status '{status}'. Use Available, Booked, InTransit or Delivered." });

                query = query.Where(l => l.Status == parsedStatus);
            }

            if (!string.IsNullOrWhiteSpace(origin))
            {
                var term = origin.Trim();
                query = query.Where(l => l.Origin.Contains(term));
            }

            var loads = await query.OrderBy(l => l.Id).ToListAsync();
            return Results.Ok(loads);
        })
        .WithSummary("List loads, optionally filtered by status and/or origin");

        // GET /api/loads/5
        group.MapGet("/{id:int}", async (int id, AppDbContext db) =>
        {
            var load = await db.Loads.Include(l => l.Carrier).FirstOrDefaultAsync(l => l.Id == id);
            return load is null
                ? Results.NotFound(new { error = $"Load {id} not found." })
                : Results.Ok(load);
        })
        .WithSummary("Get a single load");

        // POST /api/loads
        group.MapPost("/", async (CreateLoadRequest request, AppDbContext db) =>
        {
            var errors = Validate(request);
            if (errors.Count > 0)
            {
                // Returns a standard "ValidationProblemDetails" JSON body (RFC 7807):
                // { "title": "...", "status": 400, "errors": { "Weight": ["..."] } }
                return Results.ValidationProblem(errors);
            }

            var load = new Load
            {
                Origin = request.Origin!.Trim(),
                Destination = request.Destination!.Trim(),
                PickupDate = request.PickupDate!.Value,
                Weight = request.Weight!.Value,
                Rate = request.Rate!.Value,
                Status = LoadStatus.Available
            };
            db.Loads.Add(load);
            await db.SaveChangesAsync();

            // 201 Created + a Location header pointing at the new resource.
            return Results.Created($"/api/loads/{load.Id}", load);
        })
        .WithSummary("Post a new load (requires X-Api-Key)");

        // PUT /api/loads/5/assign/2
        group.MapPut("/{id:int}/assign/{carrierId:int}", async (int id, int carrierId, AppDbContext db) =>
        {
            var load = await db.Loads.FindAsync(id);
            if (load is null) return Results.NotFound(new { error = $"Load {id} not found." });

            var carrier = await db.Carriers.FindAsync(carrierId);
            if (carrier is null) return Results.NotFound(new { error = $"Carrier {carrierId} not found." });

            if (load.Status != LoadStatus.Available)
                return Results.BadRequest(new { error = $"Only Available loads can be assigned. Load {id} is {load.Status}." });

            if (!carrier.IsActive)
                return Results.BadRequest(new { error = $"Carrier '{carrier.Name}' is inactive and cannot be assigned loads." });

            load.CarrierId = carrier.Id;
            load.Status = LoadStatus.Booked;
            await db.SaveChangesAsync();

            load.Carrier = carrier;
            return Results.Ok(load);
        })
        .WithSummary("Assign a carrier to an Available load (requires X-Api-Key)");

        // PUT /api/loads/5/status   body: { "status": "InTransit" }
        group.MapPut("/{id:int}/status", async (int id, UpdateStatusRequest request, AppDbContext db) =>
        {
            if (request.Status is null)
                return Results.ValidationProblem(new Dictionary<string, string[]>
                {
                    ["Status"] = ["Status is required."]
                });

            var load = await db.Loads.Include(l => l.Carrier).FirstOrDefaultAsync(l => l.Id == id);
            if (load is null) return Results.NotFound(new { error = $"Load {id} not found." });

            var newStatus = request.Status.Value;
            if (!IsValidTransition(load.Status, newStatus))
                return Results.BadRequest(new { error = $"Cannot change status from {load.Status} to {newStatus}." });

            load.Status = newStatus;
            await db.SaveChangesAsync();
            return Results.Ok(load);
        })
        .WithSummary("Move a load to its next status (requires X-Api-Key)");

        // DELETE /api/loads/5
        group.MapDelete("/{id:int}", async (int id, AppDbContext db) =>
        {
            var load = await db.Loads.FindAsync(id);
            if (load is null) return Results.NotFound(new { error = $"Load {id} not found." });

            if (load.Status != LoadStatus.Available)
                return Results.BadRequest(new { error = $"Only Available loads can be deleted. Load {id} is {load.Status}." });

            db.Loads.Remove(load);
            await db.SaveChangesAsync();
            return Results.NoContent(); // 204
        })
        .WithSummary("Delete an Available load (requires X-Api-Key)");
    }

    /// <summary>
    /// Server-side validation for a new load. Returns a dictionary of
    /// field name -> error messages (empty when everything is valid).
    /// Never trust the browser: the frontend validates too, but anyone can call the API directly.
    /// </summary>
    private static Dictionary<string, string[]> Validate(CreateLoadRequest r)
    {
        var errors = new Dictionary<string, string[]>();

        if (string.IsNullOrWhiteSpace(r.Origin))
            errors["Origin"] = ["Origin is required."];

        if (string.IsNullOrWhiteSpace(r.Destination))
            errors["Destination"] = ["Destination is required."];

        if (r.PickupDate is null)
            errors["PickupDate"] = ["Pickup date is required."];
        else if (r.PickupDate.Value < DateOnly.FromDateTime(DateTime.UtcNow))
            errors["PickupDate"] = ["Pickup date cannot be in the past."];

        if (r.Weight is null)
            errors["Weight"] = ["Weight is required."];
        else if (r.Weight < MinWeight || r.Weight >= MaxWeight)
            errors["Weight"] = [$"Weight must be between {MinWeight:N0} and {MaxWeight:N0} lbs."];

        if (r.Rate is null)
            errors["Rate"] = ["Rate is required."];
        else if (r.Rate <= 0)
            errors["Rate"] = ["Rate must be greater than 0."];

        return errors;
    }

    /// <summary>
    /// Business rule: once booked, a load moves forward through the lifecycle
    /// (Booked -> InTransit -> Delivered). It can never go backwards, and
    /// "Available -> Booked" only happens through the assign endpoint.
    /// </summary>
    private static bool IsValidTransition(LoadStatus current, LoadStatus next)
    {
        if (current == LoadStatus.Available) return false;
        return next > current;
    }
}
