SELECT DISTINCT location_name, vendor_name
FROM wasteology.new_ct.vw_flat_services
WHERE location_name IS NOT NULL AND location_name != ''
  AND vendor_name IS NOT NULL AND vendor_name != ''