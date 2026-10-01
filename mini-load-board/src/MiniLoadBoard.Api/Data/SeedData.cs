using MiniLoadBoard.Api.Models;

namespace MiniLoadBoard.Api.Data;

/// <summary>
/// Puts a small, predictable set of demo data into an empty database.
/// Tests and the SQL practice queries rely on this data, so change it carefully.
/// </summary>
public static class SeedData
{
    public static void Initialize(AppDbContext db)
    {
        // Only seed an empty database.
        if (db.Carriers.Any()) return;

        var carriers = new List<Carrier>
        {
            new() { Name = "Lone Star Logistics",   McNumber = "MC-100001", Rating = 5, IsActive = true },
            new() { Name = "Great Lakes Freight",   McNumber = "MC-100002", Rating = 4, IsActive = true },
            new() { Name = "Peach State Haulers",   McNumber = "MC-100003", Rating = 3, IsActive = true },
            new() { Name = "Rocky Mountain Movers", McNumber = "MC-100004", Rating = 4, IsActive = true },
            // An inactive carrier so we can test "cannot assign inactive carrier".
            new() { Name = "Budget Trucking Co",    McNumber = "MC-100005", Rating = 1, IsActive = false },
        };
        db.Carriers.AddRange(carriers);
        db.SaveChanges(); // SaveChanges fills in the generated Ids.

        // Dates are relative to "today" so Available loads always have a future pickup date.
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        var lone = carriers[0].Id;
        var lakes = carriers[1].Id;
        var peach = carriers[2].Id;
        var rocky = carriers[3].Id;

        db.Loads.AddRange(
            new Load { Origin = "Dallas, TX",      Destination = "Atlanta, GA",     PickupDate = today.AddDays(2),  Weight = 42000, Rate = 2450m, Status = LoadStatus.Available },
            new Load { Origin = "Dallas, TX",      Destination = "Denver, CO",      PickupDate = today.AddDays(3),  Weight = 38000, Rate = 2100m, Status = LoadStatus.Available },
            new Load { Origin = "Chicago, IL",     Destination = "Columbus, OH",    PickupDate = today.AddDays(1),  Weight = 25000, Rate = 1150m, Status = LoadStatus.Available },
            new Load { Origin = "Atlanta, GA",     Destination = "Miami, FL",       PickupDate = today.AddDays(4),  Weight = 30000, Rate = 1800m, Status = LoadStatus.Available },
            new Load { Origin = "Denver, CO",      Destination = "Phoenix, AZ",     PickupDate = today.AddDays(5),  Weight = 44000, Rate = 2300m, Status = LoadStatus.Available },
            new Load { Origin = "Chicago, IL",     Destination = "Dallas, TX",      PickupDate = today.AddDays(1),  Weight = 40000, Rate = 2600m, Status = LoadStatus.Booked,    CarrierId = lakes },
            // Booked but the pickup date already passed - a "stale" load for the SQL practice queries.
            new Load { Origin = "Houston, TX",     Destination = "Memphis, TN",     PickupDate = today.AddDays(-2), Weight = 35000, Rate = 1650m, Status = LoadStatus.Booked,    CarrierId = lone },
            new Load { Origin = "Atlanta, GA",     Destination = "Charlotte, NC",   PickupDate = today.AddDays(-1), Weight = 22000, Rate = 950m,  Status = LoadStatus.InTransit, CarrierId = peach },
            new Load { Origin = "Dallas, TX",      Destination = "Houston, TX",     PickupDate = today.AddDays(-3), Weight = 46000, Rate = 900m,  Status = LoadStatus.Delivered, CarrierId = lone },
            new Load { Origin = "Denver, CO",      Destination = "Salt Lake City, UT", PickupDate = today.AddDays(-5), Weight = 28000, Rate = 1400m, Status = LoadStatus.Delivered, CarrierId = rocky },
            // A "legacy import" record with a data-quality problem: it is Delivered
            // but has no carrier. The SQL practice queries are meant to find it.
            new Load { Origin = "Memphis, TN",     Destination = "Nashville, TN",   PickupDate = today.AddDays(-10), Weight = 18000, Rate = 600m, Status = LoadStatus.Delivered, CarrierId = null }
        );
        db.SaveChanges();
    }
}
