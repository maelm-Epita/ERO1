import math
import osmnx as ox
import networkx as nx
import folium
from collections import Counter
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# Données
DISTRICTS = {
    "Verdun": {
        "sector": "Verdun, Montréal, Québec, Canada",
        "depot":  (45.4617, -73.5722),
        "poi_sante":    [
            (45.4639, -73.5638), (45.4583, -73.5694), (45.4601, -73.5722),
        ],
        "poi_police":   [(45.4656, -73.5683)],
        "poi_pompiers": [(45.4678, -73.5681), (45.4617, -73.5722)],
        "poi_metro":    [(45.4594, -73.5717), (45.4708, -73.5664), (45.4558, -73.5753)],
        "poi_ecoles":   [
            (45.4633, -73.5756), (45.4611, -73.5700),
            (45.4694, -73.5675), (45.4636, -73.5719),
            (45.4650, -73.5736), (45.4583, -73.5756),
            (45.4700, -73.5680), (45.4680, -73.5672),
        ],
        "bus_streets": {"wellington", "de verdun", "lasalle", "bannantyne",
                        "de l'église", "gaëtan-laberge", "champlain"},
    },

    "Outremont": {
        "sector": "Outremont, Montréal, Québec, Canada",
        "depot":  (45.5177, -73.6093),
        "poi_sante":    [
            (45.5080, -73.6155), (45.5195, -73.6050),
        ],
        "poi_police":   [(45.5143, -73.6083)],
        "poi_pompiers": [(45.5160, -73.6100)],
        "poi_metro":    [
            (45.5156, -73.6158), (45.5225, -73.6083), (45.5102, -73.6142),
        ],
        "poi_ecoles":   [
            (45.5165, -73.6125), (45.5190, -73.6070),
            (45.5130, -73.6090), (45.5210, -73.6110),
            (45.5148, -73.6060), (45.5175, -73.6145),
        ],
        "bus_streets": {"van horne", "bernard", "laurier", "côte-sainte-catherine",
                        "acadie", "outremont", "maplewood"},
    },

    "Anjou": {
        "sector": "Anjou, Montréal, Québec, Canada",
        "depot":  (45.6050, -73.5600),
        "poi_sante":    [
            (45.6010, -73.5540), (45.6080, -73.5620),
        ],
        "poi_police":   [(45.6040, -73.5570)],
        "poi_pompiers": [(45.6065, -73.5580)],
        "poi_metro":    [
            (45.5958, -73.5528), (45.5992, -73.5463),
        ],
        "poi_ecoles":   [
            (45.6020, -73.5610), (45.6055, -73.5545),
            (45.6085, -73.5595), (45.6015, -73.5560),
            (45.6070, -73.5615), (45.6035, -73.5580),
        ],
        "bus_streets": {"jean-talon", "métropolitaine", "anjou", "des roseraies",
                        "beaubien", "galeries d'anjou", "pierre-de-coubertin"},
    },

    "RDP-PAT": {
        "sector": "Rivière-des-Prairies-Pointe-aux-Trembles, Montréal, Québec, Canada",
        "depot":  (45.6620, -73.5290),
        "poi_sante":    [
            (45.6230, -73.5027), (45.6600, -73.5120),
        ],
        "poi_police":   [
            (45.6650, -73.5200), (45.6400, -73.5000),
        ],
        "poi_pompiers": [
            (45.6640, -73.5240), (45.6370, -73.4910),
        ],
        "poi_metro":    [
        ],
        "poi_ecoles":   [
            (45.6580, -73.5310), (45.6650, -73.5180),
            (45.6440, -73.5060), (45.6500, -73.5150),
            (45.6390, -73.4970), (45.6620, -73.5260),
            (45.6350, -73.4930), (45.6680, -73.5200),
        ],
        "bus_streets": {"sherbrooke", "notre-dame", "de la rousselière",
                        "perras", "rodolphe-forget", "pointe-aux-trembles",
                        "rivière-des-prairies"},
    },
}

# Paramètres Globaux
SPEED_KMH  = 10.0
SPEED_MS   = SPEED_KMH / 3.6
MAX_TRUCKS = 6
TIME_LIMIT = 5
COST_FIXED = 500.0
COST_KM    = 1.1
COST_H1    = 1.1
COST_H2    = 1.3
BETA       = 500
BIG        = 10**9

PRIORITY_LABELS = {1: "Priorité 1 (urgent)", 2: "Priorité 2 (secondaire)", 3: "Priorité 3 (local)"}
TRUCK_COLORS = ["#e6194B", "#4363d8", "#3cb44b", "#f58231", "#911eb4", "#46f0f0"]

