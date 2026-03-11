import streamlit as st

st.title("Methodology and Eligibility Criteria")

st.markdown("""
This page explains how the Nigeria Waterpoint Identification Tool defines
waterpoint eligibility and calculates opportunity scores.

The tool is intended for **planning and geographic prioritization** only.
Field verification is required before installation decisions are made.
""")

st.header("Waterpoint eligibility criteria")

st.markdown("""
A waterpoint is considered **eligible** in the planning tool if:

• Technology = **Hand Pump**  
• Status = **Functional** or **Functional, not in use**

These conditions reflect common implementation approaches used in
chlorine dispenser programs.
""")

st.header("Waterpoint status definitions")

st.markdown("""
**Functional — Eligible**  
Pump works and is used by the community.

**Functional, not in use — Eligible**  
Pump works but is temporarily unused. Infrastructure is still viable.

**Functional, needs repair — Not eligible**  
Pump works but requires maintenance.

**Non-functional — Not eligible**  
Pump is broken and cannot supply water.

**Non-functional, dry season — Not eligible**  
Pump runs dry seasonally.

**Abandoned / decommissioned — Not eligible**  
Infrastructure permanently removed from service.
""")

st.header("Sources informing eligibility approach")

st.markdown("""
Evidence Action – Dispensers for Safe Water  
https://www.evidenceaction.org/programs/safe-water/dispensers-for-safe-water/

Innovations for Poverty Action – Chlorine dispenser trials  
https://poverty-action.org/chlorine-dispensers-safe-water

Kremer et al. – Rural water chlorination research  
https://www.nber.org/papers/w15280
""")