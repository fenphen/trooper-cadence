# Planted bugs - answer key

> Don't read this until you've tried to find the bugs with the tests first!
> Run all three suites and look at which tests fail - each failure points at one
> of the bugs below.

All three bugs live in `src/MiniLoadBoard.Api/Endpoints/LoadEndpoints.cs`.

---

## Bug 1 - Off-by-one in the weight validation (48,000 lbs is rejected)

**Where:** `Validate()`:

```csharp
else if (r.Weight < MinWeight || r.Weight >= MaxWeight)
```

**What's wrong:** the spec says weight must be **1-48,000 inclusive**, but `>=`
rejects exactly 48,000. The error message even says "between 1 and 48,000",
and the browser's client-side check allows 48,000 - so the UI shows a confusing
"server rejected this load" message for a value it just told you was fine.

**Fix:**

```csharp
else if (r.Weight < MinWeight || r.Weight > MaxWeight)
```

**Tests that catch it:**

| Suite | Test |
|---|---|
| RestSharp | `LoadsPostTests.Weight_48000_IsAccepted` (the `[TestCase(48000, Created)]` boundary) |
| Playwright API | `POST /api/loads accepts the 48,000 lb boundary` |
| Playwright UI | `Post a Load form > accepts the maximum legal weight of 48,000 lbs` |

**Interview angle:** this is why *boundary value analysis* exists. Testing 0, 1,
48,000 and 48,001 costs four test cases and finds the most common class of
validation bug (`<` vs `<=`). Note that the Selenium suite does **not** catch it
- a good example of coverage gaps between suites.

---

## Bug 2 - A load can jump from Booked straight to Delivered

**Where:** `IsValidTransition()`:

```csharp
if (current == LoadStatus.Available) return false;
return next > current;
```

**What's wrong:** "`next > current`" only checks that the load moves *forward*
in the enum. It allows **Booked -> Delivered**, skipping InTransit - a load
that was never picked up gets marked delivered (and paid). The rule should be
"exactly one step forward".

**Fix:**

```csharp
if (current == LoadStatus.Available) return false;
return (int)next == (int)current + 1;
```

(or an explicit map: `Booked -> InTransit`, `InTransit -> Delivered`.)

**Tests that catch it:**

| Suite | Test |
|---|---|
| RestSharp | `StatusTransitionTests.Booked_To_Delivered_SkippingInTransit_IsRejected` |
| Playwright API | `PUT /api/loads/{id}/status rejects skipping from Booked straight to Delivered` |

**Interview angle:** the UI *cannot* trigger this bug because the "Mark
Delivered" button is disabled while a load is Booked. Only API-level tests find
it. That's the argument for testing business rules at the API layer and not
relying on front-end guards - anyone with the API key (or Swagger UI) can skip
the button.

---

## Bug 3 - The origin filter is case-sensitive

**Where:** the `GET /api/loads` handler:

```csharp
query = query.Where(l => l.Origin.Contains(term));
```

**What's wrong:** EF Core translates `string.Contains` for SQLite into
`instr(Origin, @term) > 0`, which is **case-sensitive**. Searching `dallas`
returns nothing, `Dallas` returns three loads. The status filter right next to
it *is* case-insensitive (`Enum.TryParse(..., ignoreCase: true)`), so the API is
inconsistent with itself - which is the kind of clue a tester should notice.

**Fix** (either works):

```csharp
query = query.Where(l => EF.Functions.Like(l.Origin, $"%{term}%")); // SQLite LIKE ignores ASCII case
// or
var lowered = term.ToLower();
query = query.Where(l => l.Origin.ToLower().Contains(lowered));
```

**Tests that catch it:**

| Suite | Test |
|---|---|
| RestSharp | `LoadsGetTests.GetLoads_FilterByOrigin_IsCaseInsensitive` |
| Playwright UI | `Load board > origin search ignores letter case` |
| Selenium | `LoadBoardTests.Board_SearchByOrigin_IgnoresCase` |

**Interview angle:** behaviour that depends on the database provider (SQLite vs
SQL Server collations) is a classic source of "works on my machine" bugs. It's
also a good reminder to assert on *non-empty* results: a test that only checks
"every returned row contains 'dallas'" passes vacuously when zero rows come
back.

---

## Scoreboard

After fixing all three bugs you should see:

| Suite | Before | After |
|---|---|---|
| Playwright | 20 passed / 4 failed | 24 passed |
| RestSharp | 46 passed / 3 failed | 49 passed |
| Selenium | 4 passed / 1 failed | 5 passed |
