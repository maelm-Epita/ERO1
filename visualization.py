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
        folium.PolyLine(edge_points(G, j.u, j.v, j.k), color='#999', weight=1, opacity=0.3, tooltip=f'{PRIO_LABEL[j.priority]} | {j.name}').add_to(fg)
    fg.add_to(m)

def approx_meters(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    x = (lon2 - lon1) * 111000 * math.cos(math.radians((lat1 + lat2) / 2))
    y = (lat2 - lat1) * 111000
    return math.hypot(x, y)

def sample_polyline(points, step_m=55):
    if not points:
        return []
    if len(points) == 1:
        return [points[0]]
    out = [points[0]]
    for a, b in zip(points[:-1], points[1:]):
        d = approx_meters(a, b)
        if d <= 0:
            continue
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
        if len(sampled) < 2:
            continue
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
    
    panel = f"""\n    <div id="animPanel" style="position:fixed;bottom:25px;left:25px;z-index:9999;background:white;padding:12px;border-radius:8px;box-shadow:0 2px 8px #999;font-size:13px;max-width:500px">\n      <b>{district} — scénario {scenario}</b><br>\n      <b>Animation des déneigeuses</b><br>\n      Déneigeuses retenues : <b>{st['k']}</b><br>\n      Coût : {st['cost']:.0f} $ — durée max : {st['hours']:.2f} h<br>\n      Distance totale : {st['km']:.1f} km, utile : {st['service_km']:.1f} km, répété : {st['repeat_km']:.1f} km ({100 * st['repeat_rate']:.1f} %)<br>\n      Couverture : <span style="color:{coverage_color};font-weight:bold">{st['covered_jobs']} / {st['total_jobs']}</span><br>\n      <hr style="margin:6px 0;">\n      <button id="animPlay">▶ Lecture</button>\n      <button id="animPause">⏸ Pause</button>\n      <button id="animReset">↺ Recommencer</button>\n      <label style="margin-left:8px;">Vitesse</label>\n      <select id="animSpeed">\n        <option value="0.05">très lent</option>\n        <option value="0.12" selected>lent</option>\n        <option value="0.30">normal</option>\n        <option value="0.70">rapide</option>\n      </select><br>\n      <input id="animRange" type="range" min="0" max="1000" value="0" style="width:100%;margin-top:8px;">\n      <div id="animTime" style="font-size:12px;margin-top:4px;">Progression : 0 %</div>\n      <hr style="margin:6px 0;">{legend}\n      <small>Fond pâle = tracé final. Le chemin derrière chaque dameuse est plus fort. Une rue déjà coloriée garde sa première couleur.</small>\n    </div>\n    """
    m.get_root().html.add_child(folium.Element(panel))
    
    js = f"""\n    <script>\n    (function() {{\n      var mapName = {json.dumps(map_name)};\n      var truckChunks = {json.dumps(chunks_json)};\n      var colors = {json.dumps(colors)};\n      var TRAIL_POINTS = 18;\n\n      function chunkSignature(points) {{\n        if (!points || points.length < 2) return null;\n        var a = points[0], b = points[points.length - 1];\n        var sa = a[0].toFixed(6) + ',' + a[1].toFixed(6);\n        var sb = b[0].toFixed(6) + ',' + b[1].toFixed(6);\n        return sa < sb ? sa + '|' + sb : sb + '|' + sa;\n      }}\n\n      function pointCount(chunks) {{\n        var n = 0;\n        for (var i=0; i<chunks.length; i++) n += Math.max(1, chunks[i].points.length);\n        return Math.max(1, n);\n      }}\n\n      function firstPoint(chunks) {{\n        for (var i=0; i<chunks.length; i++) {{\n          if (chunks[i].points && chunks[i].points.length) return chunks[i].points[0];\n        }}\n        return [0, 0];\n      }}\n\n      function getState(chunks, wanted) {{\n        var seen = 0;\n        var last = firstPoint(chunks);\n        for (var i=0; i<chunks.length; i++) {{\n          var pts = chunks[i].points || [];\n          var n = Math.max(1, pts.length);\n          if (wanted > seen + n) {{\n            seen += n;\n            if (pts.length) last = pts[pts.length - 1];\n            continue;\n          }}\n          var idx = Math.max(1, Math.min(n, wanted - seen));\n          if (!pts.length) pts = [last, last];\n          last = pts[Math.min(pts.length - 1, idx - 1)];\n          var start = Math.max(0, idx - TRAIL_POINTS);\n          return {{\n            chunkIndex: i,\n            localIndex: idx,\n            last: last,\n            tail: pts.slice(start, Math.min(pts.length, idx)),\n            points: pts,\n            isService: !!chunks[i].is_service,\n            kind: chunks[i].kind || ''\n          }};\n        }}\n        var endChunk = chunks[chunks.length - 1] || {{points:[last,last], is_service:false, kind:''}};\n        var endPts = endChunk.points || [last,last];\n        return {{\n          chunkIndex: chunks.length - 1,\n          localIndex: endPts.length,\n          last: endPts[endPts.length - 1] || last,\n          tail: endPts.slice(Math.max(0, endPts.length - TRAIL_POINTS)),\n          points: endPts,\n          isService: !!endChunk.is_service,\n          kind: endChunk.kind || ''\n        }};\n      }}\n\n      window.addEventListener('load', function() {{\n        var map = window[mapName];\n        if (!map) return;\n\n        var range = document.getElementById('animRange');\n        var timeLabel = document.getElementById('animTime');\n        var playBtn = document.getElementById('animPlay');\n        var pauseBtn = document.getElementById('animPause');\n        var resetBtn = document.getElementById('animReset');\n        var speedSelect = document.getElementById('animSpeed');\n\n        var markers = [];\n        var tails = [];\n        var completedLayers = [];\n        var currentChunkLayers = [];\n        var lastCompletedIdx = [];\n        var totalPoints = [];\n        var claimed = {{}};\n\n        function addCompletedChunk(points, color, truckIdx) {{\n          var sig = chunkSignature(points);\n          if (!sig) return;\n          if (claimed[sig] !== undefined) return;\n          claimed[sig] = truckIdx;\n          var line = L.polyline(points, {{\n            color: color,\n            weight: 6,\n            opacity: 0.92\n          }}).addTo(map);\n          completedLayers[truckIdx].push(line);\n        }}\n\n        for (var i=0; i<truckChunks.length; i++) {{\n          totalPoints.push(pointCount(truckChunks[i]));\n          completedLayers.push([]);\n          lastCompletedIdx.push(-1);\n\n          var p0 = firstPoint(truckChunks[i]);\n          var marker = L.circleMarker(p0, {{\n            radius: 8,\n            color: colors[i % colors.length],\n            fillColor: colors[i % colors.length],\n            fillOpacity: 1,\n            weight: 3\n          }}).addTo(map);\n          marker.bindTooltip('Dameuse ' + (i+1), {{permanent:false}});\n          markers.push(marker);\n\n          var tail = L.polyline([], {{\n            color: colors[i % colors.length],\n            weight: 7,\n            opacity: 0.98\n          }}).addTo(map);\n          tails.push(tail);\n\n          var current = L.polyline([], {{\n            color: colors[i % colors.length],\n            weight: 7,\n            opacity: 0.95\n          }}).addTo(map);\n          currentChunkLayers.push(current);\n        }}\n\n        var t = 0;\n        var timer = null;\n\n        function clearCompleted() {{\n          for (var i=0; i<completedLayers.length; i++) {{\n            for (var j=0; j<completedLayers[i].length; j++) map.removeLayer(completedLayers[i][j]);\n            completedLayers[i] = [];\n            lastCompletedIdx[i] = -1;\n          }}\n          claimed = {{}};\n        }}\n\n        function update() {{\n          clearCompleted();\n\n          for (var i=0; i<truckChunks.length; i++) {{\n            var wanted = Math.max(1, Math.floor((t / 1000) * totalPoints[i]));\n            var state = getState(truckChunks[i], wanted);\n            markers[i].setLatLng(state.last);\n\n            for (var c=0; c<state.chunkIndex; c++) {{\n              var chunk = truckChunks[i][c];\n              if (chunk.is_service) addCompletedChunk(chunk.points, colors[i % colors.length], i);\n            }}\n\n            if (state.isService) {{\n              currentChunkLayers[i].setStyle({{color: colors[i % colors.length], opacity: 0.95, weight: 7, dashArray: null}});\n              currentChunkLayers[i].setLatLngs(state.points.slice(0, Math.max(2, state.localIndex)));\n              tails[i].setStyle({{color: colors[i % colors.length], opacity: 0.98, weight: 7, dashArray: null}});\n              tails[i].setLatLngs(state.tail);\n            }} else {{\n              currentChunkLayers[i].setStyle({{color:'#666666', opacity:0.45, weight:4, dashArray:'6,8'}});\n              currentChunkLayers[i].setLatLngs(state.points.slice(0, Math.max(2, state.localIndex)));\n              tails[i].setStyle({{color:'#666666', opacity:0.45, weight:4, dashArray:'6,8'}});\n              tails[i].setLatLngs(state.tail);\n            }}\n          }}\n          range.value = Math.round(t);\n          timeLabel.innerHTML = 'Progression : ' + Math.round(t / 10) + ' %';\n        }}\n\n        function pause() {{\n          if (timer !== null) {{ clearInterval(timer); timer = null; }}\n        }}\n\n        function play() {{\n          if (timer !== null) return;\n          timer = setInterval(function() {{\n            var speed = parseFloat(speedSelect.value || '0.12');\n            t += speed;\n            if (t >= 1000) {{ t = 1000; pause(); }}\n            update();\n          }}, 50);\n        }}\n\n        function reset() {{\n          pause();\n          t = 0;\n          update();\n        }}\n\n        playBtn.addEventListener('click', play);\n        pauseBtn.addEventListener('click', pause);\n        resetBtn.addEventListener('click', reset);\n        range.addEventListener('input', function() {{\n          t = parseFloat(range.value || '0');\n          update();\n        }});\n\n        update();\n      }});\n    }})();\n    </script>\n    """
    m.get_root().html.add_child(folium.Element(js))
    
    output_dir = os.path.join("results", district)
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f'{district}_{scenario}_Animation.html')
    
    m.save(filename)
    return filename