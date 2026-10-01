-- 06: Status breakdown with a CASE expression and a percentage
--
-- Tester use: a quick cross-check for the API's filters. The LoadCount per
-- status here must equal the number of rows returned by
-- GET /api/loads?status=<Status>. The CASE column shows how to bucket values
-- (handy for "is this lifecycle stage open or closed?" style reports).
--
-- The window function SUM(COUNT(*)) OVER () gives the grand total on every
-- row without a second query.
SELECT
    Status,
    COUNT(*)                                                       AS LoadCount,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)             AS PercentOfAll,
    CASE
        WHEN Status IN ('Available', 'Booked') THEN 'Open'
        WHEN Status = 'InTransit'               THEN 'Moving'
        ELSE 'Closed'
    END                                                            AS Bucket,
    SUM(Rate)                                                      AS TotalRate
FROM Loads
GROUP BY Status
ORDER BY CASE Status
    WHEN 'Available' THEN 1
    WHEN 'Booked'    THEN 2
    WHEN 'InTransit' THEN 3
    ELSE 4
END;
