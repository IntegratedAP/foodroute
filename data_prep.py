"""
============================================================
FOODROUTE — DATA PREPARATION SCRIPT
============================================================
Run this ONCE (and again only if you change AOI_NAME) to download
everything the dashboard needs and save it to disk:

  - Markets / food shops          -> markets.geojson
  - Restaurants / cafes / etc.    -> restaurants.geojson
  - Drivable road network         -> roads_drive.graphml
  - Walkable road network         -> roads_walk.graphml

USAGE (from Anaconda Prompt / Command Prompt, inside this project
folder):

    python data_prep.py

This can take a few minutes depending on your internet connection.
Do NOT close the window until you see "ALL DATA READY".
============================================================
"""

import warnings
from pathlib import Path

import osmnx as ox

warnings.filterwarnings("ignore")

# ============================================================
# 1. SETTINGS
# ============================================================
# Change this if you want to map a different area. Keep the format
# "Neighbourhood/LGA, State, Country" for best OpenStreetMap results.

AOI_NAME = "Ibadan North, Oyo State, Nigeria"

# This makes the script always save data next to itself, no matter
# which folder you run it from.
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "foodroute_dashboard_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("FOODROUTE — DATA PREPARATION")
print("=" * 60)
print(f"Area of interest : {AOI_NAME}")
print(f"Saving data to   : {DATA_DIR}")
print("=" * 60)


def to_points(gdf):
    """Convert polygons to centroid points using a proper metric CRS,
    then convert back to lat/lon (EPSG:4326)."""
    if gdf is None or gdf.empty:
        return gdf
    gdf = gdf.copy()
    projected = gdf.to_crs(gdf.estimate_utm_crs())
    gdf["geometry"] = projected.geometry.centroid.to_crs(gdf.crs)
    return gdf


# ============================================================
# 2. MARKETS / FOOD SHOPS
# ============================================================

print("\n[1/4] Downloading markets & food shops...")

tags_markets = {
    "shop": ["marketplace", "supermarket", "grocery", "convenience"],
    "amenity": ["marketplace"],
}

markets = ox.features_from_place(AOI_NAME, tags_markets)
markets = markets[
    markets.geometry.type.isin(["Point", "Polygon", "MultiPolygon"])
].copy()
markets = to_points(markets)
markets = markets[markets.geometry.notna()].copy()
markets = markets.reset_index(drop=True)

markets.to_file(DATA_DIR / "markets.geojson", driver="GeoJSON")
print(f"    -> {len(markets)} markets/food shops saved.")

# ============================================================
# 3. RESTAURANTS / CAFES / FAST FOOD
# ============================================================

print("\n[2/4] Downloading restaurants & eateries...")

tags_restaurants = {
    "amenity": ["restaurant", "fast_food", "cafe", "food_court", "pub", "bar"]
}

restaurants = ox.features_from_place(AOI_NAME, tags_restaurants)
restaurants = restaurants[
    restaurants.geometry.type.isin(["Point", "Polygon", "MultiPolygon"])
].copy()
restaurants = to_points(restaurants)
restaurants = restaurants[restaurants.geometry.notna()].copy()
restaurants = restaurants.reset_index(drop=True)

restaurants.to_file(DATA_DIR / "restaurants.geojson", driver="GeoJSON")
print(f"    -> {len(restaurants)} restaurants/eateries saved.")

# ============================================================
# 4. DRIVABLE ROAD NETWORK
# ============================================================

print("\n[3/4] Downloading drivable road network (for 🚗 Drive mode)...")

G_drive = ox.graph_from_place(AOI_NAME, network_type="drive")
ox.save_graphml(G_drive, filepath=DATA_DIR / "roads_drive.graphml")
print(f"    -> {len(G_drive.nodes):,} nodes, {len(G_drive.edges):,} edges saved.")

# ============================================================
# 5. WALKABLE ROAD NETWORK
# ============================================================

print("\n[4/4] Downloading walkable road network (for 🚶 Walk mode)...")

G_walk = ox.graph_from_place(AOI_NAME, network_type="walk")
ox.save_graphml(G_walk, filepath=DATA_DIR / "roads_walk.graphml")
print(f"    -> {len(G_walk.nodes):,} nodes, {len(G_walk.edges):,} edges saved.")

print("\n" + "=" * 60)
print("✅ ALL DATA READY.")
print("Next step: run   streamlit run app.py")
print("=" * 60)
