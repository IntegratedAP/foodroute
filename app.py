"""
============================================================
FOODROUTE
OSM-powered Food Access & Mobility Dashboard
============================================================
Run with:   streamlit run app.py
(Run data_prep.py once BEFORE this, to download the data.)
============================================================
"""

import warnings
from pathlib import Path

import streamlit as st
import pandas as pd
import geopandas as gpd
import networkx as nx
import osmnx as ox
import folium
from folium.plugins import MarkerCluster, AntPath
from geopy.distance import geodesic
from streamlit_folium import st_folium
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="FoodRoute",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# PROJECT PATHS  (relative to this file — works in any folder)
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "foodroute_dashboard_data"

MARKETS_FILE = DATA_DIR / "markets.geojson"
RESTAURANTS_FILE = DATA_DIR / "restaurants.geojson"
ROADS_DRIVE_FILE = DATA_DIR / "roads_drive.graphml"
ROADS_WALK_FILE = DATA_DIR / "roads_walk.graphml"

APP_TITLE = "🍲 FoodRoute"
SUBTITLE = "An OpenStreetMap-powered food-access and mobility dashboard for Ibadan North, Oyo State."

DEFAULT_LAT = 7.3986
DEFAULT_LON = 3.9003

SPEED_KMH = {"🚗 Drive": 28, "🚶 Walk": 4.8}

# ============================================================
# CUSTOM CSS — beautiful theme
# ============================================================

st.markdown(
    """
    <style>
    .stApp { background-color: #f6f8f6; }

    .hero {
        background: linear-gradient(120deg, #1b5e20 0%, #2e7d32 45%, #66bb6a 100%);
        padding: 34px 36px;
        border-radius: 18px;
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 8px 24px rgba(27, 94, 32, 0.25);
    }
    .hero h1 { font-size: 40px; font-weight: 800; margin: 0 0 6px 0; }
    .hero p { font-size: 16px; opacity: 0.95; margin: 0; }

    .card {
        background: white;
        padding: 20px 22px;
        border-radius: 14px;
        border: 1px solid #e3e8e3;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        margin-bottom: 16px;
    }

    .score-number { font-size: 54px; font-weight: 800; color: #1b5e20; line-height: 1; }
    .score-label { font-size: 20px; font-weight: 600; color: #333; margin-top: 4px; }
    .small-label { color: #777; font-size: 13px; letter-spacing: 0.5px; text-transform: uppercase; }

    .badge-green { background:#e6f4ea; color:#1b5e20; padding:4px 12px; border-radius:20px; font-weight:600; font-size:13px; }
    .badge-orange { background:#fff3e0; color:#e65100; padding:4px 12px; border-radius:20px; font-weight:600; font-size:13px; }
    .badge-red { background:#fdecea; color:#c62828; padding:4px 12px; border-radius:20px; font-weight:600; font-size:13px; }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e3e8e3;
        border-radius: 12px;
        padding: 10px 14px;
    }

    .stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: 600; padding: 10px 16px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# HEADER
# ============================================================

st.markdown(
    f"""
    <div class="hero">
        <h1>{APP_TITLE}</h1>
        <p>{SUBTITLE}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# DATA LOADERS
# ============================================================

@st.cache_data
def load_points(path):
    if not path.exists():
        return gpd.GeoDataFrame()
    gdf = gpd.read_file(path)
    if gdf.empty:
        return gdf
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf.to_crs("EPSG:4326")
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: g.centroid if (g is not None and g.geom_type != "Point") else g
    )
    return gdf


@st.cache_resource
def load_graph(path):
    if not path.exists():
        return None
    try:
        return ox.load_graphml(path)
    except Exception as e:
        st.error(f"Could not load road network: {e}")
        return None


data_missing = not (MARKETS_FILE.exists() and ROADS_DRIVE_FILE.exists())

if data_missing:
    st.error(
        "⚠️ No data found yet. Please run **`python data_prep.py`** in this "
        "project folder first, then restart the dashboard with "
        "**`streamlit run app.py`**. See the setup steps you were given."
    )
    st.stop()

