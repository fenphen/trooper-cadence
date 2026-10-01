// ---------------------------------------------------------------------------
// Mini Load Board - entry point.
// ASP.NET Core "minimal API" style: everything is configured in this one file
// with no controllers. Read it top to bottom: register services, then build
// the app, then set up the HTTP pipeline (middleware) and endpoints.
// ---------------------------------------------------------------------------
using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;
using MiniLoadBoard.Api.Auth;
using MiniLoadBoard.Api.Data;
using MiniLoadBoard.Api.Endpoints;

var builder = WebApplication.CreateBuilder(args);

// 1) SERVICES ---------------------------------------------------------------

// EF Core with SQLite. The connection string lives in appsettings.json
// ("Data Source=loadboard.db" = a file next to the app).
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(builder.Configuration.GetConnectionString("LoadBoard")));

// Send/receive enums as text ("Booked") rather than numbers (1) in JSON.
builder.Services.ConfigureHttpJsonOptions(options =>
    options.SerializerOptions.Converters.Add(new JsonStringEnumConverter()));

// OpenAPI / Swagger: documents every endpoint and gives a "Try it out" UI.
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    // Adds an "Authorize" button in Swagger UI so you can enter the API key once.
    c.AddSecurityDefinition("ApiKey", new Microsoft.OpenApi.Models.OpenApiSecurityScheme
    {
        Name = ApiKeyMiddleware.HeaderName,
        In = Microsoft.OpenApi.Models.ParameterLocation.Header,
        Type = Microsoft.OpenApi.Models.SecuritySchemeType.ApiKey,
        Description = $"Use {ApiKeyMiddleware.ValidKey}"
    });
    c.AddSecurityRequirement(new Microsoft.OpenApi.Models.OpenApiSecurityRequirement
    {
        [new Microsoft.OpenApi.Models.OpenApiSecurityScheme
        {
            Reference = new Microsoft.OpenApi.Models.OpenApiReference
            {
                Type = Microsoft.OpenApi.Models.ReferenceType.SecurityScheme,
                Id = "ApiKey"
            }
        }] = Array.Empty<string>()
    });
});

var app = builder.Build();

// 2) DATABASE ---------------------------------------------------------------
// Start from a clean, known database every time the app starts so tests are
// repeatable. (Set "ResetDatabaseOnStartup": false in appsettings.json to keep data.)
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    if (app.Configuration.GetValue("ResetDatabaseOnStartup", true))
        db.Database.EnsureDeleted();
    db.Database.EnsureCreated();
    SeedData.Initialize(db);
}

// 3) HTTP PIPELINE (order matters!) -----------------------------------------
app.UseSwagger();      // serves /swagger/v1/swagger.json
app.UseSwaggerUI();    // serves the UI at /swagger

app.UseDefaultFiles(); // "/" -> "/index.html"
app.UseStaticFiles();  // serves everything in wwwroot (our HTML/CSS/JS frontend)

app.UseMiddleware<ApiKeyMiddleware>(); // fake auth for POST/PUT/DELETE

// 4) ENDPOINTS --------------------------------------------------------------
app.MapLoadEndpoints();
app.MapCarrierEndpoints();

app.Run();

// Makes the auto-generated Program class public, which is handy if you later
// want in-memory integration tests with WebApplicationFactory<Program>.
public partial class Program { }