_MAJOR = {"motorway","trunk","primary","primary_link","motorway_link","trunk_link"}
_SECONDARY = {"secondary","secondary_link","tertiary","tertiary_link"}

# Utilitaires
def poi_nodes(G, poi_list, radius_m=150):
    nodes = set()
    for lat, lon in poi_list:
        nodes.add(ox.distance.nearest_nodes(G, X=lon, Y=lat))
        for n, d in G.nodes(data=True):
            dy = (d["y"] - lat) * 111_000
            dx = (d["x"] - lon) * 111_000 * math.cos(math.radians(lat))
            if math.hypot(dx, dy) <= radius_m:
                nodes.add(n)
    return nodes

def highway(data):
    hw = data.get("highway", "unclassified")
    return hw[0] if isinstance(hw, list) else hw

def name_matches(data, keywords):
    name = data.get("name", "") or ""
    if isinstance(name, list):
        name = " ".join(str(n) for n in name)
    return any(kw in name.lower() for kw in keywords)

def make_jobs(G, priority_fn):
    jobs, seen = [], set()
    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get("length", 0)
        if length <= 0:
            continue
        key = tuple(sorted((u, v)))
        if key in seen:
            continue
        seen.add(key)
        jobs.append((u, v, k, length, priority_fn(data)))
    jobs.sort(key=lambda x: x[4])
    return jobs

# Scénarios
def scenario_A(G, district_data):
    def prio(data):
        hw = highway(data)
        if hw in _MAJOR: return 1
        if hw in _SECONDARY: return 2
        return 3
    return make_jobs(G, prio)

def scenario_B(G, district_data):
    metro = poi_nodes(G, district_data["poi_metro"], 200)
    bus_streets = district_data["bus_streets"]
    
    jobs, seen = [], set()
    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get("length", 0)
        if length <= 0: continue
        key = tuple(sorted((u, v)))
        if key in seen: continue
        seen.add(key)
        
        near = u in metro or v in metro
        on_bus = name_matches(data, bus_streets)
        
        if on_bus or near: p = 1
        elif highway(data) in _MAJOR | _SECONDARY: p = 2
        else: p = 3
        jobs.append((u, v, k, length, p))
        
    jobs.sort(key=lambda x: x[4])
    return jobs

def scenario_C(G, district_data):
    all_essential_poi = (district_data["poi_sante"] + 
                         district_data["poi_police"] + 
                         district_data["poi_pompiers"] + 
                         district_data["poi_ecoles"])
                         
    essential = poi_nodes(G, all_essential_poi)
    bus_streets = district_data["bus_streets"]
    
    jobs, seen = [], set()
    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get("length", 0)
        if length <= 0: continue
        key = tuple(sorted((u, v)))
        if key in seen: continue
        seen.add(key)
        
        near = u in essential or v in essential
        hw = highway(data)
        
        if hw in _MAJOR or near: p = 1
        elif hw in _SECONDARY or name_matches(data, bus_streets): p = 2
        else: p = 3
        jobs.append((u, v, k, length, p))
        
    jobs.sort(key=lambda x: x[4])
    return jobs

# Distances & coûts
def precompute_distances(GU, jobs, depot):
    nodes = {depot} | {u for u,v,*_ in jobs} | {v for u,v,*_ in jobs}
    return {n: nx.single_source_dijkstra_path_length(GU, n, weight="length") for n in nodes}

def dist_m(dist, a, b):
    return int(dist.get(a, {}).get(b, BIG))

def truck_cost(km):
    h = km / SPEED_KMH
    return COST_FIXED + COST_KM * km + COST_H1 * min(h, 8) + COST_H2 * max(h - 8, 0)

def solution_stats(routes):
    return {
        "k":       len(routes),
        "km":       sum(r["km"]    for r in routes),
        "cost":      sum(r["cost"]  for r in routes),
        "hours":     max(r["hours"] for r in routes),
        "objective": sum(r["cost"]  for r in routes) + BETA * max(r["hours"] for r in routes),
    }

