import geopandas as gpd
import pandas as pd
import rasterio

print("Loading waterpoints Excel")

waterpoints = pd.read_excel("nigeria_waterpoints_analysis.xlsx", sheet_name="waterpoints")

waterpoints = gpd.GeoDataFrame(
    waterpoints,
    geometry=gpd.points_from_xy(waterpoints.longitude, waterpoints.latitude),
    crs="EPSG:4326"
)

print("Loading settlement points")

settlements = gpd.read_file("Settlements_in_Nigeria/grid3_nga_settlementpt.shp")

print("Loading population raster")

raster = rasterio.open("nga_pop_2020_CN_100m_R2025A_v1.tif")

print("Sampling population for settlements")

pop_vals = []

for point in settlements.geometry:
    try:
        for val in raster.sample([(point.x, point.y)]):
            pop_vals.append(val[0])
    except:
        pop_vals.append(None)

settlements["pop_cell"] = pop_vals
settlements["population_est"] = settlements["pop_cell"] * 9

print("Converting to projected CRS")

settlements = settlements.to_crs(3857)
waterpoints = waterpoints.to_crs(3857)

print("Creating settlement buffers (500m)")

settlements["buffer"] = settlements.geometry.buffer(500)

buffers = settlements.set_geometry("buffer")

print("Finding waterpoints near settlements")

join = gpd.sjoin(waterpoints, buffers, how="left", predicate="within")

counts = join.groupby("index_right").size()

settlements["waterpoints_nearby"] = settlements.index.map(counts).fillna(0)

print("Population per waterpoint")

settlements["population_per_waterpoint"] = (
    settlements["population_est"] /
    settlements["waterpoints_nearby"].replace(0, pd.NA)
)

print("Preparing settlement output")

settlements_output = settlements[
    [
        "statename",
        "lganame",
        "wardname",
        "set_name",
        "population_est",
        "waterpoints_nearby",
        "population_per_waterpoint"
    ]
]

settlements_output.columns = [
    "state",
    "lga",
    "ward",
    "settlement",
    "population_est",
    "waterpoints_nearby",
    "population_per_waterpoint"
]

print("Ward level aggregation")

ward_summary = settlements_output.groupby(
    ["state","lga","ward"]
).agg(
    settlements=("settlement","count"),
    population_est=("population_est","sum"),
    waterpoints_nearby=("waterpoints_nearby","sum")
).reset_index()

ward_summary["population_per_waterpoint"] = (
    ward_summary["population_est"] /
    ward_summary["waterpoints_nearby"].replace(0,pd.NA)
)

print("Legend")

legend = pd.DataFrame({
"column":[
"state","lga","ward","settlement",
"population_est","waterpoints_nearby",
"population_per_waterpoint"
],
"description":[
"State name",
"Local Government Area",
"Ward name",
"Settlement name",
"Estimated settlement population",
"Waterpoints within 500m",
"Estimated population per waterpoint"
]
})

print("Saving Excel")

with pd.ExcelWriter("nigeria_water_access_analysis.xlsx") as writer:

    waterpoints.to_excel(writer,sheet_name="waterpoints",index=False)

    settlements_output.to_excel(writer,sheet_name="settlements",index=False)

    ward_summary.to_excel(writer,sheet_name="ward_summary",index=False)

    legend.to_excel(writer,sheet_name="legend",index=False)

print("Done.")