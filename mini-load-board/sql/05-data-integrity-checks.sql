-- 05: Data integrity checks - rows that break the business rules
--
-- Tester use: run this after a test suite, a data migration, or against a
-- production copy. Every row returned is a bug (either the app let bad data
-- in, or an import did). An empty result set is the "pass" condition, which
-- makes this easy to automate: SELECT COUNT(*) ... and assert it is 0.
--
-- The seed data deliberately contains one offender (a Delivered load with no
-- carrier) so you can see the query working.
SELECT 'Booked/InTransit/Delivered load with no carrier' AS Problem, Id AS LoadId, Status, CarrierId, Weight, Rate
FROM Loads
WHERE Status IN ('Booked', 'InTransit', 'Delivered') AND CarrierId IS NULL

UNION ALL

SELECT 'Available load that already has a carrier', Id, Status, CarrierId, Weight, Rate
FROM Loads
WHERE Status = 'Available' AND CarrierId IS NOT NULL

UNION ALL

SELECT 'Carrier id points at a carrier that does not exist', l.Id, l.Status, l.CarrierId, l.Weight, l.Rate
FROM Loads AS l
LEFT JOIN Carriers AS c ON c.Id = l.CarrierId
WHERE l.CarrierId IS NOT NULL AND c.Id IS NULL

UNION ALL

SELECT 'Weight outside 1-48000 lbs', Id, Status, CarrierId, Weight, Rate
FROM Loads
WHERE Weight < 1 OR Weight > 48000

UNION ALL

SELECT 'Rate is zero or negative', Id, Status, CarrierId, Weight, Rate
FROM Loads
WHERE Rate <= 0

UNION ALL

SELECT 'Unknown status value', Id, Status, CarrierId, Weight, Rate
FROM Loads
WHERE Status NOT IN ('Available', 'Booked', 'InTransit', 'Delivered')

UNION ALL

SELECT 'Active (Booked/InTransit) load assigned to an INACTIVE carrier', l.Id, l.Status, l.CarrierId, l.Weight, l.Rate
FROM Loads AS l
JOIN Carriers AS c ON c.Id = l.CarrierId
WHERE l.Status IN ('Booked', 'InTransit') AND c.IsActive = 0

ORDER BY Problem, LoadId;
