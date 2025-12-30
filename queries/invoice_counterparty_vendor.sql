SELECT DISTINCT counterparty, vendor_name
FROM wasteology.dbo.sharepoint_gapi
WHERE sp_created_date >= '2025-01-01'
  AND vendor_name IS NOT NULL AND vendor_name != ''
  AND counterparty IS NOT NULL AND counterparty != ''