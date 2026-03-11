import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="Nigeria Waterpoint Identification Tool", layout="wide")

st.title("Nigeria Waterpoint Identification Tool – v1.4")
st.caption("Geospatial screening tool for chlorine dispenser targeting")

st.markdown("""
This tool screens potential chlorine dispenser sites using:

• Waterpoint infrastructure data  
• Population catchment estimates  
• State-level mortality (DHS + GBD)

The tool is intended for **initial geographic prioritization only**.
Field verification is required before implementation.
""")

st.info("""
⚠️ Waterpoint data may be incomplete or outdated.

This tool should be used for **screening and planning only**.
Field verification is required before installation.
""")

# ---------------------------------------------------
# REFERENCES
# ---------------------------------------------------

with st.expander("References and methodology"):

    st.markdown("""
**Evidence Action – Dispensers for Safe Water**  
https://www.evidenceaction.org/programs/safe-water/dispensers-for-safe-water/

**IPA chlorine dispenser research**  
https://poverty-action.org/chlorine-dispensers-safe-water

**Kremer et al chlorine dispenser trials**  
https://www.nber.org/papers/w15280

**GiveWell water quality intervention analysis**  
https://www.givewell.org/international/technical/programs/water-quality

**Data sources**

Nigeria DHS 2024 – Under-5 mortality  
IHME Global Burden of Disease – diarrheal mortality  
GBD Risk factors – unsafe water attribution
""")

# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------

@st.cache_data
def load_waterpoints():
    return pd.read_excel("nigeria_water_access_analysis.xlsx", sheet_name="waterpoints")

@st.cache_data
def load_mortality():
    return pd.read_excel("state_mortality_inputs_exact_DHS_GBD.xlsx", sheet_name="state_inputs")

df = load_waterpoints()
mort = load_mortality()

df["state"] = df["state"].astype(str).str.strip()
mort["state"] = mort["state"].astype(str).str.strip()

df = df.merge(mort, on="state", how="left")

# ---------------------------------------------------
# CLEAN NUMERIC DATA
# ---------------------------------------------------

numeric_cols = [
"latitude",
"longitude",
"households_300m_est",
"assigned_population"
]

for c in numeric_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

df["households_300m_est"] = df["households_300m_est"].clip(lower=0)

# ---------------------------------------------------
# WATERPOINT CLASSIFICATION
# ---------------------------------------------------

df["waterpoint_type"] = "Other"

df.loc[df["water_tech"].str.contains("Hand Pump", case=False, na=False),"waterpoint_type"] = "Hand Pump"
df.loc[df["water_tech"].str.contains("Motorized", case=False, na=False),"waterpoint_type"] = "Motorized Pump"
df.loc[df["water_tech"].str.contains("Tapstand", case=False, na=False),"waterpoint_type"] = "Tapstand"

df["functional"] = (
df["status"].str.contains("Functional", case=False, na=False)
& ~df["status"].str.contains("Non-Functional", case=False, na=False)
)

df["eligible"] = (df["waterpoint_type"]=="Hand Pump") & (df["functional"])

# ---------------------------------------------------
# PROGRAM ASSUMPTIONS
# ---------------------------------------------------

st.sidebar.header("Program assumptions")

uptake_pct = st.sidebar.slider(
"Effective uptake (%)",
10,80,40
)

mortality_reduction_pct = st.sidebar.slider(
"Mortality reduction from clean water (%)",
2,15,6
)

household_size = st.sidebar.slider(
"Average household size (persons)",
3,8,5
)

uptake = uptake_pct/100
mortality_reduction = mortality_reduction_pct/100

# ---------------------------------------------------
# STATE PRIORITY SCORE
# ---------------------------------------------------

priority = mort.copy()

priority["priority_score"] = (
priority["annual_u5_mortality"]
* priority["diarrheal_share"]
* priority["unsafe_water_fraction"]
)

priority = priority.sort_values("priority_score", ascending=False)

st.subheader("High priority states for chlorine intervention")

display_priority = priority[[
"state",
"u5_mortality_per_1000",
"annual_u5_mortality",
"diarrheal_share",
"unsafe_water_fraction",
"priority_score"
]].copy()

display_priority["annual_u5_mortality"]=(display_priority["annual_u5_mortality"]*100).round(2).astype(str)+"%"
display_priority["diarrheal_share"]=(display_priority["diarrheal_share"]*100).round(2).astype(str)+"%"
display_priority["unsafe_water_fraction"]=(display_priority["unsafe_water_fraction"]*100).round(2).astype(str)+"%"

st.dataframe(display_priority.head(10), width="stretch")

# ---------------------------------------------------
# FILTERS
# ---------------------------------------------------

st.sidebar.header("Geographic filters")

