import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(layout="wide")

# -------------------------------------------------------
# MAPBOX TOKEN
# -------------------------------------------------------
try:
    pdk.settings.mapbox_api_key = st.secrets["MAPBOX_API_KEY"]
    MAP_STYLE = "mapbox://styles/mapbox/satellite-streets-v12"
except:
    MAP_STYLE = "light"

# -------------------------------------------------------
# PAGE HEADER
# -------------------------------------------------------

st.title("Nigeria Waterpoint Identification Tool – v1.7")
st.subheader("Geospatial screening tool for chlorine dispenser targeting")

st.write(
"""
This tool combines **waterpoint infrastructure data**, **population catchment estimates**, and **DHS + GBD mortality data**
to identify candidate locations for chlorine dispenser deployment.
"""
)

# -------------------------------------------------------
# DISCLAIMER
# -------------------------------------------------------

st.info(
"""
This is a planning tool only.

Waterpoint datasets may be incomplete or outdated and eligibility must be confirmed through field verification.
"""
)

# -------------------------------------------------------
# SIDEBAR ASSUMPTIONS
# -------------------------------------------------------

st.sidebar.header("Planning Assumptions")

uptake = st.sidebar.slider("Effective uptake (%)", 10, 80, 40) / 100
mortality_reduction = st.sidebar.slider("Mortality reduction (%)", 2, 15, 6) / 100
household_size = st.sidebar.slider("Household size", 3, 8, 5)

# -------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------

@st.cache_data
def load_waterpoints():
    df = pd.read_excel("nigeria_water_access_analysis.xlsx", sheet_name="waterpoints")
    if "country" in df.columns:
        df = df[df["country"].str.lower() == "nigeria"]
    return df

@st.cache_data
def load_mortality():
    df = pd.read_excel(
        "Nigeria_Statewise mortality and diarrhea prevalence.xlsx",
        sheet_name="state_priority"
    )

    df = df.rename(columns={
        "GiveWell formula for annualized mortality value": "annual_u5_mortality",
        "diarrheal_share_pct": "diarrheal_share",
        "unsafe_water_attr_pct": "unsafe_water_fraction",
        "annual_water_addressable_diarrheal_mortality_pct": "annual_water_addressable_mortality"
    })

    return df

waterpoints = load_waterpoints()
mortality = load_mortality()

# -------------------------------------------------------
# FILTER LOW-MORTALITY STATES (<2%)
# -------------------------------------------------------

mortality = mortality[mortality["annual_u5_mortality"] >= 0.02]

# -------------------------------------------------------
# STATE TABLE
# -------------------------------------------------------

st.header("State Mortality Overview")

state_table = mortality[
    ["state", "u5_mortality_per_1000", "annual_u5_mortality", "diarrheal_share", "unsafe_water_fraction"]
].copy()

state_table["Annual U5 mortality (%)"] = state_table["annual_u5_mortality"] * 100

state_table = state_table.sort_values(by="Annual U5 mortality (%)", ascending=False)

state_table = state_table.round({
    "Annual U5 mortality (%)": 2,
    "diarrheal_share": 2,
    "unsafe_water_fraction": 2
})

state_table = state_table.rename(columns={
    "diarrheal_share": "Diarrheal share (%)",
    "unsafe_water_fraction": "Unsafe water attributable (%)"
})

st.dataframe(
    state_table[
        [
            "state",
            "u5_mortality_per_1000",
            "Annual U5 mortality (%)",
            "Diarrheal share (%)",
            "Unsafe water attributable (%)"
        ]
    ],
    use_container_width=True
)

# -------------------------------------------------------
# WATERPOINT PROCESSING
# -------------------------------------------------------

def classify_waterpoint(tech):
    if pd.isna(tech):
        return "Other"
    tech = str(tech)
    if "Hand Pump" in tech:
        return "Hand Pump"
    elif "Motorized" in tech:
        return "Motorized Pump"
    elif "Tapstand" in tech:
        return "Tapstand"
    else:
        return "Other"

waterpoints["waterpoint_type"] = waterpoints["water_tech"].apply(classify_waterpoint)

waterpoints["functional"] = (
    waterpoints["status"].str.contains("Functional", case=False, na=False)
    &
    ~waterpoints["status"].str.contains("Non-Functional", case=False, na=False)
)

waterpoints["eligible"] = (
    (waterpoints["waterpoint_type"] == "Hand Pump")
    &
    (waterpoints["functional"])
)

# -------------------------------------------------------
# MERGE
# -------------------------------------------------------

df = waterpoints.merge(
    mortality[["state", "annual_u5_mortality", "annual_water_addressable_mortality"]],
    on="state",
    how="inner"
)

# -------------------------------------------------------
# DATA CLEANING
# -------------------------------------------------------

