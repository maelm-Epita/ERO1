import osmnx as ox
import folium

G = ox.graph_from_place("Verdun, Montréal, Canada", network_type="drive")
print(G)

m = folium.Map(location=[45.75, -73.85], zoom_start=12)

folium.PolyLine(
    [(45.75, 4.85)],  # liste [(lat, lon), ...]
    color="blue",
    weight=4
).add_to(m)

m.save("carp_solution.html")
