"""
Vendor Name Normalization - DETERMINISTIC VERSION

Rules:
1. EXACT MATCH ONLY (after normalization)
2. Flag invalid names - don't guess
3. Output files for manual review

No fuzzy matching. No guessing.
"""

import pandas as pd
import re
import os

# =============================================================================
# CONFIGURATION
# =============================================================================
DATA_PATH = r"C:\Users\ShaneStClair\OneDrive - Wasteology Group\Flywheel\Incoming Dashboard Build\Active\data"

MIN_NAME_LENGTH = 5  # Minimum characters
MIN_ALPHA_CHARS = 3  # Minimum alphabetic characters

# =============================================================================
# MANUAL OVERRIDES - Add known mappings here
# =============================================================================
MANUAL_OVERRIDES = {
    # Format: 'exact messy name': 'clean vendor name'
    
    # Waste Pro variations
    'WASTE PRO': 'Waste Pro',
    'Waste Pro': 'Waste Pro',
    'WastePro': 'Waste Pro',
    'WASTE PRO USA': 'Waste Pro',
    'WASTE PRO Caring For Our Communities': 'Waste Pro',
    
    # Republic Services
    'REPUBLIC SERVICES': 'Republic Services',
    'Republic Services': 'Republic Services',
    
    # Waste Management  
    'WASTE MANAGEMENT': 'Waste Management',
    'Waste Management': 'Waste Management',
    
    # Casella
    'CASELLA': 'Casella Waste',
    'Casella': 'Casella Waste',
    'casella': 'Casella Waste',
    'CASELLA WASTE': 'Casella Waste',
    'CASELLA WASTE SYSTEMS': 'Casella Waste',
    
    # GFL
    'GFL': 'GFL Environmental',
    'GFL Environmental': 'GFL Environmental',
    'GFL ENVIRONMENTAL': 'GFL Environmental',
    
    # Rumpke
    'RUMPKE': 'Rumpke',
    'Rumpke': 'Rumpke',
    
    # Flood Brothers (newline issue)
    'Flood Brothers': 'Flood Brothers Disposal',
    'FLOOD BROTHERS': 'Flood Brothers Disposal',
    
    # Meridian (newline issue)
    'MERIDIAN WASTE': 'Meridian Waste',
    'Meridian Waste': 'Meridian Waste',
    
    # Delta Waste (newline issue)
    'DELTA WASTE SOLUTIONS': 'Delta Waste Solutions',
    
    # 1-800-GOT-JUNK variations
    '1-800-GOT-JUNK': '1-800-GOT-JUNK National',
    '1-800-Got-Junk': '1-800-GOT-JUNK National',
    '1-800-Got Junk': '1-800-GOT-JUNK National',
    '1-800 Got Junk': '1-800-GOT-JUNK National',
    '1-800-GOT-JUNK?': '1-800-GOT-JUNK National',
    '1-800-Got Junk Commercial Services (USA) LLC': '1-800-GOT-JUNK National',
}

# =============================================================================
# LOAD DATA
# =============================================================================
print("="*60)
print("DETERMINISTIC VENDOR NORMALIZATION")
print("="*60)
print("\nLoading data...")

clean_vendors = pd.read_csv(os.path.join(DATA_PATH, 'clean_vendor_names.csv'))
clean_vendor_list = clean_vendors['vendor_name'].dropna().str.strip().unique().tolist()
print(f"  Clean vendors: {len(clean_vendor_list):,}")

location_vendor = pd.read_csv(os.path.join(DATA_PATH, 'location_vendor_lookup.csv'))
location_vendor['location_name'] = location_vendor['location_name'].str.strip()
location_vendor['vendor_name'] = location_vendor['vendor_name'].str.strip()
print(f"  Location-vendor pairs: {len(location_vendor):,}")

# Build location → vendors dict
location_to_vendors = location_vendor.groupby('location_name')['vendor_name'].apply(set).to_dict()
print(f"  Unique locations: {len(location_to_vendors):,}")

