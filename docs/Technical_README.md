# Invoice Volume Dashboard - Technical Documentation

## Overview

Dashboard displaying invoice volume metrics from `wasteology.dbo.sharepoint_gapi`. Uses fuzzy matching to normalize vendor names against canonical vendor list.

**Tech Stack:**
- Data Source: SQL Server (Azure)
- Pipeline: Python (pandas, rapidfuzz)
- Frontend: Static HTML + Chart.js
- Hosting: GitHub Pages

**Match Rate:** ~98.8%

---

## File Structure

### OneDrive
```
Incoming Dashboard Build/
└── Active/
    ├── data/
    │   ├── raw_invoices.csv              ← Daily DataGrip export
    │   ├── vendor_names.xlsx             ← Clean vendor list (refresh monthly)
    │   ├── location_vendor_lookup.xlsx   ← Location → vendor mapping (refresh monthly)
    │   └── unmatched_invoices.csv        ← Generated (for review)
    │
    ├── scripts/
    │   └── update_dashboard.py           ← Daily pipeline
    │
    └── github_output/                    ← Generated files for GitHub
        ├── daily_mtd.csv
        ├── monthly_trend.csv
        └── alerts.csv
```

### GitHub Repository
```
incoming-bills-dashboard/
├── index.html
├── logo.png
├── daily_mtd.csv
├── monthly_trend.csv
└── alerts.csv
```

---

## Daily Update Process

### Step 1: Export Invoices from DataGrip

```sql
SELECT 
    invoice_md5,
    vendor_name,
    counterparty,
    sp_created_date,
    status
FROM wasteology.dbo.sharepoint_gapi
WHERE invoice_md5 IS NOT NULL
  AND invoice_md5 != ''
  AND (status IS NULL OR status NOT IN ('obsolete', 'duplicate'))
```

**Save as:** `data/raw_invoices.csv` (with headers)

### Step 2: Run Pipeline

```cmd
cd "...\Active\scripts"
python update_dashboard.py
```

**Requires:** `pip install pandas rapidfuzz openpyxl`

### Step 3: Push to GitHub

Copy from `github_output/` to GitHub repo:
- `daily_mtd.csv`
- `monthly_trend.csv`
- `alerts.csv`

Commit and push.

**Dashboard URL:** https://wasteology.github.io/incoming-bills-dashboard/

---

## Reference Data (Monthly Refresh)

### vendor_names.xlsx

Clean vendor list from services table:

```sql
SELECT DISTINCT vendor_name
FROM wasteology.new_ct.vw_flat_services
WHERE vendor_name IS NOT NULL
```

### location_vendor_lookup.xlsx

Location → vendor mapping:

```sql
SELECT DISTINCT location_name, vendor_name
FROM wasteology.new_ct.vw_flat_services
WHERE location_name IS NOT NULL
  AND vendor_name IS NOT NULL
```

---

## Matching Algorithm

### Stage 1: Direct Vendor Match (~95%)

Matches invoice `vendor_name` against `vendor_names.xlsx`:

1. **Case-insensitive exact:** `REPUBLIC` → `Republic`
2. **Normalized:** `BECKER360` → `Becker 360`
3. **Fuzzy (65%):** `Republic Svcs` → `Republic Services`
4. **Partial (80%):** `1-800-Got Junk Commercial Services` → `1-800-Got-Junk`
5. **Substring:** `GROOT, INC.` → `Waste Connections - Groot Industries`

### Stage 2: Location-Based Match (~3%)

For unmatched invoices, uses `counterparty` → `location_name` → `vendor_name`:

1. Exact location match
2. Fuzzy location match (75% threshold)
3. If single vendor at location → use it
4. If multiple vendors → fuzzy match vendor name against candidates

### Unmatched (~1.2%)

Exported to `data/unmatched_invoices.csv` for manual review.

---

## Output File Schemas

### daily_mtd.csv
| Column | Type | Description |
|--------|------|-------------|
| month | string | Month abbreviation (Jan, Feb, etc.) |
| day | string | Day label (e.g., "Dec 18") |
| count | int | Invoice count |
| isWeekend | bool | true/false |

### monthly_trend.csv
| Column | Type | Description |
|--------|------|-------------|
| vendor | string | Normalized vendor name or "All Vendors" |
| month | string | Month abbreviation |
| count | int | Invoice count |

### alerts.csv
| Column | Type | Description |
|--------|------|-------------|
| vendor | string | Normalized vendor name |
| priorCount | int | Prior month count |
| currentCount | int | Current month count |
| pct | float | Current as % of prior |

---

## Dashboard Features

### KPI Cards
| Card | Behavior |
|------|----------|
| Yesterday | Most recent day (fixed, doesn't change with filter) |
| MTD | Updates with month filter |
| YTD | Sum of all complete months |
| Alerts | Count of flagged vendors |

### Filters
- **Month dropdown:** Filters daily chart
- **Vendor dropdown:** Top 20 vendors by volume

### Alert Thresholds
- Triggers when: `priorCount >= 10 AND (pct < 75 OR pct > 125)`
- Excludes "Unmatched" vendor

---

## Troubleshooting

### Low Match Rate
- Check `unmatched_invoices.csv` for patterns
- Add missing vendors to `vendor_names.xlsx`
- Add missing locations to `location_vendor_lookup.xlsx`

### Missing Module Error
```cmd
pip install pandas rapidfuzz openpyxl
```

### Dashboard Not Updating
- Verify CSVs pushed to GitHub
- Check GitHub Pages build status
- Hard refresh browser (Ctrl+Shift+R)

---

## Dependencies

**Python packages:**
- pandas
- rapidfuzz
- openpyxl

**Install:**
```cmd
pip install pandas rapidfuzz openpyxl
```
