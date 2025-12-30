"""
Rebuild Vendor Normalization Map - ENHANCED VERSION

Improvements:
- Cleans newlines, extra whitespace from vendor names
- Manual overrides for known mappings
- Partial name matching (e.g., "Anytime" → "Anytime Waste Systems")
- Lower threshold for short names
- Token-based matching for reordered words
"""

import pandas as pd
from rapidfuzz import fuzz, process
import re
import os

# =============================================================================
# CONFIGURATION
# =============================================================================
DATA_PATH = r"C:\Users\ShaneStClair\OneDrive - Wasteology Group\Flywheel\Incoming Dashboard Build\Active\data"

# Manual overrides - add known mappings here
# Format: 'messy_name': 'clean_name'
MANUAL_OVERRIDES = {
    # Partial names
    'Anytime': 'Anytime Waste Systems',
    'ANYTIME': 'Anytime Waste Systems',
    'casella': 'Casella Waste',
    'Casella': 'Casella Waste',
    'CASELLA': 'Casella Waste',
    'ROBINSON': 'Robinson Waste',
    'Robinson': 'Robinson Waste',
    'Friedman': 'Friedman Industries Inc.',
    'FRIEDMAN': 'Friedman Industries Inc.',
    'Fruednab': 'Friedman Industries Inc.',
    'PRIORITY': 'Priority Waste',
    'PPRIORITY': 'Priority Waste',
    'Priority': 'Priority Waste',
    'Walters': 'Walters Services',
    'WALTERS': 'Walters Services',
    'Best Way': 'Bestway Disposal',
    'BEST WAY': 'Bestway Disposal',
    'ROCKY RIDGE': 'Rocky Ridge Sanitation',
    'HDS HOMEWOOD': 'Homewood Disposal',
    
    # Newline fixes (will also be handled automatically)
    'Flood Brothers': 'Flood Brothers Disposal',
    'FLOOD BROTHERS': 'Flood Brothers Disposal',
    
    # Common variations
    '1-800-Got Junk Commercial Services (USA) LLC': '1-800-GOT-JUNK National',
    'WASTE PRO Caring For Our Communities': 'Waste Pro',
    'Fusion Waste and Recycling': 'Fusion Waste & Recycling',
    'J & J SERVICES, INC.': 'J & J Services Inc.',
    'J & J Services, Inc.': 'J & J Services Inc.',
    'ash Franchise Partners, LLC': 'Trash Franchise Partners LLC',
}

# =============================================================================
# LOAD DATA
# =============================================================================
print("Loading data...")

# Clean vendor names (source of truth)
clean_vendors = pd.read_csv(os.path.join(DATA_PATH, 'clean_vendor_names.csv'))
clean_vendor_list = clean_vendors['vendor_name'].dropna().str.strip().unique().tolist()
print(f"  Clean vendors: {len(clean_vendor_list):,}")

# Location → Vendor lookup
location_vendor = pd.read_csv(os.path.join(DATA_PATH, 'location_vendor_lookup.csv'))
location_vendor['location_name'] = location_vendor['location_name'].str.strip()
location_vendor['vendor_name'] = location_vendor['vendor_name'].str.strip()
print(f"  Location-vendor pairs: {len(location_vendor):,}")

# Build location → vendors dict
location_to_vendors = location_vendor.groupby('location_name')['vendor_name'].apply(set).to_dict()
print(f"  Unique locations: {len(location_to_vendors):,}")

# Invoice counterparty → vendor (what we need to match)
invoice_cp_vendor = pd.read_csv(os.path.join(DATA_PATH, 'invoice_counterparty_vendor.csv'))
# Clean up newlines and whitespace in vendor names
invoice_cp_vendor['vendor_name'] = invoice_cp_vendor['vendor_name'].str.replace(r'\n', ' ', regex=True)
invoice_cp_vendor['vendor_name'] = invoice_cp_vendor['vendor_name'].str.replace(r'\s+', ' ', regex=True)
invoice_cp_vendor['vendor_name'] = invoice_cp_vendor['vendor_name'].str.strip()
invoice_cp_vendor['counterparty'] = invoice_cp_vendor['counterparty'].str.strip()
invoice_cp_vendor = invoice_cp_vendor.dropna()
print(f"  Invoice counterparty-vendor pairs: {len(invoice_cp_vendor):,}")