invoice_cp_vendor = pd.read_csv(os.path.join(DATA_PATH, 'invoice_counterparty_vendor.csv'))
# Clean newlines
invoice_cp_vendor['vendor_name_raw'] = invoice_cp_vendor['vendor_name'].copy()
invoice_cp_vendor['vendor_name'] = invoice_cp_vendor['vendor_name'].str.replace(r'\n', ' ', regex=True)
invoice_cp_vendor['vendor_name'] = invoice_cp_vendor['vendor_name'].str.replace(r'\s+', ' ', regex=True)
invoice_cp_vendor['vendor_name'] = invoice_cp_vendor['vendor_name'].str.strip()
invoice_cp_vendor['counterparty'] = invoice_cp_vendor['counterparty'].str.strip()
invoice_cp_vendor = invoice_cp_vendor.dropna(subset=['vendor_name', 'counterparty'])
print(f"  Invoice counterparty-vendor pairs: {len(invoice_cp_vendor):,}")

messy_vendors = invoice_cp_vendor['vendor_name'].unique().tolist()
print(f"  Unique messy vendor names: {len(messy_vendors):,}")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_for_lookup(name):
    """Normalize name for exact matching lookup"""
    if pd.isna(name) or not name:
        return ""
    name = str(name).strip()
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name)
    # Uppercase for comparison
    return name.upper()

def normalize_aggressive(name):
    """More aggressive normalization - remove punctuation, suffixes"""
    if pd.isna(name) or not name:
        return ""
    name = str(name).upper()
    # Remove common suffixes
    name = re.sub(r'\b(INC\.?|LLC\.?|CORP\.?|CO\.?|L\.?L\.?C\.?)\b', '', name)
    # Remove punctuation
    name = re.sub(r'[^A-Z0-9\s]', ' ', name)
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def is_invalid_name(name):
    """
    Check if name is invalid/garbage and should be flagged.
    Returns (is_invalid, reason)
    """
    if not name:
        return True, "empty"
    
    # Too short
    if len(name) < MIN_NAME_LENGTH:
        return True, f"too_short ({len(name)} chars)"
    
    # Count alphabetic characters
    alpha_count = sum(1 for c in name if c.isalpha())
    if alpha_count < MIN_ALPHA_CHARS:
        return True, f"too_few_letters ({alpha_count})"
    
    # Starts with lowercase (truncated OCR)
    if name[0].islower():
        return True, "starts_lowercase (OCR truncation)"
    
    # Known garbage patterns
    garbage_patterns = [
        r'^(INC|LLC|CORP|CO|LTD)\.?$',  # Just suffix
        r'^\d+$',  # Just numbers
        r'^[^a-zA-Z]*$',  # No letters at all
    ]
    for pattern in garbage_patterns:
        if re.match(pattern, name, re.IGNORECASE):
            return True, "garbage_pattern"
    
    return False, None

# =============================================================================
# BUILD LOOKUP TABLES
# =============================================================================
print("\nBuilding lookup tables...")

# Create lookup dictionaries from clean vendor list
# Key: normalized name, Value: original clean name
clean_lookup_exact = {}  # Exact uppercase match
clean_lookup_aggressive = {}  # Aggressive normalization match

for v in clean_vendor_list:
    norm_exact = normalize_for_lookup(v)
    norm_agg = normalize_aggressive(v)
    
    if norm_exact and norm_exact not in clean_lookup_exact:
        clean_lookup_exact[norm_exact] = v
    if norm_agg and norm_agg not in clean_lookup_aggressive:
        clean_lookup_aggressive[norm_agg] = v

print(f"  Exact lookup entries: {len(clean_lookup_exact):,}")
print(f"  Aggressive lookup entries: {len(clean_lookup_aggressive):,}")