# OR-Tools
def solve_vrp(jobs, depot, dist, nb_trucks):
    n = len(jobs) + 1
    matrix_dist = [[0]*n for _ in range(n)]
    matrix_time = [[0]*n for _ in range(n)]
    
    for i in range(n):
        src = depot if i == 0 else jobs[i-1][1]
        for j in range(n):
            if i == j: continue
            dst, svc = (depot, 0) if j == 0 else (jobs[j-1][0], jobs[j-1][3])
            
            dist_meters = dist_m(dist, src, dst) + int(svc)
            matrix_dist[i][j] = dist_meters
            matrix_time[i][j] = int(dist_meters / SPEED_MS)

    manager = pywrapcp.RoutingIndexManager(n, nb_trucks, 0)
    routing = pywrapcp.RoutingModel(manager)

    dist_cb = routing.RegisterTransitCallback(
        lambda fi, ti: matrix_dist[manager.IndexToNode(fi)][manager.IndexToNode(ti)])
    routing.SetArcCostEvaluatorOfAllVehicles(dist_cb)
    routing.AddDimension(dist_cb, 0, BIG, True, "Distance")
    routing.GetDimensionOrDie("Distance").SetGlobalSpanCostCoefficient(100)

    time_cb = routing.RegisterTransitCallback(
        lambda fi, ti: matrix_time[manager.IndexToNode(fi)][manager.IndexToNode(ti)])
    routing.AddDimension(time_cb, 0, 86400, True, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    
    for j in range(1, n):
        idx = manager.NodeToIndex(j)
        prio = jobs[j-1][4]
        weight = {1: 15, 2: 3, 3: 0}.get(prio, 0)
        if weight > 0:
            time_dim.SetCumulVarSoftUpperBound(idx, 0, weight)

    cnt_idx = routing.RegisterTransitCallback(
        lambda fi, ti: 0 if manager.IndexToNode(ti) == 0 else 1)
    routing.AddDimension(cnt_idx, 0, len(jobs), True, "Count")
    cnt_dim = routing.GetDimensionOrDie("Count")
    for v in range(nb_trucks):
        routing.solver().Add(cnt_dim.CumulVar(routing.End(v)) >= 1)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = TIME_LIMIT

    sol = routing.SolveWithParameters(params)
    if sol is None:
        return None

    routes = []
    for v in range(nb_trucks):
        idx, route_jobs, meters = routing.Start(v), [], 0
        step = 1
        while not routing.IsEnd(idx):
            nxt = sol.Value(routing.NextVar(idx))
            i, j = manager.IndexToNode(idx), manager.IndexToNode(nxt)
            meters += matrix_dist[i][j]
            if j != 0:
                route_jobs.append(jobs[j-1] + (step,))
                step += 1
            idx = nxt
        km = meters / 1000
        routes.append({"id": v, "jobs": route_jobs, "km": km,
                       "hours": km / SPEED_KMH, "cost": truck_cost(km)})
    return routes

# Carte
def edge_points(G, job):
    u, v, k = job[0], job[1], job[2]
    data = G[u][v][k]
    if "geometry" in data:
        return [(lat, lon) for lon, lat in data["geometry"].coords]
    return [(G.nodes[u]["y"], G.nodes[u]["x"]), (G.nodes[v]["y"], G.nodes[v]["x"])]

def draw_map(G, routes, stats, name, district_name, district_data):
    depot = district_data["depot"]
    m = folium.Map(location=depot, zoom_start=14, tiles="CartoDB positron")

    legend_trucks = ""

    for r in routes:
        color = TRUCK_COLORS[r['id'] % len(TRUCK_COLORS)]
        legend_trucks += f'<span style="color:{color};font-weight:bold">━</span> Camion {r["id"]+1} ({r["km"]:.1f} km)<br>'
        
        for job in r["jobs"]:
            prio = job[4]
            step = job[5]
            tip = f"<b>Camion {r['id']+1}</b><br>Étape n°{step}<br>{PRIORITY_LABELS.get(prio, 'Inconnu')}"
            
            folium.PolyLine(edge_points(G, job),
                color=color,
                weight=4, opacity=0.85, tooltip=tip).add_to(m)

    if name in ("B", "C"):
        poi_layers = [
            ("Hôpitaux / Santé", district_data["poi_sante"],    "red",    "plus-square"),
            ("Police",           district_data["poi_police"],   "blue",   "shield"),
            ("Pompiers",         district_data["poi_pompiers"], "orange", "fire"),
            ("Métro",            district_data["poi_metro"],    "green",  "subway"),
            ("Écoles",           district_data["poi_ecoles"],   "purple", "graduation-cap"),
        ]
        for layer_name, poi_list, color, icon in poi_layers:
            fg = folium.FeatureGroup(name=layer_name)
            for lat, lon in poi_list:
                folium.Marker([lat, lon], tooltip=layer_name,
                    icon=folium.Icon(color=color, icon=icon, prefix="fa")).add_to(fg)
            fg.add_to(m)
        folium.LayerControl().add_to(m)

    folium.Marker(depot, tooltip="Dépôt",
        icon=folium.Icon(color="black", icon="home", prefix="fa")).add_to(m)
        
    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:fixed;bottom:25px;left:25px;z-index:9999;background:white;
    padding:10px;border-radius:8px;box-shadow:0 2px 8px #999;font-size:13px">
    <b>{district_name} – Scénario {name}</b><br>
    Déneigeuses : {stats['k']}<br>Coût : {stats['cost']:.0f} $<br>
    Distance : {stats['km']:.1f} km<br>Durée max : {stats['hours']:.2f} h<br>
    <hr style="margin:5px 0;">
    {legend_trucks}
    </div>"""))

    out = f"{district_name}_{name}.html"
    m.save(out)
    print(f"  Carte : {out}")

# Résolution
def run_scenario(G, GU, scenario_fn, name, district_name, district_data):
    print(f"\n{'='*50}\n  SCÉNARIO {name} ({district_name})\n{'='*50}")
    
    depot_coords = district_data["depot"]
    depot = ox.distance.nearest_nodes(G, X=depot_coords[1], Y=depot_coords[0])
    jobs  = scenario_fn(G, district_data)

    counts = Counter(j[4] for j in jobs)
    for p in sorted(counts):
        print(f"  Priorité {p} : {counts[p]} rues")
    print(f"  Total : {len(jobs)} rues")

    dist = precompute_distances(GU, jobs, depot)

    print(f"\n  {'k':>2} | {'coût':>8} | {'h max':>6} | {'km':>7} | {'obj':>8}")
    print("  " + "-"*41)

    best_routes, best_stats = None, None
    for k in range(1, min(MAX_TRUCKS, len(jobs)) + 1):
        routes = solve_vrp(jobs, depot, dist, k)
        if routes is None:
            print(f"  {k:>2} | impossible")
            continue
        s = solution_stats(routes)
        print(f"  {k:>2} | {s['cost']:>8.0f} | {s['hours']:>6.2f} | {s['km']:>7.1f} | {s['objective']:>8.0f}")
        if best_stats is None or s["objective"] < best_stats["objective"]:
            best_routes, best_stats = routes, s

    print(f"  Meilleur : {best_stats['k']} déneigeuse(s)")
    draw_map(G, best_routes, best_stats, name, district_name, district_data)
    best_stats["counts"] = counts
    return best_stats

# Main
def main():
    ox.settings.use_cache = True
    
    print("\n--- MENU DÉNEIGEMENT ---")
    districts_list = list(DISTRICTS.keys())
    for i, district in enumerate(districts_list, 1):
        print(f"{i}. {district}")
    print(f"{len(districts_list) + 1}. Tous les quartiers")
    
    choix = input(f"Sélectionnez le quartier à traiter (1-{len(districts_list) + 1}) : ")
    
    try:
        choix_idx = int(choix) - 1
        if choix_idx == len(districts_list):
            selected_districts = districts_list
        else:
            selected_districts = [districts_list[choix_idx]]
    except (ValueError, IndexError):
        print("Choix invalide. Fermeture du programme.")
        return

    for district_name in selected_districts:
        district_data = DISTRICTS[district_name]
        print(f"\n\n{'#'*65}\n# TRAITEMENT DE : {district_name.upper()}\n{'#'*65}")
        
        print(f"Téléchargement OSM pour {district_name}...")
        G  = ox.graph_from_place(district_data["sector"], network_type="drive", simplify=True, retain_all=False)
        GU = G.to_undirected()

        all_stats = {}
        for fn, name in [(scenario_A, "A"), (scenario_B, "B"), (scenario_C, "C")]:
            all_stats[name] = run_scenario(G, GU, fn, name, district_name, district_data)

        print(f"\n{'='*65}\n  COMPARAISON POUR {district_name.upper()}\n{'='*65}")
        print(f"  {'Scén':<6} | {'P1':>4} | {'P2':>4} | {'P3':>4} | {'Coût ($)':>9} | {'h max':>6} | {'km':>7}")
        print("  " + "-"*55)
        for name, s in all_stats.items():
            c = s["counts"]
            print(f"  {name:<6} | {c.get(1,0):>4} | {c.get(2,0):>4} | {c.get(3,0):>4} | "
                  f"{s['cost']:>9.0f} | {s['hours']:>6.2f} | {s['km']:>7.1f}")

if __name__ == "__main__":
    main()