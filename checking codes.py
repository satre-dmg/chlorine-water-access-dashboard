import pandas as pd

# Load the waterpoints sheet from your analysis workbook
df = pd.read_excel("nigeria_water_access_analysis.xlsx", sheet_name="waterpoints")

print("\n=== WATER TECHNOLOGY VALUES ===\n")
print(df["water_tech"].fillna("MISSING").value_counts(dropna=False))

print("\n=== STATUS VALUES ===\n")
print(df["status"].fillna("MISSING").value_counts(dropna=False))

print("\n=== FIRST 20 UNIQUE WATER TECHNOLOGY VALUES ===\n")
for val in sorted(df["water_tech"].fillna("MISSING").astype(str).unique())[:20]:
    print(val)

print("\n=== FIRST 30 UNIQUE STATUS VALUES ===\n")
for val in sorted(df["status"].fillna("MISSING").astype(str).unique())[:30]:
    print(val)