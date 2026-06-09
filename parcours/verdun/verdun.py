import osmnx as ox
import folium

sector = "Verdun, Montréal, Canada"
G = ox.graph_from_place(sector, network_type="drive")
print(G)

sector_lat, sector_lon = ox.geocode(sector)

map = folium.Map(location=[sector_lat, sector_lon], zoom_start=14)

l = []
for id, data in G.nodes(data=True):
    lat = data['y']
    lon = data['x']
    l.append((lat, lon))

folium.PolyLine(
    l,  # liste [(lat, lon), ...]
    color="blue",
    weight=4
).add_to(map)

map.save("carp_solution.html")
