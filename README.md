# Invoice Volume Dashboard
## Summary Overview 
## URL: https://shane-wasteology.github.io/incoming-bills-dashboard/
### Refer to technical_readme for dailiy pipeline instructions
---

### Purpose

The Invoice Volume Dashboard provides visibility into the daily inbound invoice count. The dashboard shows daily volume against average daily average, monthly volume by hauler, and surfaces the haulers who demonstrate a 25% drop in volume month over month. 

---

### Data Source

**Source Table:** `wasteology.dbo.sharepoint_gapi`

This table contains incoming invoices from haulers, parsed by Google Document AI. Each row represents one invoice received and processed through the SharePoint intake system.

**Data Exclusions:**
- Invoices marked as `obsolete` or `duplicate` status are excluded
- Only invoices from January 1, 2025 forward are displayed

---

### Vendor Matching

Hauler vendor names arrive in inconsistent formats from Document AI parsing. For example, "Republic Services" may appear as:
- `REPUBLIC SERVICES`
- `REPUBLIC\nSERVICES`
- `Republic Services Inc.`
- `REPUBLIC`

**Solution:**
A two-stage fuzzy matching algorithm normalizes messy vendor names to our canonical vendor list from `vw_flat_services`:

1. **Direct Match:** Invoice vendor name matched against clean vendor list using multiple techniques (exact match, fuzzy match, substring match)
2. **Location Match:** For remaining invoices, use counterparty → location → vendor lookup

**Current Match Rate:** ~98.8%

---

### Key Metrics

| Metric | Definition |
|--------|------------|
| **Yesterday** | Invoice count for the most recent complete day |
| **MTD** | Month-to-date invoice count (selected month) |
| **YTD** | Year-to-date invoice count (all complete months) |
| **Alerts** | Vendors with volume changes exceeding ±25% month-over-month |

---

### Alert Logic

Alerts flag vendors where invoice volume changed significantly between the two most recent complete months.

**Thresholds:**
- **Volume Drop:** Current month < 75% of prior month
- **Volume Spike:** Current month > 125% of prior month
- **Minimum Volume:** Vendor must have ≥10 invoices in prior month

**Potential Causes:**

| Alert Type | Possible Causes |
|------------|-----------------|
| **Volume Drop** | site closures, invoice scraping or routing issues.
| **Volume Spike** | Duplicate invoices, billing errors, new service locations, catch-up billing |

---

### Dashboard Views

**1. Daily MTD**
- Bar chart showing daily invoice counts for selected month
- Weekend days shown at reduced opacity
- Orange line = YTD daily average (benchmark)

**2. Monthly Trend**
- Line chart showing monthly totals
- Filterable by vendor (top 20 by volume)
- Current month excluded (incomplete data)

**3. Alerts**
- Table of vendors with unusual volume changes
- Exportable to CSV for follow-up
- Sorted by prior month volume (highest impact first)

---

### Update Frequency

The dashboard is updated daily via a manual process:
1. Fresh data exported from SQL Server
2. Pipeline script processes and generates output files
3. Files pushed to GitHub for dashboard refresh

**Note:** Dashboard shows data through the previous day (current day excluded).

---

### Limitations

1. **Unmatched Invoices:** ~1.2% of invoices cannot be matched to a known vendor
2. **Document AI Accuracy:** Source data quality depends on OCR parsing
3. **Manual Updates:** Dashboard requires daily manual refresh
4. **Historical Only:** This is not a real-time feed

---

### Business Value

- **Month-End Close:** Quickly identify missing or delayed invoices from key vendors
- **Anomaly Detection:** Early warning for billing issues or routing problems
- **Vendor Management:** Track invoice volume trends by hauler
- **Operational Visibility:** Understand daily/monthly processing patterns

---

### Contact

