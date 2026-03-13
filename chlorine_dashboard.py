import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(layout="wide")

# -------------------------------------------------------
# PAGE HEADER
# -------------------------------------------------------

st.title("Nigeria Waterpoint Identification Tool – v1.7")
st.subheader("Geospatial screening tool for chlorine dispenser targeting")

st.write(
"""
This tool combines **waterpoint infrastructure data**, **population catchment estimates**, and **DHS + GBD mortality data**
to identify candidate locations for chlorine dispenser deployment.

The tool is intended to support **planning and prioritization of interventions** aimed at reducing
waterborne disease and child mortality.
"""
)

# -------------------------------------------------------
# DISCLAIMER
# -------------------------------------------------------

st.info(
"""
This is a planning tool only.

Waterpoint datasets may be incomplete or outdated and eligibility must be confirmed through field verification.

The tool identifies candidate sites based on:
- waterpoint technology
- operational status
- nearby population
"""
)

# -------------------------------------------------------
# SIDEBAR ASSUMPTIONS
# -------------------------------------------------------

st.sidebar.header("Planning Assumptions")

uptake = st.sidebar.slider(
    "Effective uptake (%)",
    min_value=10,
    max_value=80,
    value=40
) / 100

mortality_reduction = st.sidebar.slider(
    "Mortality reduction (%)",
    min_value=2,
    max_value=15,
    value=6
) / 100

household_size = st.sidebar.slider(
    "Household size",
    min_value=3,
    max_value=8,
    value=5
)

# -------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------

@st.cache_data
def load_waterpoints():
    df = pd.read_excel(
        "nigeria_water_access_analysis.xlsx",
        sheet_name="waterpoints"
    )
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
# STATE PRIORITIZATION TABLE
# -------------------------------------------------------

st.header("State Mortality Overview")

state_table = mortality[
    [
        "state",
        "u5_mortality_per_1000",
        "annual_u5_mortality",
        "diarrheal_share",
        "unsafe_water_fraction"
    ]
].copy()

# Convert to percentage for display
state_table["Annual U5 mortality (%)"] = state_table["annual_u5_mortality"] * 100

# Sort by highest mortality
state_table = state_table.sort_values(
    by="Annual U5 mortality (%)",
    ascending=False
)

# Round values
state_table = state_table.round({
    "Annual U5 mortality (%)": 2,
    "diarrheal_share": 2,
    "unsafe_water_fraction": 2
})

# Rename for display
state_table = state_table.rename(columns={
    "diarrheal_share": "Diarrheal share (%)",
    "unsafe_water_fraction": "Unsafe water attributable (%)"
})

# Display table (no highlighting)
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
# WATERPOINT CLASSIFICATION
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

# -------------------------------------------------------
# FUNCTIONAL STATUS
# -------------------------------------------------------

waterpoints["functional"] = (
    waterpoints["status"].str.contains("Functional", case=False, na=False)
    &
    ~waterpoints["status"].str.contains("Non-Functional", case=False, na=False)
)

# -------------------------------------------------------
# ELIGIBILITY RULE
# -------------------------------------------------------

waterpoints["eligible"] = (
    (waterpoints["waterpoint_type"] == "Hand Pump")
    &
    (waterpoints["functional"] == True)
)

# -------------------------------------------------------
# MERGE MORTALITY DATA
# -------------------------------------------------------

df = waterpoints.merge(
    mortality[["state", "annual_u5_mortality", "annual_water_addressable_mortality"]],
    on="state",
    how="left"
)

# -------------------------------------------------------
# IMPACT CALCULATIONS
# -------------------------------------------------------

df["population_served"] = df["households_300m_est"] * household_size

df["children_under5"] = df["population_served"] * 0.15

df["expected_child_deaths"] = df["children_under5"] * df["annual_u5_mortality"]

df["deaths_averted"] = (
    df["expected_child_deaths"]
    * mortality_reduction
    * uptake
)

# -------------------------------------------------------
# OPPORTUNITY SCORE
# -------------------------------------------------------

df["opportunity_score"] = (
    df["households_300m_est"]
    * df["annual_water_addressable_mortality"]
    * df["eligible"].astype(int)
)

# -------------------------------------------------------
# DASHBOARD METRICS
# -------------------------------------------------------

st.header("Dashboard Summary")

total_waterpoints = len(df)
eligible_pumps = df["eligible"].sum()
population_served = int(df["population_served"].sum())
deaths_averted_total = df["deaths_averted"].sum()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Waterpoints identified", f"{total_waterpoints:,}")
col2.metric("Eligible hand pumps", f"{eligible_pumps:,}")
col3.metric("Population served", f"{population_served:,}")
col4.metric("Deaths averted per year", f"{deaths_averted_total:.1f}")

# -------------------------------------------------------
# LGA RANKING
# -------------------------------------------------------

st.header("LGA Opportunity Ranking")

lga_table = (
    df.groupby(["state", "lga"])
    .agg(
        eligible_pumps=("eligible", "sum"),
        total_households=("households_300m_est", "sum"),
        opportunity_score=("opportunity_score", "sum")
    )
    .reset_index()
)

lga_table = lga_table.sort_values(
    by="opportunity_score",
    ascending=False
)

st.dataframe(lga_table, use_container_width=True)

# -------------------------------------------------------
# WATERPOINT RANKING TABLE
# -------------------------------------------------------

st.header("Waterpoint Ranking")

waterpoint_table = df[
    [
        "state",
        "lga",
        "ward",
        "waterpoint_type",
        "status",
        "households_300m_est",
        "opportunity_score",
        "latitude",
        "longitude"
    ]
].copy()

waterpoint_table = waterpoint_table.rename(columns={
    "households_300m_est": "Households within 300m",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "opportunity_score": "Opportunity Score"
})

waterpoint_table = waterpoint_table.sort_values(
    by="Opportunity Score",
    ascending=False
)

st.dataframe(waterpoint_table, use_container_width=True)

# -------------------------------------------------------
# MAP
# -------------------------------------------------------

st.header("Waterpoint Map")

df["color"] = df["eligible"].apply(
    lambda x: [0, 200, 0] if x else [200, 0, 0]
)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position=["longitude", "latitude"],
    get_color="color",
    get_radius=120,
    pickable=True
)

tooltip = {
    "html": """
    <b>State:</b> {state}<br/>
    <b>LGA:</b> {lga}<br/>
    <b>Ward:</b> {ward}<br/>
    <b>Waterpoint type:</b> {waterpoint_type}<br/>
    <b>Status:</b> {status}<br/>
    <b>Eligible:</b> {eligible}<br/>
    <b>Households within 300m:</b> {households_300m_est}<br/>
    <b>Latitude:</b> {latitude}<br/>
    <b>Longitude:</b> {longitude}<br/>
    <b>Opportunity score:</b> {opportunity_score}
    """
}

view_state = pdk.ViewState(
    latitude=df["latitude"].mean(),
    longitude=df["longitude"].mean(),
    zoom=5
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip=tooltip
)

st.pydeck_chart(deck)

# -------------------------------------------------------
# EXPORT
# -------------------------------------------------------

st.header("Export for Field Verification")

export_df = df[
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

csv = export_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download filtered dataset",
    data=csv,
    file_name="nigeria_waterpoints_field_verification.csv",
    mime="text/csv"
)