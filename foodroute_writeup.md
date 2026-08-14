# FoodRoute
### Real-time food access & routing for Ibadan North, Oyo State

---

## The Problem

In many Nigerian cities, including Ibadan, people don't actually know how far they are from real, physical food. Not "does a market exist somewhere in the city" — but "if I'm standing right here, right now, on foot or with the little fuel I have, how far do I actually have to travel, on the roads that actually exist."

That gap between *food exists somewhere in the city* and *food is reachable from where I am* is invisible until you're the one stuck in it. Nobody had mapped that gap for Ibadan before. FoodRoute tries to.

## Who It's For

- A resident of Ibadan North with no market close by, deciding whether walking is realistic or whether they need transport money.
- A local NGO or planner trying to identify which neighborhoods are food-insecure due to distance and road access — not just price.
- A new resident or student who doesn't know the area and needs to find the nearest place to eat, right now.
- Anyone using OpenStreetMap data for Ibadan, as a working example of what that data can do once it's turned into something usable.

## What Changes Because of This Project

Before FoodRoute, a map could show dots for markets and restaurants — but a dot doesn't tell you if you can get there, or how far it really is once you follow real streets instead of a straight line.

Now, someone can drop a pin on their exact location, choose walking or driving, and get a real road-following route with accurate distance and time. They can search a market or restaurant by name and route straight to it, or ask a plain question like *"where can I eat?"* and get a real, computed answer. And for the first time, they get a single number — a **Food Access Score** — that explains in plain language whether their location has good, moderate, or poor food access, and why.

## How OpenStreetMap Data Makes This Possible

Every core dataset comes directly from OpenStreetMap, pulled via the **Overpass API** through **OSMnx**:

- **Markets & food shops** — `shop=marketplace/supermarket/grocery/convenience`, `amenity=marketplace`
- **Restaurants & eateries** — `amenity=restaurant/fast_food/cafe/food_court/pub/bar`
- **Road network** — a full routable graph (drivable *and* walkable), built from OSM's street geometry and lengths

OSM isn't a basemap here — it's the computation layer. Every distance, every route line, and every number behind the Food Access Score is calculated by running shortest-path routing directly over OSM's road graph. Without OSM's road topology, this would be dots on a map with straight-line guesses. With it, FoodRoute can tell someone the real walking or driving distance along streets that genuinely exist and connect — and that distinction is the entire reason the project works.

## Key Features

| Feature | Description |
|---|---|
| 🗺️ Interactive routing | Click-to-pin location, animated real road routes |
| 🚗 / 🚶 Travel mode | Separate drive and walk networks, distance + time estimates |
| 🔎 Search | Find any market or restaurant by name, route to it directly |
| 🤖 Ask FoodRoute | Local, rule-based natural-language question answering |
| 📊 Food Access Score | 0–100 gauge with a plain-language explanation |
| 🚧 Road Scenario | Simulates a road closure and its impact on food access |

## Tools Used

**OpenStreetMap** · **Overpass API** · **OSMnx** · **NetworkX** · **GeoPandas** · **Shapely** · **Python** · **Streamlit** · **Folium** · **Plotly** · **GitHub** · **Streamlit Community Cloud**

---

*Live app & source code: [github.com/IntegratedAP/foodroute](https://github.com/IntegratedAP/foodroute)*
