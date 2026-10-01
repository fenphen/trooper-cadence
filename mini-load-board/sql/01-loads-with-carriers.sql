-- 01: Loads joined to their carriers
--
-- Tester use: the "source of truth" view of the load board. Run this after a
-- UI or API test and compare it with what the screen/response showed - e.g.
-- "did assigning Great Lakes Freight to load 6 really write CarrierId = 2?".
--
-- LEFT JOIN (not INNER JOIN) so unassigned loads still appear, with NULL
-- carrier columns. An INNER JOIN would silently hide every Available load -
-- a classic cause of "the report is missing rows" bugs.
SELECT
    l.Id            AS LoadId,
    l.Origin,
    l.Destination,
    l.PickupDate,
    l.Weight,
    l.Rate,
    l.Status,
    c.Name          AS CarrierName,
    c.McNumber,
    c.IsActive      AS CarrierIsActive
FROM Loads AS l
LEFT JOIN Carriers AS c ON c.Id = l.CarrierId
ORDER BY l.Id;
