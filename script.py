"""Déneigement Verdun avec OR-Tools — CARP simplifié, 3 scénarios."""

import math
import osmnx as ox
import networkx as nx
import folium
from collections import Counter
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# ── Paramètres ────────────────────────────────────────────────
SECTOR     = "Verdun, Montréal, Québec, Canada"
DEPOT      = (45.4617, -73.5722)
SPEED_KMH  = 10.0
MAX_TRUCKS = 6
TIME_LIMIT = 5
COST_FIXED = 500.0
COST_KM    = 1.1
COST_H1    = 1.1
COST_H2    = 1.3
BETA       = 1000.0
BIG        = 10**9
COLORS     = ["red", "blue", "green", "purple", "orange", "darkred"]

# ── POI ───────────────────────────────────────────────────────
POI_SANTE = [
    (45.4639, -73.5638),   # Hôpital de Verdun
    (45.4583, -73.5694),   # GMF-U LaSalle
    (45.4601, -73.5722),   # GMF-U de l'Église
]
POI_POLICE   = [(45.4656, -73.5683)]
POI_POMPIERS = [(45.4678, -73.5681), (45.4617, -73.5722)]
POI_METRO    = [(45.4594, -73.5717), (45.4708, -73.5664), (45.4558, -73.5753)]
POI_ECOLES   = [
    (45.4633, -73.5756), (45.4611, -73.5700), (45.4694, -73.5675),
    (45.4636, -73.5719), (45.4650, -73.5736), (45.4583, -73.5756),
    (45.4700, -73.5680), (45.4680, -73.5672),
]

BUS_STREETS = {"wellington", "de verdun", "lasalle", "bannantyne",
               "de l'église", "gaëtan-laberge", "champlain"}

POI_LAYERS = [
    ("Hôpitaux / Santé", POI_SANTE,    "red",    "plus-square"),
    ("Police",           POI_POLICE,   "blue",   "shield"),
    ("Pompiers",         POI_POMPIERS, "orange", "fire"),
    ("Métro",            POI_METRO,    "green",  "subway"),
    ("Écoles",           POI_ECOLES,   "purple", "graduation-cap"),
]

PRIORITY_COLORS = {1: "#d62728", 2: "#ff7f0e", 3: "#2ca02c"}
PRIORITY_LABELS = {1: "Priorité 1 (urgent)", 2: "Priorité 2 (secondaire)", 3: "Priorité 3 (local)"}

_MAJOR = {"motorway","trunk","primary","primary_link","motorway_link","trunk_link"}
_SECONDARY = {"secondary","secondary_link","tertiary","tertiary_link"}


# ── Utilitaires ───────────────────────────────────────────────
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


# ── Scénarios ─────────────────────────────────────────────────
def scenario_A(G):
    def prio(data):
        hw = highway(data)
        if hw in _MAJOR: return 1
        if hw in _SECONDARY: return 2
        return 3
    return make_jobs(G, prio)

def scenario_B(G):
    metro = poi_nodes(G, POI_METRO, 200)
    def prio(data):
        if name_matches(data, BUS_STREETS) or data.get("_u") in metro: return 1
        if highway(data) in _MAJOR | _SECONDARY: return 2
        return 3
    # on ne peut pas accéder à u/v dans la closure proprement, on refait à la main
    jobs, seen = [], set()
    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get("length", 0)
        if length <= 0: continue
        key = tuple(sorted((u, v)))
        if key in seen: continue
        seen.add(key)
        near = u in metro or v in metro
        on_bus = name_matches(data, BUS_STREETS)
        if on_bus or near: p = 1
        elif highway(data) in _MAJOR | _SECONDARY: p = 2
        else: p = 3
        jobs.append((u, v, k, length, p))
    jobs.sort(key=lambda x: x[4])
    return jobs

def scenario_C(G):
    essential = poi_nodes(G, POI_SANTE + POI_POLICE + POI_POMPIERS + POI_ECOLES)
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
        elif hw in _SECONDARY or name_matches(data, BUS_STREETS): p = 2
        else: p = 3
        jobs.append((u, v, k, length, p))
    jobs.sort(key=lambda x: x[4])
    return jobs


# ── Distances & coûts ─────────────────────────────────────────
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
        "k":         len(routes),
        "km":        sum(r["km"]    for r in routes),
        "cost":      sum(r["cost"]  for r in routes),
        "hours":     max(r["hours"] for r in routes),
        "objective": sum(r["cost"]  for r in routes) + BETA * max(r["hours"] for r in routes),
    }