# Create location-constrained lookups
# Key: (location, normalized vendor name), Value: clean vendor name
location_vendor_lookup = {}
for loc, vendors in location_to_vendors.items():
    loc_norm = normalize_for_lookup(loc)
    for v in vendors:
        v_exact = normalize_for_lookup(v)
        v_agg = normalize_aggressive(v)
        if v_exact:
            location_vendor_lookup[(loc_norm, v_exact)] = v
        if v_agg:
            location_vendor_lookup[(loc_norm, v_agg)] = v

print(f"  Location-vendor lookup entries: {len(location_vendor_lookup):,}")

# Counterparty to location mapping (exact match on normalized)
cp_to_location = {}
for loc in location_to_vendors.keys():
    cp_to_location[normalize_for_lookup(loc)] = loc

# =============================================================================
# MATCHING PROCESS
# =============================================================================
print("\nMatching vendor names...")

normalization_map = {}
flagged_invalid = []
unmatched_valid = []
match_details = []

for messy_vendor in messy_vendors:
    # Check manual override first (exact match)
    if messy_vendor in MANUAL_OVERRIDES:
        normalization_map[messy_vendor] = MANUAL_OVERRIDES[messy_vendor]
        match_details.append({
            'messy_vendor': messy_vendor,
            'matched_vendor': MANUAL_OVERRIDES[messy_vendor],
            'method': 'manual_override'
        })
        continue
    
    # Check if name is invalid
    is_invalid, reason = is_invalid_name(messy_vendor)
    if is_invalid:
        flagged_invalid.append({
            'vendor_name': messy_vendor,
            'reason': reason
        })
        continue
    
    # Try exact match (uppercase)
    messy_norm = normalize_for_lookup(messy_vendor)
    if messy_norm in clean_lookup_exact:
        normalization_map[messy_vendor] = clean_lookup_exact[messy_norm]
        match_details.append({
            'messy_vendor': messy_vendor,
            'matched_vendor': clean_lookup_exact[messy_norm],
            'method': 'exact_match'
        })
        continue
    
    # Try aggressive normalization match
    messy_agg = normalize_aggressive(messy_vendor)
    if messy_agg in clean_lookup_aggressive:
        normalization_map[messy_vendor] = clean_lookup_aggressive[messy_agg]
        match_details.append({
            'messy_vendor': messy_vendor,
            'matched_vendor': clean_lookup_aggressive[messy_agg],
            'method': 'normalized_match'
        })
        continue
    
    # Try location-constrained matching
    # Find counterparties this vendor appears with
    vendor_rows = invoice_cp_vendor[invoice_cp_vendor['vendor_name'] == messy_vendor]
    matched_via_location = False
    
    for _, row in vendor_rows.iterrows():
        cp = row['counterparty']
        cp_norm = normalize_for_lookup(cp)
        
        # Check if counterparty matches a location
        if cp_norm in cp_to_location:
            location = cp_to_location[cp_norm]
            loc_norm = normalize_for_lookup(location)
            
            # Try exact match within location's vendors
            if (loc_norm, messy_norm) in location_vendor_lookup:
                normalization_map[messy_vendor] = location_vendor_lookup[(loc_norm, messy_norm)]
                match_details.append({
                    'messy_vendor': messy_vendor,
                    'matched_vendor': location_vendor_lookup[(loc_norm, messy_norm)],
                    'method': 'location_exact',
                    'location': location
                })
                matched_via_location = True
                break
            
            # Try aggressive match within location's vendors
            if (loc_norm, messy_agg) in location_vendor_lookup:
                normalization_map[messy_vendor] = location_vendor_lookup[(loc_norm, messy_agg)]
                match_details.append({
                    'messy_vendor': messy_vendor,
                    'matched_vendor': location_vendor_lookup[(loc_norm, messy_agg)],
                    'method': 'location_normalized',
                    'location': location
                })
                matched_via_location = True
                break
    
    if matched_via_location:
        continue
    
    # No match found - add to unmatched list
    unmatched_valid.append({
        'vendor_name': messy_vendor,
        'normalized': messy_norm,
        'aggressive_normalized': messy_agg
    })