markets = load_points(MARKETS_FILE)
restaurants = load_points(RESTAURANTS_FILE)
G_drive = load_graph(ROADS_DRIVE_FILE)
G_walk = load_graph(ROADS_WALK_FILE) if ROADS_WALK_FILE.exists() else None

# ============================================================
# HELPERS
# ============================================================

def get_name(row, fallback="Unnamed location"):
    try:
        name = row.get("name")
        if isinstance(name, str) and name.strip():
            return name
        return fallback
    except Exception:
        return fallback


def straight_distance_km(lat1, lon1, lat2, lon2):
    return geodesic((lat1, lon1), (lat2, lon2)).km


def resolve_graph(mode):
    if mode == "🚶 Walk" and G_walk is not None:
        return G_walk
    return G_drive


def estimate_minutes(distance_km, mode):
    speed = SPEED_KMH.get(mode, 28)
    if speed <= 0:
        return None
    return (distance_km / speed) * 60.0


def route_to_location(lat, lon, dest_lat, dest_lon, graph):
    if graph is None:
        return None
    try:
        origin_node = ox.distance.nearest_nodes(graph, lon, lat)
        dest_node = ox.distance.nearest_nodes(graph, dest_lon, dest_lat)
        route = nx.shortest_path(graph, origin_node, dest_node, weight="length")
        if len(route) < 2:
            return None

        total_length = 0.0
        for u, v in zip(route[:-1], route[1:]):
            edge_data = graph.get_edge_data(u, v)
            if edge_data is None:
                continue
            data = edge_data[0] if 0 in edge_data else next(iter(edge_data.values()))
            total_length += float(data.get("length", 0))

        coordinates = [
            (graph.nodes[n]["y"], graph.nodes[n]["x"]) for n in route
        ]

        return {
            "route_coordinates": coordinates,
            "distance_m": total_length,
            "distance_km": total_length / 1000.0,
        }
    except Exception:
        return None


def nearest_location_straight(lat, lon, locations):
    if locations is None or locations.empty:
        return None
    best = None
    for idx, row in locations.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        d = straight_distance_km(lat, lon, geom.y, geom.x)
        if best is None or d < best["distance_km"]:
            best = {
                "index": idx, "name": get_name(row),
                "lat": float(geom.y), "lon": float(geom.x),
                "distance_km": d,
            }
    return best


def nearest_by_road(lat, lon, locations, graph, max_candidates=15):
    if locations is None or locations.empty or graph is None:
        return None

    candidates = []
    for idx, row in locations.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        d = straight_distance_km(lat, lon, geom.y, geom.x)
        candidates.append((d, idx, row))
    candidates.sort(key=lambda x: x[0])
    candidates = candidates[:max_candidates]

    best = None
    for _, idx, row in candidates:
        geom = row.geometry
        result = route_to_location(lat, lon, geom.y, geom.x, graph)
        if result is None:
            continue
        item = {
            "index": idx, "name": get_name(row),
            "lat": float(geom.y), "lon": float(geom.x),
            "distance_km": result["distance_km"],
            "distance_m": result["distance_m"],
            "route_coordinates": result["route_coordinates"],
        }
        if best is None or item["distance_km"] < best["distance_km"]:
            best = item
    return best


def get_food_locations(category):
    if category == "Market":
        return markets
    if category == "Restaurant":
        return restaurants
    frames = []
    if markets is not None and not markets.empty:
        m = markets.copy(); m["food_type"] = "Market"; frames.append(m)
    if restaurants is not None and not restaurants.empty:
        r = restaurants.copy(); r["food_type"] = "Restaurant"; frames.append(r)
    if frames:
        return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    return gpd.GeoDataFrame()


def calculate_food_access_score(market_result, restaurant_result):
    score = 100
    if market_result is None:
        score -= 40
    else:
        d = market_result["distance_km"]
        if d > 5: score -= 40
        elif d > 3: score -= 25
        elif d > 2: score -= 15
        elif d > 1: score -= 5

    if restaurant_result is None:
        score -= 20
    else:
        d = restaurant_result["distance_km"]
        if d > 5: score -= 20
        elif d > 3: score -= 12
        elif d > 2: score -= 8
        elif d > 1: score -= 3

    return max(0, min(100, score))


