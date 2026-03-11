import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="Nigeria Waterpoint Identification Tool", layout="wide")

st.title("Nigeria Waterpoint Identification Tool – v1.1")
st.caption("Version 1.1 – Adds DHS/GBD mortality layer and deaths-averted screening aligned to GiveWell principles")

st.markdown("""
### How to use this tool

1. Select **State → LGA → Ward** to focus on a geography.
2. Use filters to screen waterpoints by **population and eligibility**.
3. Toggle **Only Eligible Hand Pump Sites** to focus on likely chlorine dispenser locations.
4. Review **LGA and Ward rankings** to identify underserved areas.
5. Hover on map points to view details for each waterpoint.
6. Review **deaths averted estimates** for candidate sites.
7. Download filtered results for planning or field teams.

Green points = **eligible chlorine candidate sites**  
Red points = **not eligible**
""")

@st.cache_data
def load_waterpoints():
    return pd.read_excel("nigeria_water_access_analysis.xlsx", sheet_name="waterpoints")

@st.cache_data
def load_state_mortality():
    return pd.read_excel("state_mortality_inputs_exact_DHS_GBD.xlsx", sheet_name="state_inputs")

df = load_waterpoints().copy()
mort = load_state_mortality().copy()

# Clean waterpoint text columns
text_cols = ["state","lga","ward","water_tech","status"]
for col in text_cols:
    if col in df.columns:
        df[col] = df[col].fillna("MISSING").astype(str)

# Numeric conversions
num_cols = [
    "longitude","latitude",
    "assigned_population",
    "households_300m_est"
]

for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Waterpoint classification
df["waterpoint_type"] = "Other"

df.loc[
    df["water_tech"].str.contains("Hand Pump", case=False, na=False),
    "waterpoint_type"
] = "Hand Pump"

df.loc[
    df["water_tech"].str.contains("Motorized", case=False, na=False),
    "waterpoint_type"
] = "Motorized Pump"

df.loc[
    df["water_tech"].str.contains("Tapstand", case=False, na=False),
    "waterpoint_type"
] = "Tapstand"

# Functional status
df["functional"] = (
    df["status"].str.contains("Functional", case=False, na=False)
    & ~df["status"].str.contains("Non-Functional", case=False, na=False)
)

# Eligible sites
df["eligible"] = (
    (df["waterpoint_type"] == "Hand Pump")
    & (df["functional"])
)

# Merge mortality data
df = df.merge(mort, on="state", how="left")

# Sidebar model parameters
st.sidebar.header("Model parameters")

under5_share = st.sidebar.slider(
    "Share of population under 5",
    0.05, 0.30, 0.15
)

mortality_reduction = st.sidebar.slider(
    "Mortality reduction from chlorination",
    0.01, 0.15, 0.06
)

uptake = st.sidebar.slider(
    "Effective uptake / adherence",
    0.05, 0.90, 0.40
)

household_size = st.sidebar.slider(
    "Household size",
    3.0, 8.0, 5.0
)

# Impact model
df["population_served"] = df["households_300m_est"].fillna(0) * household_size

df["children_under5_served"] = (
    df["population_served"] * under5_share
)

df["expected_child_deaths_per_year"] = (
    df["children_under5_served"]
    * df["annual_u5_mortality"]
)

df["deaths_averted_per_year"] = (
    df["expected_child_deaths_per_year"]
    * mortality_reduction
    * uptake
)

# Map colors
df["color_r"] = df["eligible"].apply(lambda x: 0 if x else 220)
df["color_g"] = df["eligible"].apply(lambda x: 170 if x else 50)
df["color_b"] = 60

# Sidebar filters
st.sidebar.header("Filters")

state = st.sidebar.selectbox(
    "State",
    ["All"] + sorted(df["state"].dropna().unique())
)

filtered = df.copy()

if state != "All":
    filtered = filtered[filtered["state"] == state]

lga = st.sidebar.selectbox(
    "LGA",
    ["All"] + sorted(filtered["lga"].dropna().unique())
)

if lga != "All":
    filtered = filtered[filtered["lga"] == lga]

ward = st.sidebar.selectbox(
    "Ward",
    ["All"] + sorted(filtered["ward"].dropna().unique())
)

if ward != "All":
    filtered = filtered[filtered["ward"] == ward]

type_filter = st.sidebar.selectbox(
    "Waterpoint Type",
    ["All"] + sorted(filtered["waterpoint_type"].dropna().unique())
)

if type_filter != "All":
    filtered = filtered[
        filtered["waterpoint_type"] == type_filter
    ]

eligible_only = st.sidebar.checkbox(
    "Only Eligible Hand Pump Sites"
)

if eligible_only:
    filtered = filtered[filtered["eligible"]]

# Summary metrics
c1, c2, c3, c4 = st.columns(4)

c1.metric("Sites shown", len(filtered))

c2.metric("Eligible sites", int(filtered["eligible"].sum()))

c3.metric(
    "Population served",
    int(filtered["population_served"].fillna(0).sum())
)

c4.metric(
    "Deaths averted / year",
    f"{filtered['deaths_averted_per_year'].fillna(0).sum():.2f}"
)

# Top sites
st.subheader("Top candidate sites by deaths averted")

top_sites = filtered.sort_values(
    "deaths_averted_per_year",
    ascending=False
)

st.dataframe(
    top_sites[
        [
            "state","lga","ward",
            "waterpoint_type",
            "status",
            "eligible",
            "households_300m_est",
            "population_served",
            "deaths_averted_per_year"
        ]
    ].head(200),
    use_container_width=True
)

# Map
st.subheader("Map")

map_df = filtered.dropna(
    subset=["latitude","longitude"]
)

if len(map_df):

    tooltip = {
        "html": """
        <b>State:</b> {state}<br/>
        <b>LGA:</b> {lga}<br/>
        <b>Ward:</b> {ward}<br/>
        <b>Type:</b> {waterpoint_type}<br/>
        <b>Status:</b> {status}<br/>
        <b>Eligible:</b> {eligible}<br/>
        <b>HH within 300m:</b> {households_300m_est}<br/>
        <b>Deaths averted/year:</b> {deaths_averted_per_year}
        """
    }

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[longitude, latitude]",
        get_fill_color="[color_r, color_g, color_b]",
        get_radius=120,
        pickable=True
    )

    view = pdk.ViewState(
        latitude=float(map_df["latitude"].mean()),
        longitude=float(map_df["longitude"].mean()),
        zoom=6 if state == "All" else 8
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            tooltip=tooltip
        )
    )

    st.caption(
        "Green = eligible hand pump sites | Red = ineligible sites"
    )

# Download
st.subheader("Download filtered data")

csv = filtered.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download filtered dataset",
    csv,
    "filtered_waterpoints_with_mortality.csv",
    "text/csv"
)