using Microsoft.EntityFrameworkCore;
using MiniLoadBoard.Api.Models;

namespace MiniLoadBoard.Api.Data;

/// <summary>
/// The EF Core "unit of work". Each DbSet maps to a table in the SQLite database.
/// </summary>
public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<Load> Loads => Set<Load>();
    public DbSet<Carrier> Carriers => Set<Carrier>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Load>(load =>
        {
            // Store the status as readable text ("Booked") instead of a number (1).
            // This makes the SQL practice queries in /sql much easier to read.
            load.Property(l => l.Status).HasConversion<string>();

            // SQLite has no native decimal type, so store money as REAL (a double).
            // That lets SQL functions like AVG() and ORDER BY work on the column.
            load.Property(l => l.Rate).HasConversion<double>();

            // A load optionally points at a carrier. If a carrier is deleted,
            // don't delete its loads - just clear the reference.
            load.HasOne(l => l.Carrier)
                .WithMany()
                .HasForeignKey(l => l.CarrierId)
                .OnDelete(DeleteBehavior.SetNull);
        });
    }
}