def score_label(score):
    if score >= 80: return "Good food access"
    if score >= 60: return "Moderate food access"
    if score >= 40: return "Limited food access"
    return "Poor food access"


def score_badge_class(score):
    if score >= 60: return "badge-green"
    if score >= 40: return "badge-orange"
    return "badge-red"


def generate_explanation(score, label, market_result, restaurant_result):
    parts = [f"{label}."]
    distances = [r["distance_km"] for r in (market_result, restaurant_result) if r]

    if distances:
        avg = sum(distances) / len(distances)
        parts.append(
            f"Most mapped food facilities near this location are within "
            f"approximately {avg:.1f} km along the available road network."
        )
    else:
        parts.append(
            "No mapped food facility could be reached from this location "
            "on the available road network."
        )

    if market_result is None or market_result["distance_km"] > 3:
        parts.append(
            "However, market access is limited here — the nearest mapped "
            "market is more than 3 km away by road, or none was found."
        )
    if restaurant_result is None or restaurant_result["distance_km"] > 3:
        parts.append("Restaurant access is also limited in this area.")

    if score < 40:
        parts.append(
            "This is a physical-proximity indicator only — it does not "
            "capture prices, transport cost, or affordability."
        )
    return " ".join(parts)


def interpret_query(question):
    q = question.lower().strip()
    restaurant_words = ["restaurant", "eat", "eating", "meal", "lunch", "dinner", "breakfast", "cafe", "fast food"]
    market_words = ["market", "buy food", "buy", "grocery", "supermarket", "shopping", "shop"]
    walk_words = ["walk", "walking", "on foot", "trek"]
    drive_words = ["drive", "driving", "car", "vehicle"]
    score_words = ["score", "food access", "accessibility", "how accessible", "food security"]

    if any(w in q for w in score_words):
        intent = "score"
    elif any(w in q for w in restaurant_words):
        intent = "restaurant"
    elif any(w in q for w in market_words):
        intent = "market"
    else:
        intent = "general"

    if any(w in q for w in walk_words):
        mode = "🚶 Walk"
    elif any(w in q for w in drive_words):
        mode = "🚗 Drive"
    else:
        mode = None

    category = {"restaurant": "Restaurant", "market": "Market"}.get(intent, "All food locations")
    return {"intent": intent, "category": category, "mode": mode}


# ============================================================
# MAP BUILDER
# ============================================================

