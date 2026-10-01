-- 02: Aggregation - average, min, max rate and load count per origin city
--
-- Tester use: validating a reporting/analytics feature ("Lane pricing by
-- origin"). Compute the expected numbers straight from the database and
-- compare them with what the report or dashboard shows. ROUND keeps the
-- comparison free of floating-point noise.
SELECT
    Origin,
    COUNT(*)              AS LoadCount,
    ROUND(AVG(Rate), 2)   AS AvgRate,
    MIN(Rate)             AS MinRate,
    MAX(Rate)             AS MaxRate,
    SUM(Weight)           AS TotalWeightLbs
FROM Loads
GROUP BY Origin
HAVING COUNT(*) >= 1          -- raise this to 2 to see only repeat lanes
ORDER BY AvgRate DESC;
