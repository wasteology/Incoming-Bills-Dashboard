import pandas as pd
from rapidfuzz import fuzz, process
import re

# ============================================================
# CONFIGURATION
# ============================================================
DATA_PATH = r"C:\Users\ShaneStClair\OneDrive - Wasteology Group\Flywheel\Incoming Dashboard Build\Active\data"
OUTPUT_PATH = r"C:\Users\ShaneStClair\OneDrive - Wasteology Group\Flywheel\Incoming Dashboard Build\Active\github_output"

# ============================================================
# STEP 1: LOAD DATA
# ============================================================
print("="*60)
print("STEP 1: LOADING DATA")
print("="*60)

invoices = pd.read_csv(f"{DATA_PATH}\\raw_invoices.csv")
services = pd.read_excel(f"{DATA_PATH}\\location_vendor_lookup.xlsx")
vendors = pd.read_excel(f"{DATA_PATH}\\vendor_names.xlsx")

print(f"  Invoices: {len(invoices):,}")
print(f"  Services: {len(services):,}")
print(f"  Vendors: {len(vendors):,}")

# Build reference data
clean_vendors = vendors['vendor_name'].dropna().unique().tolist()
clean_vendors_lower = {v.lower(): v for v in clean_vendors}

services = services[services['location_name'].apply(lambda x: isinstance(x, str))]
location_vendors = services.groupby('location_name')['vendor_name'].apply(set).to_dict()
all_locations = list(location_vendors.keys())

print(f"  Unique locations: {len(all_locations):,}")

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def clean_vendor_name(vn):
    """Clean vendor name string"""
    if pd.isna(vn):
        return ''
    vn = str(vn)
    vn = vn.replace('\\n', ' ').replace('\\r', ' ')
    vn = vn.replace('\n', ' ').replace('\r', ' ')
    vn = re.sub(r'\s+', ' ', vn).strip()
    return vn

def normalize_for_match(s):
    """Normalize for matching (remove punctuation, space numbers)"""
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'(\d+)', r' \1 ', s)
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s

# ============================================================
# STEP 2: MATCH VENDORS
# ============================================================
print("\n" + "="*60)
print("STEP 2: MATCHING VENDORS")
print("="*60)

location_cache = {}
vendor_cache = {}

def match_vendor(row):
    """
    Two-stage matching:
    1. Location-based: counterparty -> location -> candidates -> fuzzy match
    2. Direct: strict fuzzy match against clean vendor list
    """
    cp = row['counterparty']
    vn = clean_vendor_name(row['vendor_name'])
    
    # STAGE 1: Location-based matching (high confidence)
    if pd.notna(cp) and cp != '':
        candidates = location_vendors.get(cp)
        
        # Fuzzy location match if no exact
        if not candidates:
            if cp in location_cache:
                loc = location_cache[cp]
            else:
                match = process.extractOne(str(cp), all_locations, scorer=fuzz.token_sort_ratio)
                loc = match[0] if match and match[1] >= 75 else None
                location_cache[cp] = loc
            if loc:
                candidates = location_vendors.get(loc)
        
        if candidates:
            # Single vendor at location - use it
            if len(candidates) == 1:
                return list(candidates)[0]
            
            # Multiple vendors - fuzzy match against candidates only
            if vn:
                match = process.extractOne(vn, list(candidates), scorer=fuzz.token_sort_ratio)
                if match and match[1] >= 35:
                    return match[0]
                # Try partial ratio
                match2 = process.extractOne(vn, list(candidates), scorer=fuzz.partial_ratio)
                if match2 and match2[1] >= 50:
                    return match2[0]
    
    # STAGE 2: Direct vendor match (strict thresholds only)
    if vn:
        if vn in vendor_cache:
            if vendor_cache[vn]:
                return vendor_cache[vn]
        else:
            # Exact match
            if vn.lower() in clean_vendors_lower:
                vendor_cache[vn] = clean_vendors_lower[vn.lower()]
                return vendor_cache[vn]
            
            # Normalized exact match (BECKER360 -> Becker 360)
            vn_norm = normalize_for_match(vn)
            for clean in clean_vendors:
                if normalize_for_match(clean) == vn_norm:
                    vendor_cache[vn] = clean
                    return clean
            
            # Strict fuzzy (80%+)
            match = process.extractOne(vn, clean_vendors, scorer=fuzz.token_sort_ratio)
            if match and match[1] >= 80:
                vendor_cache[vn] = match[0]
                return match[0]
            
            vendor_cache[vn] = None
    
    return 'Unmatched'

print("  Matching (this may take a minute)...")
invoices['normalized_vendor'] = invoices.apply(match_vendor, axis=1)

