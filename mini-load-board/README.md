# Mini Load Board - SDET practice project

A tiny freight-brokerage "load board" built to practise the test stack used at
many logistics companies: **ASP.NET Core + EF Core/SQLite** on the backend,
plain **HTML/JS** on the front, and three independent test suites - **Playwright
(TypeScript)**, **RestSharp + NUnit (C#)** and **Selenium + NUnit (C#)** - plus
SQL practice queries, Docker files and a GitHub Actions pipeline.

Everything is free and runs locally.

> **Three bugs are planted in the app on purpose.** Some tests fail until you
> find and fix them. Try it with the tests first, then check `BUG_ANSWERS.md`.

---

## 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| .NET SDK | 8.0.x | `dotnet --version` |
| Node.js | 20+ | `node --version` |
| Google Chrome | any recent | needed by Selenium (Playwright brings its own browser) |
| (optional) `sqlite3` CLI | any | for the SQL practice queries |
| (optional) Docker Desktop | any | for the Dockerfile / docker-compose |

## 2. Run the app

```bash
cd mini-load-board
dotnet run --project src/MiniLoadBoard.Api --urls http://localhost:5000
```

Then open:

- http://localhost:5000 - the load board UI
- http://localhost:5000/swagger - Swagger / OpenAPI "try it out" page
- http://localhost:5000/api/loads - raw JSON

The SQLite database (`src/MiniLoadBoard.Api/loadboard.db`) is **deleted and
re-seeded every time the app starts** (10 + 1 loads, 5 carriers), so the tests
always start from a known state. Set `"ResetDatabaseOnStartup": false` in
`appsettings.json` to keep data between runs.

Write requests (POST/PUT/DELETE) need the header `X-Api-Key: test-key-123`.
In Swagger, click **Authorize** and paste the key once.

```bash
# Quick smoke test from a terminal
curl http://localhost:5000/api/carriers
curl -X POST http://localhost:5000/api/loads -H "X-Api-Key: test-key-123" \
     -H "Content-Type: application/json" \
     -d '{"origin":"Austin, TX","destination":"Tulsa, OK","pickupDate":"2030-01-15","weight":30000,"rate":1500}'
```

## 3. Run the test suites

All suites expect the app on `http://localhost:5000` (override with the
`LOADBOARD_URL` env var for the C# suites, `BASE_URL` for Playwright).

### 3a. Playwright (TypeScript) - UI, API and accessibility

Playwright **starts the app itself** (see `webServer` in `playwright.config.ts`),
so you don't need `dotnet run` first - but if the app is already running it
reuses it.

```bash
cd tests/playwright
npm install
npx playwright install chromium     # one-time browser download
npx playwright test                 # run everything
npx playwright test --headed        # watch the browser
npx playwright test tests/api       # just the API tests
npx playwright test -g "48,000"     # one test by name
npx playwright show-report          # open the HTML report
npx playwright test --ui            # interactive time-travel UI mode
```

### 3b. RestSharp + NUnit (C#) - API tests

```bash
# terminal 1
dotnet run --project src/MiniLoadBoard.Api --urls http://localhost:5000
# terminal 2
dotnet test tests/RestSharpTests
dotnet test tests/RestSharpTests --filter "FullyQualifiedName~StatusTransition"   # one fixture
dotnet test tests/RestSharpTests --logger "console;verbosity=normal"               # see every test name
```

### 3c. Selenium + NUnit (C#) - UI tests

Needs Chrome installed. Selenium Manager (built into Selenium 4.6+) downloads a
matching chromedriver automatically on first run.

```bash
# app running in another terminal, then:
dotnet test tests/SeleniumTests                # opens a real Chrome window
HEADLESS=true dotnet test tests/SeleniumTests  # headless (Windows PowerShell: $env:HEADLESS="true")
```

Optional overrides for locked-down machines: `CHROME_BINARY=/path/to/chrome`
and `CHROMEDRIVER_PATH=/path/to/chromedriver`.

### 3d. SQL practice queries

```bash
./sql/run-all.sh                                   # runs all six against loadboard.db
sqlite3 -header -column src/MiniLoadBoard.Api/loadboard.db < sql/05-data-integrity-checks.sql
```

(No `sqlite3` CLI? Open the `.db` file with the free [DB Browser for SQLite](https://sqlitebrowser.org/)
or the VS Code "SQLite Viewer" extension and paste the queries in.)

### 3e. Docker

```bash
docker compose up --build        # app on http://localhost:5000
```

### 3f. Everything (the way CI does it)

```bash
dotnet build MiniLoadBoard.sln
dotnet run --project src/MiniLoadBoard.Api --urls http://localhost:5000 &   # background
dotnet test tests/RestSharpTests
HEADLESS=true dotnet test tests/SeleniumTests
kill %1                                                                      # stop the app
cd tests/playwright && npm ci && npx playwright test                         # starts its own app
```

The GitHub Actions workflow (`.github/workflows/tests.yml` at the repo root)
runs exactly these steps on every push and uploads the Playwright HTML report
and the `.trx` results as artifacts.

## 4. Expected results (before fixing the planted bugs)

| Suite | Result | Failing tests |
|---|---|---|
| Playwright | 20 passed, **4 failed** | `accepts the 48,000 lb boundary` (API), `accepts the maximum legal weight of 48,000 lbs` (UI), `rejects skipping from Booked straight to Delivered`, `origin search ignores letter case` |
| RestSharp | 46 passed, **3 failed** | `Weight_48000_IsAccepted`, `Booked_To_Delivered_SkippingInTransit_IsRejected`, `GetLoads_FilterByOrigin_IsCaseInsensitive` |
| Selenium | 4 passed, **1 failed** | `Board_SearchByOrigin_IgnoresCase` |

Fix the bugs (answers in `BUG_ANSWERS.md`) and everything goes green.

---

## 5. Folder structure

```
mini-load-board/
├── MiniLoadBoard.sln                 # app + both C# test projects
├── src/MiniLoadBoard.Api/            # ASP.NET Core minimal API (.NET 8)
│   ├── Program.cs                    #   services, DB reset/seed, middleware, endpoints
│   ├── Auth/ApiKeyMiddleware.cs      #   fake auth: X-Api-Key on POST/PUT/DELETE
│   ├── Data/AppDbContext.cs          #   EF Core DbContext (SQLite)
│   ├── Data/SeedData.cs              #   the 11 loads and 5 carriers
│   ├── Endpoints/LoadEndpoints.cs    #   /api/loads  (validation + status rules live here)
│   ├── Endpoints/CarrierEndpoints.cs #   /api/carriers
│   ├── Models/                       #   Load, Carrier, request DTOs
│   └── wwwroot/                      #   static frontend: index / post-load / load.html + js/ + css/
├── tests/
│   ├── playwright/                   # TypeScript
│   │   ├── playwright.config.ts      #   webServer, baseURL, reporters, traces
│   │   ├── pages/                    #   Page Object Model classes
│   │   ├── helpers/api.ts            #   API helpers used to arrange test data
│   │   └── tests/{ui,api,a11y}/      #   the specs
│   ├── RestSharpTests/               # C# NUnit API tests
│   │   ├── Api/ApiClientBase.cs      #   base URL + API key handling
│   │   ├── Api/LoadBoardApiClient.cs #   one typed method per endpoint
│   │   ├── Models/                   #   LoadDto, CarrierDto, CreateLoadRequest, error shapes
│   │   └── Tests/                    #   positive / negative / boundary / end-to-end fixtures
│   └── SeleniumTests/                # C# NUnit UI tests
│       ├── Drivers/WebDriverFactory.cs   # Chrome setup, HEADLESS env var
│       ├── Pages/                        # Page Object Model + explicit-wait helpers
│       ├── Support/ApiHelper.cs          # tiny HttpClient helper for test setup
│       └── Tests/                        # 5 UI tests (+ the Selenium-vs-Playwright comparison comment)
├── sql/                              # 6 commented practice queries + run-all.sh
├── Dockerfile / docker-compose.yml   # containerised app
├── BUG_ANSWERS.md                    # the three planted bugs (spoilers!)
└── .github/workflows/tests.yml       # (at the repo root) CI pipeline
```

---

## 6. Interview talking points

**ASP.NET Core minimal API** - the lightweight way to build HTTP APIs in .NET:
endpoints are lambdas mapped to routes in `Program.cs`, with dependency
injection (the `AppDbContext` parameter), model binding (JSON -> `CreateLoadRequest`)
and `Results.*` helpers for status codes. Testers benefit from knowing it
because reading the endpoint tells you exactly which inputs are validated and
which status codes to expect.

**Entity Framework Core + SQLite** - EF Core is the ORM: C# classes map to
tables, LINQ queries become SQL. SQLite is a zero-install file database, ideal
for local practice and fast test runs. Knowing *how* LINQ translates to SQL
matters - Bug 3 exists because `Contains` becomes a case-sensitive `instr()`
on SQLite.

**Swagger / OpenAPI** - machine-readable contract of the API (`/swagger/v1/swagger.json`)
and a UI to poke at it. First stop when exploring a new API; also the input
for contract testing and client-code generation.

**Playwright** - Microsoft's browser automation library with its own test
runner. Strengths: auto-waiting (no flaky sleeps), role-based locators that
mirror accessibility, built-in API testing via the `request` fixture, tracing
and HTML reports, parallel isolated browser contexts, `webServer` to start the
app under test. Used here for UI + API + accessibility tests.

**Page Object Model (POM)** - one class per page that owns the locators and
user actions (`board.filterByStatus("Booked")`). Tests read like requirements;
a UI change is fixed in one place. Compare `tests/playwright/pages/` with
`tests/SeleniumTests/Pages/` - same idea, two tools.

**`data-testid` attributes** - stable hooks for locators that don't break when
styling or copy changes. Prefer `getByRole` where it's natural (buttons, links,
headings) because it also proves the page is accessible; use test ids for
things with no good role (table cells, status pills).

**RestSharp** - a popular .NET HTTP client with a fluent API (`AddHeader`,
`AddJsonBody`, `AddQueryParameter`). The `ApiClientBase` class shows the key
pattern: centralise base URL/auth/serialisation once, keep tests focused on
behaviour. Tests assert on status code, headers (`Location`) *and* body, and
re-read the resource afterwards to prove persistence.

**NUnit** - the test framework for both C# suites. `[TestCase]` gives
data-driven tests (the weight boundaries), `Assert.Multiple` reports every
failed assertion at once, `[SetUp]/[TearDown]` manage the browser lifecycle.

**Selenium WebDriver** - the long-standing standard for browser automation,
with a W3C protocol and bindings in every language. We use **explicit waits**
(`WebDriverWait` + a lambda) and never `Thread.Sleep`; Selenium Manager handles
the driver binary. See the comparison comment in `Tests/UiTestBase.cs`.

**Test design techniques on show** - boundary value analysis (weight 0/1/48000/48001),
negative testing (missing fields, bad auth, illegal transitions), state-transition
testing (the Booked -> InTransit -> Delivered machine), end-to-end scenario
(`EndToEndFlowTests`), arrange-through-the-API / act-through-the-UI, and
test independence (every mutating test creates its own load).

**Accessibility testing** - `@axe-core/playwright` runs the axe rules engine
over the rendered page and fails on serious/critical WCAG violations. Cheap to
add, catches ~30-50% of a11y issues automatically.

**SQL for testers** - joins to verify relationships, aggregations to check
reports, window functions for rankings, CTEs for readable multi-step logic, and
integrity queries whose "pass" condition is zero rows. Query 05 finds the seeded
Delivered-with-no-carrier record on purpose.

**Docker / docker-compose** - the app runs identically on any machine; the
test suites just point at `localhost:5000`. Multi-stage build keeps the image
small.

**GitHub Actions** - CI runs build -> API tests -> Selenium (headless) ->
Playwright on every push and publishes the Playwright report as an artifact.
`if: ${{ !cancelled() }}` makes every suite run even when an earlier one fails.

---

## 7. Ideas for extending the tests with AI (Claude, Copilot)

- **Generate test cases from the spec.** Paste `LoadEndpoints.cs` (or the
  Swagger JSON) and ask: *"List every validation rule and status-code path and
  write an NUnit `[TestCase]` table covering them, including boundaries."*
  Then review what it missed - that review is the skill.
- **Turn a bug report into a regression test.** *"Here is the failing
  curl + response; write a Playwright API test that reproduces it."*
- **Page objects from HTML.** Paste `load.html` and ask for a Page Object with
  locators that prefer `getByRole`, falling back to `data-testid`.
- **Translate between stacks.** *"Convert this Selenium test to Playwright"*
  (or the reverse) - great for comparing the two in an interview.
- **Explain a flaky test.** Paste the trace/log and ask for likely race
  conditions and which explicit wait would fix it.
- **SQL oracles.** *"Write a query that computes the expected result of
  GET /api/loads?status=Booked&origin=Dallas so I can compare it with the API."*
- **Data generation.** Ask for 50 realistic loads (real US lanes, plausible
  weights/rates) as JSON for a load test or for seeding.
- **Review your own tests.** *"Which of these tests could pass vacuously?"*
  (hint: `[].every(...)` is `true`), *"Which assertions are too weak?"*.
- **Accessibility fixes.** Paste the axe violation JSON and ask for the minimal
  HTML change that resolves it.
- **CI troubleshooting.** Paste a failed GitHub Actions log and ask for the root
  cause and a fix to the workflow YAML.
- **Use GitHub Copilot in VS Code / Visual Studio** for inline completions of
  repetitive assertions and DTOs; use **Claude Code** in the terminal to do
  multi-file changes such as "add a `/api/carriers/{id}` endpoint, a RestSharp
  test and a Playwright API test for it".

Always run the generated tests, read them critically, and make sure at least
one would fail if the feature were broken - AI is happy to write a test that
asserts nothing.