# Get unique messy vendor names
messy_vendors = invoice_cp_vendor['vendor_name'].unique().tolist()
print(f"  Unique messy vendor names: {len(messy_vendors):,}")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def clean_name(name):
    """Clean vendor name - remove newlines, extra spaces, normalize"""
    if pd.isna(name):
        return ""
    name = str(name)
    name = re.sub(r'\n', ' ', name)  # Replace newlines with space
    name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
    return name.strip()

def normalize_name(name):
    """Normalize vendor name for comparison"""
    if pd.isna(name):
        return ""
    name = clean_name(name).upper()
    name = re.sub(r'[^A-Z0-9\s]', '', name)  # Remove punctuation
    name = re.sub(r'\s+', ' ', name).strip()  # Normalize whitespace
    # Remove common suffixes for better matching
    name = re.sub(r'\b(INC|LLC|CORP|CO|COMPANY|SERVICES|SERVICE|DISPOSAL|WASTE|SANITATION)\b', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def find_best_match(messy_name, candidate_vendors, threshold=70):
    """Find best match from candidate vendors"""
    if not candidate_vendors:
        return None, 0
    
    messy_clean = clean_name(messy_name)
    messy_norm = normalize_name(messy_name)
    
    # Try exact match first (case-insensitive)
    for v in candidate_vendors:
        if clean_name(v).upper() == messy_clean.upper():
            return v, 100
    
    # Try normalized exact match
    for v in candidate_vendors:
        if normalize_name(v) == messy_norm:
            return v, 100
    
    candidates_norm = {normalize_name(v): v for v in candidate_vendors if normalize_name(v)}
    
    if not candidates_norm:
        return None, 0
    
    # Try token sort ratio (handles word reordering)
    result = process.extractOne(
        messy_norm, 
        list(candidates_norm.keys()),
        scorer=fuzz.token_sort_ratio
    )
    
    if result and result[1] >= threshold:
        return candidates_norm[result[0]], result[1]
    
    # Try partial ratio for substring matching (e.g., "Anytime" in "Anytime Waste Systems")
    result_partial = process.extractOne(
        messy_norm,
        list(candidates_norm.keys()),
        scorer=fuzz.partial_ratio
    )
    
    # Higher threshold for partial matching to avoid false positives
    if result_partial and result_partial[1] >= 90:
        return candidates_norm[result_partial[0]], result_partial[1]
    
    return None, 0

def find_location_match(counterparty, location_names, threshold=80):
    """Find matching location for a counterparty"""
    if pd.isna(counterparty):
        return None
    
    cp_norm = normalize_name(counterparty)
    
    # Try exact match first
    for loc in location_names:
        if normalize_name(loc) == cp_norm:
            return loc
    
    result = process.extractOne(
        cp_norm,
        [normalize_name(loc) for loc in location_names],
        scorer=fuzz.token_sort_ratio
    )
    
    if result and result[1] >= threshold:
        # Find original location name
        for loc in location_names:
            if normalize_name(loc) == result[0]:
                return loc
    return None

def try_partial_name_match(messy_name, clean_vendor_list, min_length=4):
    """Try matching short/partial names against full vendor names"""
    messy_clean = clean_name(messy_name)
    messy_upper = messy_clean.upper()
    
    if len(messy_clean) < min_length:
        return None, 0
    
    # Look for vendors that START with the messy name
    matches = []
    for v in clean_vendor_list:
        v_upper = v.upper()
        if v_upper.startswith(messy_upper):
            matches.append((v, 95))
        elif messy_upper in v_upper.split()[0] if v_upper.split() else False:
            # First word contains the messy name
            matches.append((v, 90))
    
    if matches:
        # Return the shortest match (most specific)
        matches.sort(key=lambda x: (100-x[1], len(x[0])))
        return matches[0]
    
    return None, 0

# =============================================================================
# BUILD NORMALIZATION MAP
# =============================================================================
print("\nBuilding normalization map...")

# Get all unique counterparties
counterparties = invoice_cp_vendor['counterparty'].unique()
location_names = list(location_to_vendors.keys())

# Cache counterparty → location matches
print("  Matching counterparties to locations...")
cp_to_location = {}
for i, cp in enumerate(counterparties):
    if i % 1000 == 0:
        print(f"    {i:,}/{len(counterparties):,}")
    cp_to_location[cp] = find_location_match(cp, location_names)

matched_cps = sum(1 for v in cp_to_location.values() if v is not None)
print(f"  Matched {matched_cps:,}/{len(counterparties):,} counterparties to locations")

# Now match vendor names
print("\nMatching vendor names...")
normalization_map = {}
match_details = []

for i, (_, row) in enumerate(invoice_cp_vendor.iterrows()):
    if i % 5000 == 0:
        print(f"  {i:,}/{len(invoice_cp_vendor):,}")
    
    messy_vendor = row['vendor_name']
    counterparty = row['counterparty']
    
    # Clean the messy vendor name
    messy_vendor_clean = clean_name(messy_vendor)
    
    # Skip if already matched
    if messy_vendor_clean in normalization_map:
        continue
    
    match_method = None
    matched_vendor = None
    score = 0
    
    # 1. Check manual overrides first
    if messy_vendor_clean in MANUAL_OVERRIDES:
        matched_vendor = MANUAL_OVERRIDES[messy_vendor_clean]
        match_method = 'manual'
        score = 100
    
    # 2. Try constrained match (vendors at this location)
    if not matched_vendor:
        location = cp_to_location.get(counterparty)
        if location and location in location_to_vendors:
            candidate_vendors = location_to_vendors[location]
            matched_vendor, score = find_best_match(messy_vendor_clean, candidate_vendors, threshold=65)
            if matched_vendor:
                match_method = 'constrained'
    
    # 3. Try global match against all clean vendors
    if not matched_vendor:
        matched_vendor, score = find_best_match(messy_vendor_clean, clean_vendor_list, threshold=80)
        if matched_vendor:
            match_method = 'global'
    
    # 4. Try partial name match (for short names like "Anytime")
    if not matched_vendor:
        matched_vendor, score = try_partial_name_match(messy_vendor_clean, clean_vendor_list)
        if matched_vendor:
            match_method = 'partial'
    
    if matched_vendor:
        normalization_map[messy_vendor_clean] = matched_vendor
        # Also map the original (uncleaned) name if different
        if messy_vendor != messy_vendor_clean:
            normalization_map[messy_vendor] = matched_vendor
        match_details.append({
            'messy_vendor': messy_vendor_clean,
            'matched_vendor': matched_vendor,
            'score': score,
            'method': match_method,
            'counterparty': counterparty,
            'location': cp_to_location.get(counterparty)
        })

# =============================================================================
# OUTPUT RESULTS
# =============================================================================
print("\n" + "="*60)
print("RESULTS")
print("="*60)

print(f"\nTotal messy vendors: {len(messy_vendors):,}")
print(f"Matched vendors: {len(normalization_map):,}")
print(f"Match rate: {len(normalization_map)/len(messy_vendors)*100:.1f}%")

# Count by method
details_df = pd.DataFrame(match_details)
if len(details_df) > 0:
    print(f"\nBy match method:")
    print(details_df['method'].value_counts())

# Save normalization map
output_df = pd.DataFrame([
    {'vendor_name': k, 'normalized_vendor': v} 
    for k, v in normalization_map.items()
])
output_df = output_df.sort_values('normalized_vendor')
output_df.to_csv(os.path.join(DATA_PATH, 'vendor_name_normalization_map_NEW.csv'), index=False)
print(f"\nSaved: vendor_name_normalization_map_NEW.csv ({len(output_df):,} mappings)")

# Save detailed results for review
details_df.to_csv(os.path.join(DATA_PATH, 'normalization_match_details.csv'), index=False)
print(f"Saved: normalization_match_details.csv (for review)")

# Show unmatched vendors
unmatched = [v for v in messy_vendors if clean_name(v) not in normalization_map]
if unmatched:
    print(f"\nTop 30 unmatched vendors:")
    # Count occurrences
    vendor_counts = invoice_cp_vendor['vendor_name'].value_counts()
    unmatched_counts = vendor_counts[vendor_counts.index.isin(unmatched)].head(30)
    for vendor, count in unmatched_counts.items():
        print(f"  {count:4d}  {vendor[:60]}")
    
    # Save unmatched for manual review
    unmatched_df = pd.DataFrame({'vendor_name': unmatched_counts.index, 'count': unmatched_counts.values})
    unmatched_df.to_csv(os.path.join(DATA_PATH, 'unmatched_vendors_to_review.csv'), index=False)
    print(f"\nSaved: unmatched_vendors_to_review.csv ({len(unmatched_counts)} vendors)")

print("\n" + "="*60)
print("DONE!")
print("="*60)
print("\nNext steps:")
print("1. Review vendor_name_normalization_map_NEW.csv")
print("2. Check unmatched_vendors_to_review.csv for vendors to add manually")
print("3. Add manual mappings to MANUAL_OVERRIDES in this script and re-run")
print("4. When satisfied, rename _NEW.csv to vendor_name_normalization_map.csv")
