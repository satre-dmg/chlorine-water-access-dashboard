import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="Nigeria Water Access Explorer", layout="wide")

st.title("Nigeria Water Access Explorer")
st.caption("Waterpoint screening and cascade planning tool for chlorine intervention targeting.")

# ----------------------------------------------------
# HOW TO USE SECTION
# ----------------------------------------------------
st.markdown("""
### How to use this tool

1. Select a **State → LGA → Ward** to focus on a geography.
2. Use filters to screen waterpoints by **population and eligibility**.
3. Toggle **Only Eligible Hand Pump Sites** to focus on likely chlorine dispenser locations.
4. Review **LGA and Ward rankings** to identify underserved areas.
5. Hover on map points to view details for each waterpoint.
6. Download filtered results if needed.

Green map points = **eligible sites**  
Red map points = **ineligible sites**
""")

# ----------------------------------------------------
# POPULATION METRICS EXPLANATION
# ----------------------------------------------------
with st.expander("Population indicators explained"):
    st.markdown("""
**Households (HHs)**  
Estimated number of households associated with the waterpoint catchment.

**Households within ~300 m**  
Estimated households within a 300 m radius of the waterpoint using high-resolution population grids (WorldPop).

This approximates the number of households **likely to collect water from the source**.

Chlorine dispenser programs typically prioritize waterpoints serving roughly:

• **50–150 households (~200–750 people)**

because larger shared sources increase cost-effectiveness and public health impact.

**References**

Evidence Action – Dispensers for Safe Water  
https://www.evidenceaction.org/programs/safe-water/dispensers-for-safe-water/

IPA chlorine dispenser research  
https://poverty-action.org/chlorine-dispensers-safe-water

Kremer et al. chlorine dispenser trials  
https://www.nber.org/papers/w15280
""")

# ----------------------------------------------------
# LOAD DATA
# ----------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_excel("nigeria_water_access_analysis.xlsx", sheet_name="waterpoints")

df = load_data().copy()

# ----------------------------------------------------
# CLEANUP
# ----------------------------------------------------
text_cols = ["state","lga","ward","water_tech","status","management"]
for c in text_cols:
    if c in df.columns:
        df[c] = df[c].fillna("MISSING").astype(str)

numeric_cols = [
"longitude","latitude",
"assigned_population","households_est",
"pop_300m_est","households_300m_est"
]

for c in numeric_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# ----------------------------------------------------
# WATERPOINT CLASSIFICATION
# ----------------------------------------------------
df["waterpoint_type"] = "Other"

df.loc[df["water_tech"].str.contains("Hand Pump",case=False,na=False),"waterpoint_type"]="Hand Pump"
df.loc[df["water_tech"].str.contains("Motorized",case=False,na=False),"waterpoint_type"]="Motorized Pump"
df.loc[df["water_tech"].str.contains("Tapstand",case=False,na=False),"waterpoint_type"]="Tapstand"

df["functional"] = (
df["status"].str.contains("Functional",case=False,na=False)
& ~df["status"].str.contains("Non-Functional",case=False,na=False)
)

df["eligible"] = (
(df["waterpoint_type"]=="Hand Pump") &
(df["functional"])
)

df["color_r"]=df["eligible"].apply(lambda x:0 if x else 220)
df["color_g"]=df["eligible"].apply(lambda x:170 if x else 50)
df["color_b"]=df["eligible"].apply(lambda x:60)

# ----------------------------------------------------
# SIDEBAR FILTERS
# ----------------------------------------------------
st.sidebar.header("Filters")

state = st.sidebar.selectbox("State",["All"]+sorted(df["state"].unique()))

filtered=df.copy()

if state!="All":
    filtered=filtered[filtered["state"]==state]

lga = st.sidebar.selectbox("LGA",["All"]+sorted(filtered["lga"].unique()))

if lga!="All":
    filtered=filtered[filtered["lga"]==lga]

ward = st.sidebar.selectbox("Ward",["All"]+sorted(filtered["ward"].unique()))

if ward!="All":
    filtered=filtered[filtered["ward"]==ward]

type_filter = st.sidebar.selectbox(
"Waterpoint Type",
["All"]+sorted(filtered["waterpoint_type"].unique())
)

if type_filter!="All":
    filtered=filtered[filtered["waterpoint_type"]==type_filter]

eligible_only = st.sidebar.checkbox("Only Eligible Hand Pump Sites")