# Stats
matched = (invoices['normalized_vendor'] != 'Unmatched').sum()
print(f"\n  Matched: {matched:,} ({matched/len(invoices)*100:.1f}%)")
print(f"  Unmatched: {len(invoices) - matched:,}")

# Export unmatched
unmatched = invoices[invoices['normalized_vendor'] == 'Unmatched'][['invoice_md5', 'vendor_name', 'counterparty', 'sp_created_date']]
unmatched.to_csv(f"{DATA_PATH}\\unmatched_invoices.csv", index=False)
print(f"  Saved unmatched_invoices.csv ({len(unmatched)} rows)")

# ============================================================
# STEP 3: PARSE DATES
# ============================================================
print("\n" + "="*60)
print("STEP 3: PARSING DATES")
print("="*60)

invoices['sp_created_date'] = pd.to_datetime(invoices['sp_created_date'], errors='coerce')

bad_dates = invoices['sp_created_date'].isna().sum()
if bad_dates > 0:
    print(f"  Warning: {bad_dates} rows with invalid dates - dropping")
    invoices = invoices.dropna(subset=['sp_created_date'])

# Filter to 2025
invoices = invoices[invoices['sp_created_date'] >= '2025-01-01']
print(f"  Invoices in 2025: {len(invoices):,}")

# Add date columns
invoices['month'] = invoices['sp_created_date'].dt.strftime('%b')
invoices['day'] = invoices['sp_created_date'].dt.strftime('%b %d')
invoices['isWeekend'] = invoices['sp_created_date'].dt.dayofweek.isin([5, 6])

# ============================================================
# STEP 4: GENERATE DAILY MTD
# ============================================================
print("\n" + "="*60)
print("STEP 4: GENERATING DAILY MTD")
print("="*60)

daily = invoices.groupby(['month', 'day', 'isWeekend']).size().reset_index(name='count')
daily['isWeekend'] = daily['isWeekend'].map({True: 'true', False: 'false'})

month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
daily['month_num'] = daily['month'].map({m: i for i, m in enumerate(month_order)})
daily = daily.sort_values(['month_num', 'day']).drop(columns=['month_num'])

daily.to_csv(f"{OUTPUT_PATH}\\daily_mtd.csv", index=False)
print(f"  Saved daily_mtd.csv ({len(daily)} rows)")

# ============================================================
# STEP 5: GENERATE MONTHLY TREND
# ============================================================
print("\n" + "="*60)
print("STEP 5: GENERATING MONTHLY TREND")
print("="*60)

monthly_vendor = invoices.groupby(['normalized_vendor', 'month']).size().reset_index(name='count')
monthly_vendor.columns = ['vendor', 'month', 'count']

monthly_all = invoices.groupby('month').size().reset_index(name='count')
monthly_all['vendor'] = 'All Vendors'
monthly_all = monthly_all[['vendor', 'month', 'count']]

monthly = pd.concat([monthly_all, monthly_vendor], ignore_index=True)
monthly['month_num'] = monthly['month'].map({m: i for i, m in enumerate(month_order)})
monthly = monthly.sort_values(['vendor', 'month_num']).drop(columns=['month_num'])

monthly.to_csv(f"{OUTPUT_PATH}\\monthly_trend.csv", index=False)
print(f"  Saved monthly_trend.csv ({len(monthly)} rows)")

# ============================================================
# STEP 6: GENERATE ALERTS
# ============================================================
print("\n" + "="*60)
print("STEP 6: GENERATING ALERTS")
print("="*60)

prior_month = 'Oct'
current_month = 'Nov'

prior = invoices[invoices['month'] == prior_month].groupby('normalized_vendor').size()
current = invoices[invoices['month'] == current_month].groupby('normalized_vendor').size()

alerts = pd.DataFrame({'vendor': prior.index, 'priorCount': prior.values})
alerts = alerts.merge(
    pd.DataFrame({'vendor': current.index, 'currentCount': current.values}),
    on='vendor', how='outer'
).fillna(0)

alerts['priorCount'] = alerts['priorCount'].astype(int)
alerts['currentCount'] = alerts['currentCount'].astype(int)
alerts['pct'] = (alerts['currentCount'] / alerts['priorCount'].replace(0, 1) * 100).round(1)

alerts = alerts[alerts['priorCount'] >= 10]
alerts = alerts.sort_values('priorCount', ascending=False)

alerts.to_csv(f"{OUTPUT_PATH}\\alerts.csv", index=False)
print(f"  Saved alerts.csv ({len(alerts)} rows)")

flagged = alerts[(alerts['pct'] < 75) | (alerts['pct'] > 125)]
print(f"  Vendors flagged: {len(flagged)}")

# ============================================================
# DONE
# ============================================================
print("\n" + "="*60)
print("DONE!")
print("="*60)
print(f"\nFiles saved to: {OUTPUT_PATH}")

input("\nPress Enter to close...")
