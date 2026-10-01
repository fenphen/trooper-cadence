-- 04: CTE (Common Table Expression) - loads whose pickup date has passed but
--     which are still waiting (Available or Booked)
--
-- Tester use: a CTE breaks a complicated question into named steps, which
-- makes the query reviewable in a pull request and reusable in a test.
-- Here "stale" loads are operational problems a dispatcher should see on a
-- warning list; if the app has such a feature this query is its oracle.
--
-- SQLite stores our dates as ISO text (YYYY-MM-DD), so string comparison with
-- date('now') works. Other databases would use a real DATE column.
WITH stale_loads AS (
    SELECT
        Id,
        Origin,
        Destination,
        PickupDate,
        Status,
        CarrierId,
        CAST(julianday('now') - julianday(PickupDate) AS INTEGER) AS DaysOverdue
    FROM Loads
    WHERE Status IN ('Available', 'Booked')
      AND PickupDate < date('now')
)
SELECT
    s.Id,
    s.Origin || ' -> ' || s.Destination AS Lane,
    s.PickupDate,
    s.DaysOverdue,
    s.Status,
    COALESCE(c.Name, '(no carrier)')     AS Carrier
FROM stale_loads AS s
LEFT JOIN Carriers AS c ON c.Id = s.CarrierId
ORDER BY s.DaysOverdue DESC;
