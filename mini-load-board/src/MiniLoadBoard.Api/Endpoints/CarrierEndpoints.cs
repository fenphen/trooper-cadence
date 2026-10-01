using Microsoft.EntityFrameworkCore;
using MiniLoadBoard.Api.Data;

namespace MiniLoadBoard.Api.Endpoints;

public static class CarrierEndpoints
{
    public static void MapCarrierEndpoints(this WebApplication app)
    {
        var group = app.MapGroup("/api/carriers").WithTags("Carriers");

        // GET /api/carriers - every carrier, active and inactive.
        group.MapGet("/", async (AppDbContext db) =>
                await db.Carriers.OrderBy(c => c.Id).ToListAsync())
            .WithSummary("List all carriers");
    }
}
