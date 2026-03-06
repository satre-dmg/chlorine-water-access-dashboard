import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="Nigeria Water Access Explorer", layout="wide")

st.title("Nigeria Water Access Explorer")
st.caption("Waterpoint screening and cascade planning tool for chlorine intervention targeting.")

st.markdown("""
### How to use this tool
1. **Select a State** to narrow the planning geography.
2. Review the **LGA ranking** and **Ward ranking** tables to identify higher-need areas.
3. Use filters for **waterpoint type**, **status**, **minimum assigned population**, and **minimum households within ~300m**.
4. Toggle **Only Eligible Hand Pump Sites** to focus on likely chlorine dispenser candidates.
5. Inspect the **map** and hover on points to view details such as waterpoint type, status, ward, and population.
6. Download the filtered data as CSV for planning or sharing.
""")

@st.cache_data
def load_data():
    return pd.read_excel("nigeria_water_access_analysis.xlsx", sheet_name="waterpoints")

df = load_data().copy()

# -----------------------------
# Column cleanup
# -----------------------------
text_cols = [
    "state", "lga", "ward", "water_tech", "source_category",
    "status", "management"
]
for col in text_cols:
    if col in df.columns:
        df[col] = df[col].fillna("MISSING").astype(str).str.strip()

numeric_cols = [
    "longitude", "latitude", "assigned_population", "households_est",
    "priority_basic", "pop_cell_100m", "pop_300m_est", "households_300m_est"
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# -----------------------------
# Waterpoint classification
# -----------------------------
df["waterpoint_type"] = "Other"
df.loc[df["water_tech"].str.contains("Hand Pump", case=False, na=False), "waterpoint_type"] = "Hand Pump"
df.loc[df["water_tech"].str.contains("Motorized", case=False, na=False), "waterpoint_type"] = "Motorized Pump"
df.loc[df["water_tech"].str.contains("Tapstand", case=False, na=False), "waterpoint_type"] = "Tapstand"

# Functional classification
df["functional_flag"] = (
    df["status"].str.contains("Functional", case=False, na=False)
    & ~df["status"].str.contains("Non-Functional", case=False, na=False)
)

# Eligibility rule for chlorine candidate sites
df["eligible"] = (
    (df["waterpoint_type"] == "Hand Pump")
    & (df["functional_flag"])
)

# Map color fields
df["color_r"] = df["eligible"].apply(lambda x: 0 if x else 220)
df["color_g"] = df["eligible"].apply(lambda x: 170 if x else 50)
df["color_b"] = df["eligible"].apply(lambda x: 60 if x else 60)

# Safe display fields for hover/map
for col in ["state", "lga", "ward", "waterpoint_type", "status"]:
    if col not in df.columns:
        df[col] = "MISSING"

# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.header("Filters")

state_options = ["All"] + sorted([x for x in df["state"].dropna().unique() if x and x != "nan"])
state = st.sidebar.selectbox("State", state_options)

filtered = df.copy()
if state != "All":
    filtered = filtered[filtered["state"] == state]

lga_options = ["All"] + sorted([x for x in filtered["lga"].dropna().unique() if x and x != "nan"])
lga = st.sidebar.selectbox("LGA", lga_options)
if lga != "All":
    filtered = filtered[filtered["lga"] == lga]

ward_options = ["All"] + sorted([x for x in filtered["ward"].dropna().unique() if x and x != "nan"])
ward = st.sidebar.selectbox("Ward", ward_options)
if ward != "All":
    filtered = filtered[filtered["ward"] == ward]

type_options = ["All"] + sorted([x for x in filtered["waterpoint_type"].dropna().unique() if x and x != "nan"])
waterpoint_type = st.sidebar.selectbox("Waterpoint Type", type_options)
if waterpoint_type != "All":
    filtered = filtered[filtered["waterpoint_type"] == waterpoint_type]

status_options = ["All"] + sorted([x for x in filtered["status"].dropna().unique() if x and x != "nan"])
status = st.sidebar.selectbox("Status", status_options)
if status != "All":
    filtered = filtered[filtered["status"] == status]

eligible_only = st.sidebar.checkbox("Only Eligible Hand Pump Sites", value=False)
if eligible_only:
    filtered = filtered[filtered["eligible"] == True]

max_assigned = int(filtered["assigned_population"].fillna(0).max()) if len(filtered) > 0 else 0
min_assigned = st.sidebar.slider("Minimum Assigned Population", 0, max_assigned if max_assigned > 0 else 1, 0)
st.sidebar.write(f"Selected minimum assigned population: **{min_assigned:,}**")
filtered = filtered[filtered["assigned_population"].fillna(0) >= min_assigned]

max_hh300 = int(filtered["households_300m_est"].fillna(0).max()) if len(filtered) > 0 else 0
min_hh300 = st.sidebar.slider("Minimum Households Within ~300m", 0, max_hh300 if max_hh300 > 0 else 1, 0)
st.sidebar.write(f"Selected minimum households within ~300m: **{min_hh300:,}**")
filtered = filtered[filtered["households_300m_est"].fillna(0) >= min_hh300]

# -----------------------------
# Summary metrics
# -----------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sites shown", f"{len(filtered):,}")
c2.metric("Eligible sites", f"{int(filtered['eligible'].sum()):,}")
c3.metric("Assigned population", f"{int(filtered['assigned_population'].fillna(0).sum()):,}")
c4.metric("Households within ~300m", f"{int(filtered['households_300m_est'].fillna(0).sum()):,}")

# -----------------------------
# Cascaded ranking: LGA
# -----------------------------
st.subheader("LGA Ranking")
if len(filtered) > 0:
    lga_rank = (
        filtered.groupby(["state", "lga"], dropna=False)
        .agg(
            waterpoints=("waterpoint_type", "count"),
            eligible_sites=("eligible", "sum"),
            assigned_population=("assigned_population", "sum"),
            households_300m_est=("households_300m_est", "sum"),
        )
        .reset_index()
    )
    lga_rank["population_per_waterpoint"] = (
        lga_rank["assigned_population"] / lga_rank["waterpoints"].replace(0, pd.NA)
    )
    lga_rank["households_300m_per_site"] = (
        lga_rank["households_300m_est"] / lga_rank["waterpoints"].replace(0, pd.NA)
    )
    lga_rank = lga_rank.sort_values("population_per_waterpoint", ascending=False, na_position="last")
    st.dataframe(lga_rank, use_container_width=True)
else:
    st.info("No rows match the current filters.")

# -----------------------------
# Cascaded ranking: Ward
# -----------------------------
st.subheader("Ward Ranking")
if len(filtered) > 0:
    ward_rank = (
        filtered.groupby(["state", "lga", "ward"], dropna=False)
        .agg(
            waterpoints=("waterpoint_type", "count"),
            eligible_sites=("eligible", "sum"),
            assigned_population=("assigned_population", "sum"),
            households_300m_est=("households_300m_est", "sum"),
        )
        .reset_index()
    )

    ward_rank["population_per_waterpoint"] = (
        ward_rank["assigned_population"] / ward_rank["waterpoints"].replace(0, pd.NA)
    )
    ward_rank["households_300m_per_site"] = (
        ward_rank["households_300m_est"] / ward_rank["waterpoints"].replace(0, pd.NA)
    )

    # Need score (simple first pass, 0-1 normalized within current filtered set)
    for metric in ["population_per_waterpoint", "households_300m_per_site", "eligible_sites"]:
        ward_rank[metric] = pd.to_numeric(ward_rank[metric], errors="coerce")

    # Normalize pressure metrics
    def normalize(series):
        s = series.fillna(0)
        if s.max() == s.min():
            return pd.Series([0] * len(s), index=s.index)
        return (s - s.min()) / (s.max() - s.min())

    ward_rank["norm_pop_pressure"] = normalize(ward_rank["population_per_waterpoint"])
    ward_rank["norm_access"] = normalize(ward_rank["households_300m_per_site"])

    # Fewer eligible sites can imply greater need, so invert normalized eligible count
    ward_rank["norm_eligible_inverse"] = 1 - normalize(ward_rank["eligible_sites"])

    ward_rank["need_score"] = (
        0.45 * ward_rank["norm_pop_pressure"]
        + 0.35 * ward_rank["norm_access"]
        + 0.20 * ward_rank["norm_eligible_inverse"]
    )

    ward_rank = ward_rank.sort_values("need_score", ascending=False, na_position="last")
    show_cols = [
        "state", "lga", "ward", "waterpoints", "eligible_sites",
        "assigned_population", "households_300m_est",
        "population_per_waterpoint", "households_300m_per_site", "need_score"
    ]
    st.dataframe(ward_rank[show_cols], use_container_width=True)
else:
    st.info("No ward ranking available for current filters.")

# -----------------------------
# Top candidate sites
# -----------------------------
st.subheader("Top Eligible Hand Pump Sites")
top_sites = filtered[filtered["eligible"] == True].copy()
top_sites = top_sites.sort_values(
    ["households_300m_est", "assigned_population"],
    ascending=[False, False],
    na_position="last"
)

top_cols = [
    "state", "lga", "ward", "waterpoint_type", "status",
    "assigned_population", "households_est",
    "pop_300m_est", "households_300m_est",
    "longitude", "latitude"
]
top_cols = [c for c in top_cols if c in top_sites.columns]

if len(top_sites) > 0:
    st.dataframe(top_sites[top_cols].head(200), use_container_width=True)
else:
    st.info("No eligible sites match the current filters.")

# -----------------------------
# Interactive map
# -----------------------------
st.subheader("Map")

map_df = filtered.dropna(subset=["latitude", "longitude"]).copy()

if len(map_df) > 0:
    tooltip = {
        "html": """
        <b>State:</b> {state} <br/>
        <b>LGA:</b> {lga} <br/>
        <b>Ward:</b> {ward} <br/>
        <b>Type:</b> {waterpoint_type} <br/>
        <b>Status:</b> {status} <br/>
        <b>Eligible:</b> {eligible} <br/>
        <b>Assigned population:</b> {assigned_population} <br/>
        <b>Households ~300m:</b> {households_300m_est}
        """,
        "style": {"backgroundColor": "steelblue", "color": "white"},
    }

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[longitude, latitude]",
        get_fill_color="[color_r, color_g, color_b, 180]",
        get_radius=120,
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=float(map_df["latitude"].mean()),
        longitude=float(map_df["longitude"].mean()),
        zoom=6 if state == "All" else 8,
        pitch=0,
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="mapbox://styles/mapbox/light-v9",
    )

    st.pydeck_chart(deck, use_container_width=True)
    st.caption("Green = eligible hand pump site, Red = ineligible site.")
else:
    st.info("No mappable points for the current filters.")

# -----------------------------
# Filtered data table
# -----------------------------
st.subheader("Filtered Waterpoints Table")

table_cols = [
    "state", "lga", "ward", "waterpoint_type", "water_tech", "status", "management",
    "assigned_population", "households_est", "pop_300m_est", "households_300m_est",
    "eligible", "longitude", "latitude"
]
table_cols = [c for c in table_cols if c in filtered.columns]

st.dataframe(filtered[table_cols], use_container_width=True)

# -----------------------------
# Download
# -----------------------------
csv_data = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download filtered data as CSV",
    data=csv_data,
    file_name="filtered_waterpoints.csv",
    mime="text/csv",
)