if eligible_only:
    filtered=filtered[filtered["eligible"]]

# population filters
max_pop=int(filtered["assigned_population"].fillna(0).max())

min_pop=st.sidebar.slider(
"Minimum assigned population",
0,
max_pop if max_pop>0 else 1,
0
)

st.sidebar.write(f"Selected: **{min_pop}**")

filtered=filtered[filtered["assigned_population"].fillna(0)>=min_pop]

max_hh=int(filtered["households_300m_est"].fillna(0).max())

min_hh=st.sidebar.slider(
"Minimum households within 300m",
0,
max_hh if max_hh>0 else 1,
0
)

st.sidebar.write(f"Selected: **{min_hh}**")

filtered=filtered[filtered["households_300m_est"].fillna(0)>=min_hh]

# ----------------------------------------------------
# SUMMARY
# ----------------------------------------------------
c1,c2,c3,c4=st.columns(4)

c1.metric("Sites shown",len(filtered))
c2.metric("Eligible sites",filtered["eligible"].sum())
c3.metric("Assigned population",int(filtered["assigned_population"].fillna(0).sum()))
c4.metric("Households within 300m",int(filtered["households_300m_est"].fillna(0).sum()))

# ----------------------------------------------------
# POPULATION REACHED CALCULATOR
# ----------------------------------------------------
st.subheader("Population reached estimator")

dispensers=st.slider("Number of dispensers to install",1,200,20)

eligible_sites=filtered[filtered["eligible"]]

avg_households=eligible_sites["households_300m_est"].fillna(0).mean()

avg_people=avg_households*5

population_reached=int(dispensers*avg_people)

st.write(f"Average households near eligible sites: **{int(avg_households)}**")

st.write(f"Estimated people reached per dispenser: **{int(avg_people)}**")

st.success(f"Estimated population reached with {dispensers} dispensers: **{population_reached:,} people**")

# ----------------------------------------------------
# LGA RANKING
# ----------------------------------------------------
st.subheader("LGA ranking")

lga_rank=filtered.groupby(["state","lga"]).agg(
waterpoints=("waterpoint_type","count"),
eligible_sites=("eligible","sum"),
population=("assigned_population","sum"),
households=("households_300m_est","sum")
).reset_index()

lga_rank["population_per_waterpoint"]=lga_rank["population"]/lga_rank["waterpoints"]

lga_rank=lga_rank.sort_values("population_per_waterpoint",ascending=False)

st.dataframe(lga_rank,use_container_width=True)

# ----------------------------------------------------
# WARD RANKING
# ----------------------------------------------------
st.subheader("Ward ranking")

ward_rank=filtered.groupby(["state","lga","ward"]).agg(
waterpoints=("waterpoint_type","count"),
eligible_sites=("eligible","sum"),
population=("assigned_population","sum"),
households=("households_300m_est","sum")
).reset_index()

ward_rank["population_per_waterpoint"]=ward_rank["population"]/ward_rank["waterpoints"]

ward_rank=ward_rank.sort_values("population_per_waterpoint",ascending=False)

st.dataframe(ward_rank,use_container_width=True)

# ----------------------------------------------------
# MAP
# ----------------------------------------------------
st.subheader("Map")

map_df=filtered.dropna(subset=["latitude","longitude"])

tooltip={
"html":"""
<b>State:</b> {state}<br/>
<b>LGA:</b> {lga}<br/>
<b>Ward:</b> {ward}<br/>
<b>Type:</b> {waterpoint_type}<br/>
<b>Status:</b> {status}<br/>
<b>Eligible:</b> {eligible}<br/>
<b>Households 300m:</b> {households_300m_est}
"""
}

layer=pdk.Layer(
"ScatterplotLayer",
data=map_df,
get_position="[longitude,latitude]",
get_fill_color="[color_r,color_g,color_b]",
get_radius=120,
pickable=True
)

view=pdk.ViewState(
latitude=map_df["latitude"].mean(),
longitude=map_df["longitude"].mean(),
zoom=6
)

st.pydeck_chart(
pdk.Deck(
layers=[layer],
initial_view_state=view,
tooltip=tooltip
)
)

st.caption("Green = eligible hand pump sites | Red = ineligible sites")

# ----------------------------------------------------
# DOWNLOAD
# ----------------------------------------------------
csv=filtered.to_csv(index=False).encode("utf-8")

st.download_button(
"Download filtered dataset",
csv,
"filtered_waterpoints.csv",
" text/csv"
)