# ── OR-Tools ──────────────────────────────────────────────────
def solve_vrp(jobs, depot, dist, nb_trucks):
    n = len(jobs) + 1
    matrix = [[0]*n for _ in range(n)]
    for i in range(n):
        src = depot if i == 0 else jobs[i-1][1]
        for j in range(n):
            if i == j: continue
            dst, svc = (depot, 0) if j == 0 else (jobs[j-1][0], jobs[j-1][3])
            matrix[i][j] = dist_m(dist, src, dst) + int(svc)

    manager = pywrapcp.RoutingIndexManager(n, nb_trucks, 0)
    routing = pywrapcp.RoutingModel(manager)

    cb_idx = routing.RegisterTransitCallback(
        lambda fi, ti: matrix[manager.IndexToNode(fi)][manager.IndexToNode(ti)])
    routing.SetArcCostEvaluatorOfAllVehicles(cb_idx)
    routing.AddDimension(cb_idx, 0, BIG, True, "Distance")
    routing.GetDimensionOrDie("Distance").SetGlobalSpanCostCoefficient(100)

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
        while not routing.IsEnd(idx):
            nxt = sol.Value(routing.NextVar(idx))
            i, j = manager.IndexToNode(idx), manager.IndexToNode(nxt)
            meters += matrix[i][j]
            if j != 0:
                route_jobs.append(jobs[j-1])
            idx = nxt
        km = meters / 1000
        routes.append({"id": v, "jobs": route_jobs, "km": km,
                       "hours": km / SPEED_KMH, "cost": truck_cost(km)})
    return routes


# ── Carte ─────────────────────────────────────────────────────
def edge_points(G, job):
    u, v, k = job[0], job[1], job[2]
    data = G[u][v][k]
    if "geometry" in data:
        return [(lat, lon) for lon, lat in data["geometry"].coords]
    return [(G.nodes[u]["y"], G.nodes[u]["x"]), (G.nodes[v]["y"], G.nodes[v]["x"])]

def draw_map(G, routes, stats, name):
    m = folium.Map(location=DEPOT, zoom_start=14, tiles="CartoDB positron")

    for r in routes:
        tip = f"Déneigeuse {r['id']+1} — {r['km']:.1f} km | {r['hours']:.2f} h | {r['cost']:.0f} $"
        for job in r["jobs"]:
            folium.PolyLine(edge_points(G, job),
                color=PRIORITY_COLORS.get(job[4] if len(job) > 4 else 0, "gray"),
                weight=3, opacity=0.85, tooltip=tip).add_to(m)

    if name in ("B", "C"):
        for layer_name, poi_list, color, icon in POI_LAYERS:
            fg = folium.FeatureGroup(name=layer_name)
            for lat, lon in poi_list:
                folium.Marker([lat, lon], tooltip=layer_name,
                    icon=folium.Icon(color=color, icon=icon, prefix="fa")).add_to(fg)
            fg.add_to(m)
        folium.LayerControl().add_to(m)

    folium.Marker(DEPOT, tooltip="Dépôt",
        icon=folium.Icon(color="black", icon="home", prefix="fa")).add_to(m)

    legend_p = "".join(
        f'<span style="color:{c};font-weight:bold">■</span> {PRIORITY_LABELS[p]}<br>'
        for p, c in PRIORITY_COLORS.items())
    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:fixed;bottom:25px;left:25px;z-index:9999;background:white;
    padding:10px;border-radius:8px;box-shadow:0 2px 8px #999;font-size:13px">
    <b>Verdun – Scénario {name}</b><br>
    Déneigeuses : {stats['k']}<br>Coût : {stats['cost']:.0f} $<br>
    Distance : {stats['km']:.1f} km<br>Durée max : {stats['hours']:.2f} h<br><br>
    {legend_p}</div>"""))

    out = f"carp_solution_{name}.html"
    m.save(out)
    print(f"  Carte : {out}")


# ── Résolution ────────────────────────────────────────────────
def run_scenario(G, GU, scenario_fn, name):
    print(f"\n{'='*50}\n  SCÉNARIO {name}\n{'='*50}")
    depot = ox.distance.nearest_nodes(G, X=DEPOT[1], Y=DEPOT[0])
    jobs  = scenario_fn(G)

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
    draw_map(G, best_routes, best_stats, name)
    best_stats["counts"] = counts
    return best_stats


# ── Main ──────────────────────────────────────────────────────
def main():
    ox.settings.use_cache = True
    print("Téléchargement OSM...")
    G  = ox.graph_from_place(SECTOR, network_type="drive", simplify=True, retain_all=False)
    GU = G.to_undirected()

    all_stats = {}
    for fn, name in [(scenario_A, "A"), (scenario_B, "B"), (scenario_C, "C")]:
        all_stats[name] = run_scenario(G, GU, fn, name)

    print(f"\n{'='*65}\n  COMPARAISON\n{'='*65}")
    print(f"  {'Scén':<6} | {'P1':>4} | {'P2':>4} | {'P3':>4} | {'Coût ($)':>9} | {'h max':>6} | {'km':>7}")
    print("  " + "-"*55)
    for name, s in all_stats.items():
        c = s["counts"]
        print(f"  {name:<6} | {c.get(1,0):>4} | {c.get(2,0):>4} | {c.get(3,0):>4} | "
              f"{s['cost']:>9.0f} | {s['hours']:>6.2f} | {s['km']:>7.1f}")

if __name__ == "__main__":
    main()