# =============================================================================
# COUNT INVOICE OCCURRENCES
# =============================================================================
print("\nCounting invoice occurrences...")

vendor_counts = invoice_cp_vendor['vendor_name'].value_counts().to_dict()

for item in flagged_invalid:
    item['invoice_count'] = vendor_counts.get(item['vendor_name'], 0)

for item in unmatched_valid:
    item['invoice_count'] = vendor_counts.get(item['vendor_name'], 0)

# Sort by count
flagged_invalid.sort(key=lambda x: -x['invoice_count'])
unmatched_valid.sort(key=lambda x: -x['invoice_count'])

# =============================================================================
# OUTPUT RESULTS
# =============================================================================
print("\n" + "="*60)
print("RESULTS")
print("="*60)

total = len(messy_vendors)
matched = len(normalization_map)
invalid = len(flagged_invalid)
unmatched = len(unmatched_valid)

print(f"\nTotal messy vendors: {total:,}")
print(f"  Matched:           {matched:,} ({matched/total*100:.1f}%)")
print(f"  Flagged invalid:   {invalid:,} ({invalid/total*100:.1f}%)")
print(f"  Unmatched (valid): {unmatched:,} ({unmatched/total*100:.1f}%)")

# Match method breakdown
details_df = pd.DataFrame(match_details)
if len(details_df) > 0:
    print(f"\nMatch methods:")
    print(details_df['method'].value_counts().to_string())

# Save normalization map
output_df = pd.DataFrame([
    {'vendor_name': k, 'normalized_vendor': v} 
    for k, v in normalization_map.items()
])
output_df = output_df.sort_values('normalized_vendor')
output_path = os.path.join(DATA_PATH, 'vendor_name_normalization_map_NEW.csv')
output_df.to_csv(output_path, index=False)
print(f"\nSaved: vendor_name_normalization_map_NEW.csv ({len(output_df):,} mappings)")

# Save flagged invalid names
if flagged_invalid:
    invalid_df = pd.DataFrame(flagged_invalid)
    invalid_path = os.path.join(DATA_PATH, 'FLAGGED_invalid_vendor_names.csv')
    invalid_df.to_csv(invalid_path, index=False)
    print(f"Saved: FLAGGED_invalid_vendor_names.csv ({len(invalid_df):,} names)")
    print(f"\n  Top 10 invalid names by invoice count:")
    for item in flagged_invalid[:10]:
        print(f"    {item['invoice_count']:4d}  [{item['reason']}]  {item['vendor_name'][:50]}")

# Save unmatched valid names (need manual mapping)
if unmatched_valid:
    unmatched_df = pd.DataFrame(unmatched_valid)
    unmatched_path = os.path.join(DATA_PATH, 'UNMATCHED_need_manual_mapping.csv')
    unmatched_df.to_csv(unmatched_path, index=False)
    print(f"\nSaved: UNMATCHED_need_manual_mapping.csv ({len(unmatched_df):,} names)")
    print(f"\n  Top 20 unmatched names by invoice count:")
    for item in unmatched_valid[:20]:
        print(f"    {item['invoice_count']:4d}  {item['vendor_name'][:50]}")

# Save match details for review
try:
    details_path = os.path.join(DATA_PATH, 'match_details.csv')
    details_df.to_csv(details_path, index=False)
    print(f"\nSaved: match_details.csv")
except:
    pass

print("\n" + "="*60)
print("NEXT STEPS")
print("="*60)
print("""
1. Review UNMATCHED_need_manual_mapping.csv
   - Add mappings to MANUAL_OVERRIDES in this script
   - Re-run the script

2. Review FLAGGED_invalid_vendor_names.csv
   - These are OCR errors or garbage data
   - Add any recoverable ones to MANUAL_OVERRIDES

3. When satisfied, rename:
   vendor_name_normalization_map_NEW.csv → vendor_name_normalization_map.csv
""")
