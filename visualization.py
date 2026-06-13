import json
import math
import os
import folium
from config import TRUCK_COLORS, PRIO_LABEL
from graph_tools import edge_points

def add_pois(m, d):
    specs = [('poi_sante', 'red', 'plus', 'Santé'), ('poi_police', 'blue', 'shield', 'Police'), ('poi_pompiers', 'orange', 'fire', 'Pompiers'), ('poi_metro', 'green', 'train', 'Métro'), ('poi_ecoles', 'purple', 'graduation-cap', 'Écoles')]
    for key, color, icon, label in specs:
        fg = folium.FeatureGroup(label, show=True)
        for lat, lon in d.get(key, []):
            folium.Marker((lat, lon), tooltip=label, icon=folium.Icon(color=color, icon=icon, prefix='fa')).add_to(fg)
        fg.add_to(m)

def add_model_layer(m, G, jobs):
    fg = folium.FeatureGroup('Modèle — toutes les rues à déneiger', show=False)
    for j in jobs:
        folium.PolyLine(edge_points(G, j.u, j.v, j.k), color='#999', weight=1, opacity=0.30, tooltip=f'{PRIO_LABEL[j.priority]} | {j.name}').add_to(fg)
    fg.add_to(m)

def approx_meters(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    x = (lon2 - lon1) * 111000 * math.cos(math.radians((lat1 + lat2) / 2))
    y = (lat2 - lat1) * 111000
    return math.hypot(x, y)

def sample_polyline(points, step_m=55):
    if not points: return []
    if len(points) == 1: return [points[0]]
    out = [points[0]]
    for a, b in zip(points[:-1], points[1:]):
        d = approx_meters(a, b)
        if d <= 0: continue
        n = max(1, int(d // step_m))
        for i in range(1, n + 1):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out

def route_animation_segments(G, route, step_m=35):
    chunks = []
    for seg in route.segments:
        edge = edge_points(G, seg.u, seg.v, seg.k)
        sampled = sample_polyline(edge, step_m=step_m)
        if len(sampled) < 2: continue
        pts = [[round(p[0], 7), round(p[1], 7)] for p in sampled]
        chunks.append({'points': pts, 'is_service': bool(seg.is_service), 'priority': int(seg.priority or 0), 'kind': seg.kind})
    return chunks

def draw_animation_map(G, routes, st, jobs, district, scenario, d):
    m = folium.Map(location=d['depot'], zoom_start=13, tiles='cartodbpositron')
    add_pois(m, d)
    add_model_layer(m, G, jobs)
    fg_final = folium.FeatureGroup('Tracé utile final — fond pâle', show=True)
    fg_repeat = folium.FeatureGroup('Répétitions / retours', show=False)
    
    for r in routes:
        color = TRUCK_COLORS[r.truck_id % len(TRUCK_COLORS)]
        for seg in r.segments:
            pts = edge_points(G, seg.u, seg.v, seg.k)
            if seg.is_service:
                folium.PolyLine(pts, color=color, weight=3, opacity=0.25, tooltip=f"Dameuse {r.truck_id + 1} | {PRIO_LABEL.get(seg.priority, 'service')}").add_to(fg_final)
            else:
                folium.PolyLine(pts, color='#666666', weight=2, opacity=0.18, dash_array='6,8', tooltip=f'Dameuse {r.truck_id + 1} | répétition / retour').add_to(fg_repeat)
                
    fg_final.add_to(m)
    fg_repeat.add_to(m)
    folium.Marker(d['depot'], tooltip='Dépôt', icon=folium.Icon(color='black', icon='home', prefix='fa')).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    
    chunks_json = []
    lengths_km = []
    for r in routes:
        chunks = route_animation_segments(G, r, step_m=28)
        if not chunks:
            chunks = [{'points': [[d['depot'][0], d['depot'][1]], [d['depot'][0], d['depot'][1]]], 'is_service': False, 'priority': 0, 'kind': 'idle'}]
        chunks_json.append(chunks)
        lengths_km.append(round(r.meters_total / 1000, 1))
        
    map_name = m.get_name()
    colors = TRUCK_COLORS[:len(routes)]
    coverage_color = 'green' if st['covered_jobs'] == st['total_jobs'] else 'red'
    legend = ''.join((f'<span style="color:{TRUCK_COLORS[i % len(TRUCK_COLORS)]};font-weight:bold">●</span> Dameuse {i + 1} — {lengths_km[i]} km<br>' for i in range(len(routes))))
    
    panel = f"""
    <div id="animPanel" style="position:fixed;bottom:25px;left:25px;z-index:9999;background:white;padding:12px;border-radius:8px;box-shadow:0 2px 8px #999;font-size:13px;max-width:500px">
      <b>{district} — scénario {scenario}</b><br>
      <b>Animation des déneigeuses</b><br>
      Déneigeuses retenues : <b>{st['k']}</b><br>
      Coût : {st['cost']:.0f} $ — durée max : {st['hours']:.2f} h<br>
      Distance totale : {st['km']:.1f} km, utile : {st['service_km']:.1f} km, répété : {st['repeat_km']:.1f} km ({100 * st['repeat_rate']:.1f} %)<br>
      Couverture : <span style="color:{coverage_color};font-weight:bold">{st['covered_jobs']} / {st['total_jobs']}</span><br>
      <hr style="margin:6px 0;">
      <button id="animPlay">▶ Lecture</button>
      <button id="animPause">⏸ Pause</button>
      <button id="animReset">↺ Recommencer</button>
      <label style="margin-left:8px;">Vitesse</label>
      <select id="animSpeed">
        <option value="0.05">très lent</option>
        <option value="0.12" selected>lent</option>
        <option value="0.30">normal</option>
        <option value="0.70">rapide</option>
      </select><br>
      <input id="animRange" type="range" min="0" max="1000" value="0" style="width:100%;margin-top:8px;">
      <div id="animTime" style="font-size:12px;margin-top:4px;">Progression : 0 %</div>
      <hr style="margin:6px 0;">{legend}
    </div>
    """
    m.get_root().html.add_child(folium.Element(panel))
    
    output_dir = os.path.join("results", district)
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{district}_{scenario}_Animation.html")

    m.save(filename)
    return filename