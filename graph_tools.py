import math
import unicodedata
import networkx as nx
import osmnx as ox
from models import Job
from config import BIG, IGNORED, MAJOR, SECONDARY

def norm(s):
    if s is None:
        return ''
    if isinstance(s, list):
        s = ' '.join(map(str, s))
    s = str(s).lower().replace('-', ' ').replace("'", ' ')
    s = unicodedata.normalize('NFD', s)
    s = ''.join((ch for ch in s if unicodedata.category(ch) != 'Mn'))
    return ' '.join(s.split())

def highway(data):
    h = data.get('highway', 'unclassified')
    return str(h[0] if isinstance(h, list) and h else h)

def edge_name(data):
    n = data.get('name', '')
    return ' / '.join(map(str, n)) if isinstance(n, list) else str(n or 'rue sans nom')

def name_matches(data, words):
    n = norm(data.get('name', ''))
    return bool(n) and any((norm(w) in n for w in words))

def project(lat, lon, lat0, lon0):
    x = (lon - lon0) * 111000 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 111000
    return (x, y)

def midpoint(G, job):
    return ((G.nodes[job.u]['y'] + G.nodes[job.v]['y']) / 2, (G.nodes[job.u]['x'] + G.nodes[job.v]['x']) / 2)

def edge_points(G, u, v, k):
    if k is not None and G.has_edge(u, v, k):
        data = G[u][v][k]
        if 'geometry' in data:
            return [(lat, lon) for lon, lat in data['geometry'].coords]
    if G.has_edge(u, v):
        kk = min(G[u][v], key=lambda key: float(G[u][v][key].get('length', BIG) or BIG))
        data = G[u][v][kk]
        if 'geometry' in data:
            return [(lat, lon) for lon, lat in data['geometry'].coords]
    return [(G.nodes[u]['y'], G.nodes[u]['x']), (G.nodes[v]['y'], G.nodes[v]['x'])]

def min_edge_key_length(G, u, v):
    if not G.has_edge(u, v):
        return (None, BIG)
    kk = min(G[u][v], key=lambda key: float(G[u][v][key].get('length', BIG) or BIG))
    return (kk, float(G[u][v][kk].get('length', BIG) or BIG))

def _osmid_key(data):
    osmid = data.get('osmid', '')
    if isinstance(osmid, list):
        return tuple(osmid)
    return osmid

def service_key_for_data(G, u, v, k, data):
    hw = highway(data)
    name = norm(data.get('name', ''))
    osmid = _osmid_key(data)
    if G.has_edge(v, u):
        a, b = sorted((u, v))
        return ('physical', a, b, osmid, name, hw)
    return ('directed', u, v, k, osmid, name, hw)

def service_key_for_edge(G, u, v, k):
    return service_key_for_data(G, u, v, k, G[u][v][k])

def poi_nodes(G, pois, radius_m):
    out = set()
    nodes = list(G.nodes(data=True))
    for lat, lon in pois:
        try:
            out.add(ox.distance.nearest_nodes(G, X=lon, Y=lat))
        except Exception:
            pass
        for n, d in nodes:
            x, y = project(d['y'], d['x'], lat, lon)
            if math.hypot(x, y) <= radius_m:
                out.add(n)
    return out

def make_jobs(G, prio_func):
    tmp = {}
    for u, v, k, data in G.edges(keys=True, data=True):
        length = float(data.get('length', 0) or 0)
        hw = highway(data)
        if length <= 1 or hw in IGNORED:
            continue
        key = service_key_for_data(G, u, v, k, data)
        p = max(1, min(3, int(prio_func(u, v, k, data))))
        if key not in tmp:
            tmp[key] = {'u': u, 'v': v, 'k': k, 'length': length, 'priority': p, 'name': edge_name(data), 'highway': hw}
        else:
            tmp[key]['priority'] = min(tmp[key]['priority'], p)
            if 0 < length < tmp[key]['length']:
                tmp[key]['length'] = length
    jobs = []
    for uid, data in enumerate(tmp.values()):
        jobs.append(Job(uid, data['u'], data['v'], data['k'], data['length'], data['priority'], data['name'], data['highway']))
    return jobs

def scenario_A(G, d):
    axes = {'wellington', 'lasalle', 'la salle', 'sherbrooke', 'notre dame', 'jean talon', 'metropolitaine', 'métropolitaine', 'van horne', 'bernard', 'laurier'}
    def p(u, v, k, data):
        h = highway(data)
        if h in MAJOR or name_matches(data, axes):
            return 1
        return 2 if h in SECONDARY else 3
    return make_jobs(G, p)

def scenario_B(G, d):
    metro = poi_nodes(G, d.get('poi_metro', []), 220)
    bus = set(d.get('bus_streets', set()))
    def p(u, v, k, data):
        h = highway(data)
        if u in metro or v in metro or name_matches(data, bus):
            return 1
        return 2 if h in MAJOR or h in SECONDARY else 3
    return make_jobs(G, p)

def scenario_C(G, d):
    pois = []
    for key in ('poi_sante', 'poi_police', 'poi_pompiers', 'poi_ecoles'):
        pois += d.get(key, [])
    essential = poi_nodes(G, pois, 190)
    bus = set(d.get('bus_streets', set()))
    def p(u, v, k, data):
        h = highway(data)
        if u in essential or v in essential:
            return 1
        return 2 if h in MAJOR or h in SECONDARY or name_matches(data, bus) else 3
    return make_jobs(G, p)

def precompute_shortest_paths(G):
    lengths = {}
    paths = {}
    nodes = list(G.nodes())
    for i, n in enumerate(nodes, 1):
        if i % 100 == 0 or i == len(nodes):
            print(f'    plus courts chemins dirigés : {i}/{len(nodes)}')
        try:
            dist, path = nx.single_source_dijkstra(G, n, weight='length')
        except Exception:
            dist, path = ({}, {})
        lengths[n] = dist
        paths[n] = path
    return (lengths, paths)

def dist_to(lengths, a, b):
    return float(lengths.get(a, {}).get(b, BIG))

def path_to(paths, a, b):
    return paths.get(a, {}).get(b)