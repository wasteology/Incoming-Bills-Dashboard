import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================
DATA_PATH = r"C:\Users\ShaneStClair\OneDrive - Wasteology Group\Flywheel\Incoming Dashboard Build\Active\data"

# ============================================================
# LOAD & ANALYZE
# ============================================================
print("Loading invoices...")
invoices = pd.read_csv(f"{DATA_PATH}\\raw_invoices.csv")
print(f"  Loaded {len(invoices):,} invoices")

unmatched = invoices[invoices['normalized_vendor'].isna()]

print(f"\n{'='*60}")
print("RESULTS")
print(f"{'='*60}")
print(f"Total invoices:   {len(invoices):,}")
print(f"Matched:          {len(invoices) - len(unmatched):,}")
print(f"Unmatched:        {len(unmatched):,}")
print(f"Match rate:       {(1 - len(unmatched)/len(invoices))*100:.1f}%")

if len(unmatched) > 0:
    print(f"\n{'='*60}")
    print("TOP 20 UNMATCHED COUNTERPARTIES")
    print(f"{'='*60}")
    top = unmatched.groupby('counterparty').size().sort_values(ascending=False).head(20)
    for cp, count in top.items():
        print(f"  {count:>6,}  {cp}")

input("\nPress Enter to close...")
