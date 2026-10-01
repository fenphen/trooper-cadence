# ---------------------------------------------------------------------------
# Multi-stage build: compile with the full SDK image, then copy only the
# published output into the much smaller ASP.NET runtime image.
# Build:  docker build -t mini-load-board .
# Run:    docker run --rm -p 5000:8080 mini-load-board   ->  http://localhost:5000
# ---------------------------------------------------------------------------

# ---- Stage 1: build --------------------------------------------------------
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Restore first, on its own layer, so Docker can cache NuGet packages between
# builds as long as the .csproj has not changed.
COPY src/MiniLoadBoard.Api/MiniLoadBoard.Api.csproj src/MiniLoadBoard.Api/
RUN dotnet restore src/MiniLoadBoard.Api

COPY src/ src/
RUN dotnet publish src/MiniLoadBoard.Api -c Release -o /app/publish --no-restore

# ---- Stage 2: runtime ------------------------------------------------------
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .

# The ASP.NET 8 images listen on 8080 by default; we map it in docker-compose.
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "MiniLoadBoard.Api.dll"]