states = st.sidebar.multiselect(
"Select states",
sorted(df["state"].dropna().unique())
)

if states:
    df = df[df["state"].isin(states)]

lgas = st.sidebar.multiselect(
"Select LGAs",
sorted(df["lga"].dropna().unique())
)

if lgas:
    df = df[df["lga"].isin(lgas)]

wards = st.sidebar.multiselect(
"Select wards",
sorted(df["ward"].dropna().unique())
)

if wards:
    df = df[df["ward"].isin(wards)]

eligible_only = st.sidebar.checkbox("Only eligible hand pumps")

if eligible_only:
    df = df[df["eligible"]]

# ---------------------------------------------------
# IMPACT MODEL
# ---------------------------------------------------

df["population_served"] = (
df["households_300m_est"] * household_size
)

df["children_under5"] = df["population_served"] * 0.15

df["expected_child_deaths"] = (
df["children_under5"] * df["annual_u5_mortality"]
)

df["deaths_averted"] = (
df["expected_child_deaths"]
* mortality_reduction
* uptake
)

# ---------------------------------------------------
# OPPORTUNITY SCORE
# ---------------------------------------------------

df["opportunity_score"] = (
df["households_300m_est"]
* df["annual_water_addressable_mortality"]
* df["eligible"].astype(int)
)

# ---------------------------------------------------
# SUMMARY METRICS
# ---------------------------------------------------

c1,c2,c3,c4 = st.columns(4)

c1.metric("Waterpoints identified",len(df))

c2.metric(
"Eligible hand pumps",
int(df["eligible"].sum())
)

c3.metric(
"Population served (people)",
int(df["population_served"].sum())
)

c4.metric(
"Deaths averted per year (children)",
round(df["deaths_averted"].sum(),2)
)

# ---------------------------------------------------
# LGA OPPORTUNITY RANKING
# ---------------------------------------------------

st.subheader("Top LGAs for chlorine intervention")

lga_rank = df.groupby(["state","lga"]).agg(
eligible_pumps=("eligible","sum"),
total_households=("households_300m_est","sum"),
opportunity_score=("opportunity_score","sum")
).reset_index()

lga_rank = lga_rank.sort_values("opportunity_score",ascending=False)

st.dataframe(lga_rank.head(20), width="stretch")

# ---------------------------------------------------
# WATERPOINT OPPORTUNITY RANKING
# ---------------------------------------------------

st.subheader("Top waterpoints by opportunity score")

wp_rank = df.sort_values(
"opportunity_score",
ascending=False
)

display_wp = wp_rank[[
"state",
"lga",
"ward",
"waterpoint_type",
"status",
"households_300m_est",
"opportunity_score",
"latitude",
"longitude"
]].copy()

display_wp = display_wp.rename(columns={
"households_300m_est":"Households within 300m",
"latitude":"Latitude",
"longitude":"Longitude",
"opportunity_score":"Opportunity Score (HH × mortality risk)"
})

st.dataframe(display_wp.head(200), width="stretch")

# ---------------------------------------------------
# MAP
# ---------------------------------------------------

st.subheader("Waterpoint map")

map_df = df.dropna(subset=["latitude","longitude"])

map_df["color_r"] = map_df["eligible"].apply(lambda x:0 if x else 220)
map_df["color_g"] = map_df["eligible"].apply(lambda x:170 if x else 50)
map_df["color_b"] = 60

layer = pdk.Layer(
"ScatterplotLayer",
data=map_df,
get_position="[longitude, latitude]",
get_fill_color="[color_r,color_g,color_b]",
get_radius=120,
pickable=True
)

view = pdk.ViewState(
latitude=float(map_df["latitude"].mean()),
longitude=float(map_df["longitude"].mean()),
zoom=6
)

tooltip = {
"html":"""
<b>State:</b> {state}<br>
<b>LGA:</b> {lga}<br>
<b>Ward:</b> {ward}<br>
<b>Type:</b> {waterpoint_type}<br>
<b>Status:</b> {status}<br>
<b>Eligible:</b> {eligible}<br>
<b>Households within 300m:</b> {households_300m_est}<br>
<b>Latitude:</b> {latitude}<br>
<b>Longitude:</b> {longitude}<br>
<b>Opportunity score:</b> {opportunity_score}
"""
}

st.pydeck_chart(
pdk.Deck(
layers=[layer],
initial_view_state=view,
tooltip=tooltip
)
)

# ---------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------

st.subheader("Download filtered dataset")

export_df = df[[
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
]]

csv = export_df.to_csv(index=False).encode("utf-8")

st.download_button(
"Download waterpoints for field verification",
csv,
"nigeria_waterpoints_field_verification.csv",
"text/csv"
)