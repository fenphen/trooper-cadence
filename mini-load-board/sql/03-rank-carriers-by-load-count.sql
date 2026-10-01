-- 03: Window function - rank carriers by how many loads they have hauled
--
-- Tester use: checking a "Top carriers" leaderboard. RANK() OVER (...) assigns
-- the position without collapsing the rows the way GROUP BY alone would, and
-- ties get the same rank (1, 1, 3 ...). DENSE_RANK would give 1, 1, 2.
--
-- LEFT JOIN from Carriers so carriers with ZERO loads still get a rank -
-- a leaderboard that drops them is a bug worth reporting.
SELECT
    c.Id,
    c.Name,
    c.IsActive,
    COUNT(l.Id)                                        AS LoadCount,
    COALESCE(SUM(l.Rate), 0)                           AS TotalRevenue,
    RANK()       OVER (ORDER BY COUNT(l.Id) DESC)      AS LoadRank,
    DENSE_RANK() OVER (ORDER BY COUNT(l.Id) DESC)      AS DenseLoadRank
FROM Carriers AS c
LEFT JOIN Loads AS l ON l.CarrierId = c.Id
GROUP BY c.Id, c.Name, c.IsActive
ORDER BY LoadRank, c.Name;
