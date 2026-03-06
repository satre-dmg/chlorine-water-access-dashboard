import streamlit as st
import pandas as pd

st.title("Nigeria Water Access Explorer")

df = pd.read_excel("nigeria_water_access_analysis.xlsx", sheet_name="waterpoints")

state = st.selectbox("State", ["All"] + sorted(df["state"].dropna().unique()))

if state != "All":
    df = df[df["state"] == state]

min_pop = st.slider("Minimum assigned population", 0, 5000, 0)

df = df[df["assigned_population"] >= min_pop]

st.dataframe(df)

st.map(df[["latitude","longitude"]])