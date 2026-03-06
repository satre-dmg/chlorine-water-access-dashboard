import streamlit as st
import pandas as pd

st.set_page_config(page_title="Nigeria Water Access Explorer", layout="wide")

st.title("Nigeria Water Access Explorer")
st.caption("Filter waterpoints by geography, population, and chlorine suitability.")

@st.cache_data
def load_data():
    return pd.read_excel("nigeria_water_access_analysis.xlsx", sheet_name="waterpoints")

df = load_data().copy()

# Normalize key fields to avoid filter errors
for col in ["state", "lga", "ward", "water_tech", "status", "management"]:
    if col in df.columns:
        df[col] = df[col].astype(str).fillna("")

# Make chlorine_candidate robust
if "chlorine_candidate" in df.columns:
    df["chlorine_candidate"] = (
        df["chlorine_candidate"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )
else:
    df["chlorine_candidate"] = False

# Numeric cleanup
numeric_cols = [
    "assigned_population",
    "households_est",
    "priority_basic",
    "pop_cell_100m",
    "pop_300m_est",
    "households_300m_est",
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

st.sidebar.header("Filters")

# State filter
state_options = ["All"] + sorted([x for x in df["state"].dropna().unique() if x and x != "nan"])
state = st.sidebar.selectbox("State", state_options)

filtered = df.copy()
if state != "All":
    filtered = filtered[filtered["state"] == state]

# LGA filter
lga_options = ["All"] + sorted([x for x in filtered["lga"].dropna().unique() if x and x != "nan"])
lga = st.sidebar.selectbox("LGA", lga_options)

if lga != "All":
    filtered = filtered[filtered["lga"] == lga]

# Ward filter
ward_options = ["All"] + sorted([x for x in filtered["ward"].dropna().unique() if x and x != "nan"])
ward = st.sidebar.selectbox("Ward", ward_options)

if ward != "All":
    filtered = filtered[filtered["ward"] == ward]

# Water tech filter
tech_options = ["All"] + sorted([x for x in filtered["water_tech"].dropna().unique() if x and x != "nan"])
water_tech = st.sidebar.selectbox("Water Technology", tech_options)

if water_tech != "All":
    filtered = filtered[filtered["water_tech"] == water_tech]

# Status filter
status_options = ["All"] + sorted([x for x in filtered["status"].dropna().unique() if x and x != "nan"])
status = st.sidebar.selectbox("Status", status_options)

if status != "All":
    filtered = filtered[filtered["status"] == status]

# Chlorine candidate only
candidate_only = st.sidebar.checkbox("Only chlorine candidate sites", value=False)
if candidate_only:
    filtered = filtered[filtered["chlorine_candidate"] == True]

# Population slider
max_assigned = int(filtered["assigned_population"].dropna().max()) if filtered["assigned_population"].notna().any() else 0
min_assigned_pop = st.sidebar.slider("Minimum assigned population", 0, max_assigned, 0)
filtered = filtered[filtered["assigned_population"].fillna(0) >= min_assigned_pop]

# 300m households slider
max_hh_300 = int(filtered["households_300m_est"].dropna().max()) if "households_300m_est" in filtered.columns and filtered["households_300m_est"].notna().any() else 0
min_hh_300 = st.sidebar.slider("Minimum households within ~300m", 0, max_hh_300, 0)
if "households_300m_est" in filtered.columns:
    filtered = filtered[filtered["households_300m_est"].fillna(0) >= min_hh_300]

# Sort option
sort_by = st.sidebar.selectbox(
    "Sort by",
    [
        "assigned_population",
        "households_est",
        "pop_300m_est",
        "households_300m_est",
        "priority_basic",
    ],
)

sort_ascending = st.sidebar.checkbox("Sort ascending", value=False)

if sort_by in filtered.columns:
    filtered = filtered.sort_values(by=sort_by, ascending=sort_ascending, na_position="last")

# Summary metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sites shown", f"{len(filtered):,}")
c2.metric("Total assigned population", f"{int(filtered['assigned_population'].fillna(0).sum()):,}")
c3.metric("Total households est.", f"{int(filtered['households_est'].fillna(0).sum()):,}")
c4.metric("Chlorine candidates", f"{int(filtered['chlorine_candidate'].sum()):,}")

st.subheader("Filtered Waterpoints")

display_cols = [
    "state",
    "lga",
    "ward",
    "water_tech",
    "status",
    "management",
    "assigned_population",
    "households_est",
    "pop_300m_est",
    "households_300m_est",
    "chlorine_candidate",
    "longitude",
    "latitude",
]

available_display_cols = [c for c in display_cols if c in filtered.columns]
st.dataframe(filtered[available_display_cols], use_container_width=True)

st.subheader("Map")
map_df = filtered.copy()
if "latitude" in map_df.columns and "longitude" in map_df.columns:
    map_df = map_df.dropna(subset=["latitude", "longitude"]).rename(
        columns={"latitude": "lat", "longitude": "lon"}
    )
    if len(map_df) > 0:
        st.map(map_df[["lat", "lon"]])
    else:
        st.info("No mappable points after filtering.")
else:
    st.info("Latitude/longitude columns not found.")

st.subheader("Top Intervention Candidates")
rank_cols = [
    "state",
    "lga",
    "ward",
    "water_tech",
    "status",
    "assigned_population",
    "households_est",
    "pop_300m_est",
    "households_300m_est",
    "chlorine_candidate",
]
available_rank_cols = [c for c in rank_cols if c in filtered.columns]

top_candidates = filtered.copy()
if "chlorine_candidate" in top_candidates.columns:
    top_candidates = top_candidates[top_candidates["chlorine_candidate"] == True]

if len(top_candidates) > 0:
    st.dataframe(top_candidates[available_rank_cols].head(100), use_container_width=True)
else:
    st.info("No chlorine candidate sites match the current filters.")

# Download button
csv_data = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download filtered data as CSV",
    data=csv_data,
    file_name="filtered_waterpoints.csv",
    mime="text/csv",
)