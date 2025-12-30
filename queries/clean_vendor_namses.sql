SELECT DISTINCT vendor_name
FROM wasteology.new_ct.vw_flat_services
WHERE vendor_name IS NOT NULL AND vendor_name != ''