df["households_300m_est"] = pd.to_numeric(df["households_300m_est"], errors="coerce")
df.loc[df["households_300m_est"] <= -1000, "households_300m_est"] = None
df.loc[df["households_300m_est"] < 0, "households_300m_est"] = None
df = df.dropna(subset=["households_300m_est"])
df.loc[df["households_300m_est"] > 1000, "households_300m_est"] = 1000

df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
df = df.dropna(subset=["latitude", "longitude"])
df = df[
    (df["latitude"].between(3, 15)) &
    (df["longitude"].between(2, 15))
]

df["annual_u5_mortality"] = pd.to_numeric(df["annual_u5_mortality"], errors="coerce")
df["annual_u5_mortality"] = df["annual_u5_mortality"].clip(lower=0, upper=1)

# -------------------------------------------------------
# FILTERS
# -------------------------------------------------------

st.sidebar.header("Location Filters")

states = sorted(df["state"].dropna().unique())

all_states = st.sidebar.checkbox("All States", value=True)

if all_states:
    df_filtered = df.copy()
else:
    selected_states = st.sidebar.multiselect("Select State(s)", states)
    df_filtered = df[df["state"].isin(selected_states)]

all_lgas = st.sidebar.checkbox("All LGAs", value=True)
if not all_lgas:
    lgas = sorted(df_filtered["lga"].dropna().unique())
    selected_lgas = st.sidebar.multiselect("Select LGA(s)", lgas)
    df_filtered = df_filtered[df_filtered["lga"].isin(selected_lgas)]

all_wards = st.sidebar.checkbox("All Wards", value=True)
if not all_wards:
    wards = sorted(df_filtered["ward"].dropna().unique())
    selected_wards = st.sidebar.multiselect("Select Ward(s)", wards)
    df_filtered = df_filtered[df_filtered["ward"].isin(selected_wards)]

only_eligible = st.sidebar.checkbox("Only eligible waterpoints", value=False)
if only_eligible:
    df_filtered = df_filtered[df_filtered["eligible"]]

# -------------------------------------------------------
# IMPACT CALCULATIONS
# -------------------------------------------------------

df_filtered["population_served"] = df_filtered["households_300m_est"] * household_size
df_filtered["children_under5"] = df_filtered["population_served"] * 0.15
df_filtered["expected_child_deaths"] = df_filtered["children_under5"] * df_filtered["annual_u5_mortality"]

df_filtered["deaths_averted"] = (
    df_filtered["expected_child_deaths"]
    * mortality_reduction
    * uptake
)

df_filtered["opportunity_score"] = (
    df_filtered["households_300m_est"]
    * df_filtered["annual_water_addressable_mortality"]
    * df_filtered["eligible"].astype(int)
)

# -------------------------------------------------------
# METRICS
# -------------------------------------------------------

st.header("Dashboard Summary")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Waterpoints identified", f"{len(df_filtered):,}")
col2.metric("Eligible hand pumps", f"{df_filtered['eligible'].sum():,}")
col3.metric("Population served", f"{int(df_filtered['population_served'].sum()):,}")
col4.metric("Deaths averted per year", f"{df_filtered['deaths_averted'].sum():.1f}")

# -------------------------------------------------------
# MAP (ENHANCED VISIBILITY)
# -------------------------------------------------------

st.header("Waterpoint Map")

df_filtered["color"] = df_filtered["eligible"].apply(
    lambda x: [0, 255, 0, 200] if x else [255, 0, 0, 200]
)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_filtered,
    get_position=["longitude", "latitude"],
    get_radius="households_300m_est * 2",
    radius_min_pixels=3,
    radius_max_pixels=20,
    get_fill_color="color",
    pickable=True,
    opacity=0.8,
)

if len(df_filtered) > 0:
    center_lat = df_filtered["latitude"].mean()
    center_lon = df_filtered["longitude"].mean()
else:
    center_lat = 9
    center_lon = 8

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lon,
    zoom=6,
    pitch=0,
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip={
        "html": """
        <b>State:</b> {state}<br/>
        <b>LGA:</b> {lga}<br/>
        <b>Ward:</b> {ward}<br/>
        <b>Type:</b> {waterpoint_type}<br/>
        <b>Status:</b> {status}<br/>
        <b>Eligible:</b> {eligible}<br/>
        <b>HHs:</b> {households_300m_est}<br/>
        <b>Score:</b> {opportunity_score}
        """
    },
    map_style=MAP_STYLE
)

st.pydeck_chart(deck)

# -------------------------------------------------------
# EXPORT
# -------------------------------------------------------

st.header("Export for Field Verification")

export_df = df_filtered[
    [
        "state",
        "lga",
        "ward",
        "waterpoint_type",
        "status",
        "eligible",
        "households_300m_est",
        "population_served",
        "latitude",
        "longitude",
        "opportunity_score"
    ]
]

st.download_button(
    label="Download CSV",
    data=export_df.to_csv(index=False).encode("utf-8"),
    file_name="nigeria_waterpoints_field_verification.csv",
    mime="text/csv"
)