def create_map(lat, lon, locations, selected_result=None, cluster=True):
    m = folium.Map(location=[lat, lon], zoom_start=13, control_scale=True, tiles="CartoDB positron")

    folium.Marker(
        [lat, lon], popup="📍 Your location", tooltip="Your location",
        icon=folium.Icon(color="blue", icon="home", prefix="fa"),
    ).add_to(m)

    folium.Circle(
        [lat, lon], radius=50, color="#1976d2", fill=True, fill_opacity=0.15
    ).add_to(m)

    if locations is not None and not locations.empty:
        layer = MarkerCluster(name="Food locations").add_to(m) if cluster else m
        for _, row in locations.iterrows():
            geom = row.geometry
            if geom is None:
                continue
            name = get_name(row, "Food location")
            food_type = row.get("food_type", "Food")
            color, icon = ("red", "cutlery") if food_type == "Restaurant" else ("green", "shopping-cart")
            folium.Marker(
                [geom.y, geom.x],
                popup=f"<b>{name}</b><br>{food_type}",
                tooltip=name,
                icon=folium.Icon(color=color, icon=icon, prefix="fa"),
            ).add_to(layer)

    if selected_result is not None:
        folium.Marker(
            [selected_result["lat"], selected_result["lon"]],
            popup=f"<b>Destination</b><br>{selected_result['name']}",
            tooltip="Selected destination",
            icon=folium.Icon(color="purple", icon="flag", prefix="fa"),
        ).add_to(m)

        if selected_result.get("route_coordinates"):
            AntPath(
                selected_result["route_coordinates"],
                weight=6, opacity=0.9, color="#d32f2f",
                delay=800,
                tooltip=f"Route: {selected_result['distance_km']:.2f} km",
            ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


# ============================================================
# SESSION STATE
# ============================================================

if "user_lat" not in st.session_state:
    st.session_state.user_lat = DEFAULT_LAT
if "user_lon" not in st.session_state:
    st.session_state.user_lon = DEFAULT_LON

# Apply any pending map-click location BEFORE the number_input widgets
# below are created. Streamlit does not allow changing a widget's bound
# session_state value after that widget has already been drawn in the
# same run, so a click on the map only stores a "pending" value, which
# gets applied here on the next run, before the widgets exist.
if st.session_state.get("pending_lat") is not None:
    st.session_state.user_lat = st.session_state.pending_lat
    st.session_state.user_lon = st.session_state.pending_lon
    st.session_state.pending_lat = None
    st.session_state.pending_lon = None
if "selected_result" not in st.session_state:
    st.session_state.selected_result = None
if "selected_category" not in st.session_state:
    st.session_state.selected_category = "Market"
if "question" not in st.session_state:
    st.session_state.question = ""

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("📍 Your location")
st.sidebar.caption("Type coordinates, or click the map in the '🗺️ Map & Route' tab and press 'Use this point'.")

lat = st.sidebar.number_input("Latitude", key="user_lat", format="%.6f")
lon = st.sidebar.number_input("Longitude", key="user_lon", format="%.6f")

st.sidebar.markdown("---")
st.sidebar.header("🚦 Travel mode")
mode = st.sidebar.radio("How are you travelling?", ["🚗 Drive", "🚶 Walk"], horizontal=True)

st.sidebar.markdown("---")
st.sidebar.header("🍴 Find food")
category = st.sidebar.selectbox("Facility type", ["Market", "Restaurant", "All food locations"])

find_button = st.sidebar.button("🔎 Find nearest facility", use_container_width=True, type="primary")

st.sidebar.markdown("---")
st.sidebar.metric("🥬 Markets mapped", len(markets) if markets is not None else 0)
st.sidebar.metric("🍽️ Restaurants mapped", len(restaurants) if restaurants is not None else 0)
st.sidebar.caption("Study area: Ibadan North, Oyo State, Nigeria")
st.sidebar.caption("Data © OpenStreetMap contributors")

graph = resolve_graph(mode)

if find_button:
    with st.spinner("Calculating the nearest facility by road..."):
        locs = get_food_locations(category)
        result = nearest_by_road(lat, lon, locs, graph)
        st.session_state.selected_result = result
        st.session_state.selected_category = category

# ============================================================
# TABS
# ============================================================

tab_map, tab_search, tab_ai, tab_score, tab_scenario, tab_about = st.tabs(
    ["🗺️ Map & Route", "🔎 Search", "🤖 Ask FoodRoute", "📊 Food Access Score", "🚧 Road Scenario", "ℹ️ About"]
)

# ------------------------------------------------------------
# TAB — MAP & ROUTE
# ------------------------------------------------------------
with tab_map:
    st.markdown("#### Explore food locations and route to the nearest one")
    st.caption("Click anywhere on the map to drop a pin, then click 'Use this point' to set it as your location.")

    c1, c2, c3 = st.columns(3)
    c1.metric("🥬 Markets", len(markets))
    c2.metric("🍽️ Restaurants", len(restaurants))
    c3.metric("🛣️ Road nodes", f"{len(graph.nodes):,}" if graph is not None else "N/A")

    selected = st.session_state.selected_result

    if selected is not None:
        st.markdown(
            f"""
            <div class="card">
            <span class="small-label">Nearest {st.session_state.selected_category.lower()}</span>
            <h3 style="margin:4px 0;">{selected['name']}</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Road distance", f"{selected['distance_km']:.2f} km")
        est_min = estimate_minutes(selected["distance_km"], mode)
        m2.metric("Estimated time", f"{est_min:.0f} min ({mode})" if est_min else "N/A")
        m3.metric("Coordinates", f"{selected['lat']:.4f}, {selected['lon']:.4f}")

    map_locations = get_food_locations(category)
    m = create_map(lat, lon, map_locations, selected)
    click_data = st_folium(m, width=None, height=580, returned_objects=["last_clicked"])

    if click_data and click_data.get("last_clicked"):
        clicked_lat = click_data["last_clicked"]["lat"]
        clicked_lon = click_data["last_clicked"]["lng"]
        st.info(f"Pin dropped at {clicked_lat:.5f}, {clicked_lon:.5f}")
        if st.button("📍 Use this point as my location"):
            st.session_state.pending_lat = clicked_lat
            st.session_state.pending_lon = clicked_lon
            st.session_state.selected_result = None
            st.rerun()

# ------------------------------------------------------------
# TAB — SEARCH
# ------------------------------------------------------------
with tab_search:
    st.markdown("#### Search markets and restaurants by name")

    sc1, sc2 = st.columns(2)

    with sc1:
        st.markdown("##### 🥬 Search markets")
        market_query = st.text_input("Market name contains...", key="market_search")
        if not markets.empty:
            m_view = markets.copy()
            m_view["name_display"] = m_view.apply(lambda r: get_name(r), axis=1)
            if market_query:
                m_view = m_view[m_view["name_display"].str.contains(market_query, case=False, na=False)]
            m_view["distance_km"] = m_view.geometry.apply(
                lambda g: straight_distance_km(lat, lon, g.y, g.x) if g is not None else None
            )
            m_view = m_view.sort_values("distance_km").head(15)
            st.dataframe(
                m_view[["name_display", "distance_km"]].rename(
                    columns={"name_display": "Name", "distance_km": "Straight-line km"}
                ),
                use_container_width=True, hide_index=True,
            )
            if not m_view.empty:
                pick = st.selectbox("Route to a market", m_view["name_display"].tolist(), key="market_pick")
                if st.button("🚗 Route to selected market"):
                    row = m_view[m_view["name_display"] == pick].iloc[0]
                    with st.spinner("Calculating route..."):
                        r = route_to_location(lat, lon, row.geometry.y, row.geometry.x, graph)
                    if r:
                        st.session_state.selected_result = {
                            "name": pick, "lat": row.geometry.y, "lon": row.geometry.x,
                            "distance_km": r["distance_km"], "route_coordinates": r["route_coordinates"],
                        }
                        st.session_state.selected_category = "Market"
                        st.success(f"Route found: {r['distance_km']:.2f} km. See the 'Map & Route' tab.")
                    else:
                        st.error("No road route could be calculated to this market.")
        else:
            st.warning("No market data found. Run data_prep.py first.")

    with sc2:
        st.markdown("##### 🍽️ Search restaurants")
        rest_query = st.text_input("Restaurant name contains...", key="rest_search")
        if not restaurants.empty:
            r_view = restaurants.copy()
            r_view["name_display"] = r_view.apply(lambda r: get_name(r), axis=1)
            if rest_query:
                r_view = r_view[r_view["name_display"].str.contains(rest_query, case=False, na=False)]
            r_view["distance_km"] = r_view.geometry.apply(
                lambda g: straight_distance_km(lat, lon, g.y, g.x) if g is not None else None
            )
            r_view = r_view.sort_values("distance_km").head(15)
            st.dataframe(
                r_view[["name_display", "distance_km"]].rename(
                    columns={"name_display": "Name", "distance_km": "Straight-line km"}
                ),
                use_container_width=True, hide_index=True,
            )
            if not r_view.empty:
                pick_r = st.selectbox("Route to a restaurant", r_view["name_display"].tolist(), key="rest_pick")
                if st.button("🚗 Route to selected restaurant"):
                    row = r_view[r_view["name_display"] == pick_r].iloc[0]
                    with st.spinner("Calculating route..."):
                        r = route_to_location(lat, lon, row.geometry.y, row.geometry.x, graph)
                    if r:
                        st.session_state.selected_result = {
                            "name": pick_r, "lat": row.geometry.y, "lon": row.geometry.x,
                            "distance_km": r["distance_km"], "route_coordinates": r["route_coordinates"],
                        }
                        st.session_state.selected_category = "Restaurant"
                        st.success(f"Route found: {r['distance_km']:.2f} km. See the 'Map & Route' tab.")
                    else:
                        st.error("No road route could be calculated to this restaurant.")
        else:
            st.warning("No restaurant data found. Run data_prep.py first.")

# ------------------------------------------------------------
# TAB — ASK FOODROUTE
# ------------------------------------------------------------
with tab_ai:
    st.markdown("#### Ask a food-access question in plain language")
    st.caption("Runs on a local rule-based engine — no external AI API or internet-based language model required.")

    question = st.text_input(
        "Your question", value=st.session_state.question,
        placeholder="e.g. What is the nearest market? / Where can I eat? / How is my food access score?",
    )
    ask = st.button("🔎 Ask FoodRoute", type="primary")

    if ask:
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            st.session_state.question = question
            interp = interpret_query(question)
            q_mode = interp["mode"] or mode
            q_graph = resolve_graph(q_mode)

            if interp["intent"] == "score":
                mr = nearest_by_road(lat, lon, markets, q_graph)
                rr = nearest_by_road(lat, lon, restaurants, q_graph)
                score = calculate_food_access_score(mr, rr)
                label = score_label(score)
                st.success(f"📊 Your food access score is **{score}/100** — {label}.")
                st.write(generate_explanation(score, label, mr, rr))
            else:
                locs = get_food_locations(interp["category"])
                with st.spinner("Analysing your question..."):
                    result = nearest_by_road(lat, lon, locs, q_graph)
                if result is None:
                    st.error("No suitable mapped location could be found on this road network.")
                else:
                    st.session_state.selected_result = result
                    st.session_state.selected_category = interp["category"] if interp["category"] != "All food locations" else "Market"
                    est_min = estimate_minutes(result["distance_km"], q_mode)
                    time_txt = f" (~{est_min:.0f} min by {q_mode.split(' ')[1].lower()})" if est_min else ""
                    st.success(
                        f"📍 The nearest mapped {interp['category'].lower()} is **{result['name']}**, "
                        f"approximately **{result['distance_km']:.2f} km by road**{time_txt}."
                    )
                    route_map = create_map(lat, lon, locs, result)
                    st_folium(route_map, width=None, height=560, returned_objects=[])

# ------------------------------------------------------------
# TAB — FOOD ACCESS SCORE
# ------------------------------------------------------------
with tab_score:
    st.markdown("#### Food access score for this location")
    st.caption("An experimental physical-proximity indicator — not an official food-security index.")

    with st.spinner("Calculating..."):
        market_result = nearest_by_road(lat, lon, markets, graph)
        restaurant_result = nearest_by_road(lat, lon, restaurants, graph)

    score = calculate_food_access_score(market_result, restaurant_result)
    label = score_label(score)
    badge_class = score_badge_class(score)

    left, right = st.columns([1, 1.3])

    with left:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=score,
                number={"suffix": " / 100", "font": {"size": 46}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#2e7d32"},
                    "steps": [
                        {"range": [0, 40], "color": "#fdecea"},
                        {"range": [40, 60], "color": "#fff3e0"},
                        {"range": [60, 80], "color": "#fff9c4"},
                        {"range": [80, 100], "color": "#e6f4ea"},
                    ],
                    "threshold": {"line": {"color": "#1b5e20", "width": 4}, "thickness": 0.8, "value": score},
                },
            )
        )
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(f'<span class="{badge_class}">{label}</span>', unsafe_allow_html=True)

    with right:
        st.markdown(f"""<div class="card">{generate_explanation(score, label, market_result, restaurant_result)}</div>""", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🥬 Nearest market**")
            if market_result:
                st.write(market_result["name"])
                st.metric("Road distance", f"{market_result['distance_km']:.2f} km")
            else:
                st.warning("No mapped market found within range.")
        with c2:
            st.markdown("**🍽️ Nearest restaurant**")
            if restaurant_result:
                st.write(restaurant_result["name"])
                st.metric("Road distance", f"{restaurant_result['distance_km']:.2f} km")
            else:
                st.warning("No mapped restaurant found within range.")

    st.markdown("---")
    st.markdown("##### What does this score mean?")
    st.write(
        "This indicator combines road-network distance from your chosen location to the nearest "
        "mapped market and restaurant. Shorter distances score higher. It does **not** measure "
        "food prices, income, availability, market capacity, nutrition, or affordability — those "
        "datasets could be layered in for a fuller food-security picture."
    )

# ------------------------------------------------------------
# TAB — ROAD SCENARIO
# ------------------------------------------------------------
with tab_scenario:
    st.markdown("#### What-if road blockage scenario (drive network)")
    st.caption("A manual simulation only — OpenStreetMap does not provide live traffic or closure data.")

    if G_drive is None:
        st.error("Drive network is unavailable.")
    else:
        st.write(f"Loaded drive network: **{len(G_drive.nodes):,} nodes**, **{len(G_drive.edges):,} edges**.")

        edge_options = []
        for i, (u, v, key, data) in enumerate(G_drive.edges(keys=True, data=True)):
            length = data.get("length", 0)
            if length is None:
                continue
            edge_options.append((u, v, key, float(length)))
            if len(edge_options) >= 3000:
                break

        if edge_options:
            labels = [f"Edge {i+1}: {length:.0f} m" for i, (_, _, _, length) in enumerate(edge_options)]
            sel_idx = st.selectbox("Road segment to block", range(len(edge_options)), format_func=lambda i: labels[i])
            u, v, key, orig_len = edge_options[sel_idx]

            if st.button("🚧 Simulate blockage"):
                with st.spinner("Recalculating route without this road..."):
                    G_temp = G_drive.copy()
                    if G_temp.has_edge(u, v, key):
                        G_temp.remove_edge(u, v, key)

                    before = nearest_by_road(lat, lon, markets, G_drive)
                    if before:
                        after = route_to_location(lat, lon, before["lat"], before["lon"], G_temp)
                        if after:
                            before_d = before["distance_km"]
                            after_d = after["distance_km"]
                            increase = after_d - before_d
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Original route", f"{before_d:.2f} km")
                            c2.metric("After blockage", f"{after_d:.2f} km")
                            c3.metric("Extra distance", f"{increase:.2f} km")
                            if increase > 0:
                                st.warning(f"This blockage adds ~{increase:.2f} km to the route to the nearest market.")
                            else:
                                st.info("This road segment did not affect the shortest route.")
                        else:
                            st.error("After the blockage, the market can no longer be reached on this network.")
                    else:
                        st.error("No nearest market could be found to test against.")
        else:
            st.warning("No road edges available.")

# ------------------------------------------------------------
# TAB — ABOUT
# ------------------------------------------------------------
with tab_about:
    st.markdown(
        """
        ### What is FoodRoute?
        FoodRoute maps food accessibility using OpenStreetMap road networks and mapped
        food facilities — markets, food shops, restaurants, and cafés.

        ### Data & tools
        OpenStreetMap · OSMnx · GeoPandas · NetworkX · Folium · Streamlit · Plotly

        ### Natural-language layer
        Questions are handled by a **local, rule-based** engine — no paid AI API is required.
        Try: *"What is the nearest market?"*, *"Where can I eat?"*, *"How is my food access score?"*

        ### Limitations
        - OpenStreetMap coverage varies by area — not every facility or road is mapped.
        - The road network reflects mapped roads, not live traffic.
        - The Road Scenario tab is a manual what-if test, not real-time data.
        - The Food Access Score is an experimental proximity indicator, not a formal
          food-security index — it excludes price, income, and affordability data.
        """
    )

st.markdown("---")
st.markdown(
    """
    <div style="text-align:center; color:#777; padding:16px;">
    <b>FoodRoute</b> · OSM-powered food accessibility dashboard<br>
    OpenStreetMap data © OpenStreetMap contributors
    </div>
    """,
    unsafe_allow_html=True,
)
