import math
from collections import Counter
from models import Segment, Route
from graph_tools import project, midpoint, min_edge_key_length, service_key_for_edge, dist_to, path_to
from config import BIG, SPEED_KMH, PRIORITY_WEIGHTS, COST_FIXED_PER_TRUCK, COST_PER_KM, COST_HOUR_FIRST_8, COST_HOUR_AFTER_8, TARGETS

def hours(meters):
    return meters / 1000 / SPEED_KMH

def principal_axis(G, jobs, depot_node):
    lat0, lon0 = (G.nodes[depot_node]['y'], G.nodes[depot_node]['x'])
    pts = [project(*midpoint(G, j), lat0, lon0) for j in jobs]
    if not pts:
        return (1.0, 0.0)
    mx = sum((x for x, y in pts)) / len(pts)
    my = sum((y for x, y in pts)) / len(pts)
    sxx = sum(((x - mx) ** 2 for x, y in pts)) / len(pts)
    syy = sum(((y - my) ** 2 for x, y in pts)) / len(pts)
    sxy = sum(((x - mx) * (y - my) for x, y in pts)) / len(pts)
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return (math.cos(angle), math.sin(angle))

def split_sectors(G, jobs, depot_node, k, scenario):
    if k <= 1:
        return [list(jobs)]
    lat0, lon0 = (G.nodes[depot_node]['y'], G.nodes[depot_node]['x'])
    ax, ay = principal_axis(G, jobs, depot_node)
    offset = {'A': 0.0, 'B': 0.4, 'C': -0.35}.get(scenario, 0.0)
    c, s = (math.cos(offset), math.sin(offset))
    ax, ay = (ax * c - ay * s, ax * s + ay * c)
    scored = []
    for j in jobs:
        x, y = project(*midpoint(G, j), lat0, lon0)
        scored.append((x * ax + y * ay, j.length_m, j))
    scored.sort(key=lambda t: t[0])
    total_len = sum((j.length_m for _, _, j in scored))
    target = total_len / k if k else total_len
    sectors = [[] for _ in range(k)]
    cur = 0
    acc = 0.0
    for _, _, j in scored:
        if cur < k - 1 and acc >= target:
            cur += 1
            acc = 0.0
        sectors[cur].append(j)
        acc += j.length_m
    return sectors

def build_job_maps(G, jobs):
    by_uid = {j.uid: j for j in jobs}
    by_service = {}
    for j in jobs:
        if G.has_edge(j.u, j.v, j.k):
            by_service[service_key_for_edge(G, j.u, j.v, j.k)] = j
        if G.has_edge(j.v, j.u):
            rk, _ = min_edge_key_length(G, j.v, j.u)
            if rk is not None:
                by_service[service_key_for_edge(G, j.v, j.u, rk)] = j
    return (by_uid, by_service)

def add_path_segments(G, node_path, unserved, by_service, segments, counters, step, kind='repeat'):
    if not node_path or len(node_path) < 2:
        return step
    for a, b in zip(node_path[:-1], node_path[1:]):
        kk, length = min_edge_key_length(G, a, b)
        if kk is None or length >= BIG:
            continue
        job = by_service.get(service_key_for_edge(G, a, b, kk))
        if job is not None and job.uid in unserved:
            unserved.remove(job.uid)
            counters['service'] += length
            counters['covered'] += 1
            counters['covered_by_prio'][job.priority] += 1
            segments.append(Segment(a, b, kk, length, True, False, job.priority, job.uid, step, 'opportunistic'))
        else:
            counters['repeat'] += length
            segments.append(Segment(a, b, kk, length, False, True, None, None, step, kind))
        counters['total'] += length
        step += 1
    return step

def path_useful_length(G, node_path, unserved, by_service):
    if not node_path or len(node_path) < 2:
        return 0.0
    useful = 0.0
    seen = set()
    for a, b in zip(node_path[:-1], node_path[1:]):
        kk, length = min_edge_key_length(G, a, b)
        if kk is None or length >= BIG:
            continue
        job = by_service.get(service_key_for_edge(G, a, b, kk))
        if job is not None and job.uid in unserved and (job.uid not in seen):
            useful += length
            seen.add(job.uid)
    return useful

def direction_penalty(G, previous_node, current_node, target_node):
    if previous_node is None or previous_node == current_node or target_node == current_node:
        return 0.0
    lat0, lon0 = (G.nodes[current_node]['y'], G.nodes[current_node]['x'])
    x1, y1 = project(G.nodes[current_node]['y'], G.nodes[current_node]['x'], lat0, lon0)
    xp, yp = project(G.nodes[previous_node]['y'], G.nodes[previous_node]['x'], lat0, lon0)
    xt, yt = project(G.nodes[target_node]['y'], G.nodes[target_node]['x'], lat0, lon0)
    vx1, vy1 = (x1 - xp, y1 - yp)
    vx2, vy2 = (xt - x1, yt - y1)
    n1 = math.hypot(vx1, vy1)
    n2 = math.hypot(vx2, vy2)
    if n1 <= 1 or n2 <= 1:
        return 0.0
    cosang = max(-1.0, min(1.0, (vx1 * vx2 + vy1 * vy2) / (n1 * n2)))
    return 50.0 * (1.0 - cosang)

def update_finish_times(counters, total_by_prio, finish):
    for p in (1, 2, 3):
        if total_by_prio[p] == 0:
            finish[p] = 0.0
        elif finish[p] == 0.0 and counters['covered_by_prio'][p] >= total_by_prio[p]:
            finish[p] = hours(counters['total'])

def orientation_options(G, lengths, current, job):
    opts = []
    if G.has_edge(job.u, job.v):
        kk = job.k if G.has_edge(job.u, job.v, job.k) else min_edge_key_length(G, job.u, job.v)[0]
        if kk is not None:
            opts.append((dist_to(lengths, current, job.u), job.u, job.v, kk))
    if G.has_edge(job.v, job.u):
        rk, _ = min_edge_key_length(G, job.v, job.u)
        if rk is not None:
            opts.append((dist_to(lengths, current, job.v), job.v, job.u, rk))
    if not opts:
        opts.append((BIG, job.u, job.v, job.k))
    return opts

def route_sector(G, lengths, paths, sector_jobs, depot_node, truck_id, scenario):
    by_uid, by_service = build_job_maps(G, sector_jobs)
    unserved = set(by_uid.keys())
    total_by_prio = Counter((j.priority for j in sector_jobs))
    segments = []
    counters = {'total': 0.0, 'service': 0.0, 'repeat': 0.0, 'covered': 0, 'covered_by_prio': Counter()}
    finish = {1: 0.0, 2: 0.0, 3: 0.0}
    current = depot_node
    previous_node = None
    step = 1

    def best_orientation_for(job):
        opts = orientation_options(G, lengths, current, job)
        return min(opts, key=lambda o: (o[0], job.uid))

    def score_job(job):
        travel, su, sv, sk = best_orientation_for(job)
        if travel >= BIG:
            return BIG
        node_path = path_to(paths, current, su)
        useful_on_path = path_useful_length(G, node_path, unserved, by_service)
        min_remaining_prio = min((by_uid[uid].priority for uid in unserved))
        priority_penalty = PRIORITY_WEIGHTS.get(scenario, 170.0) * (job.priority - min_remaining_prio)
        local_bonus = 0.0
        if travel <= 40:
            local_bonus = 220.0
        elif travel <= 100:
            local_bonus = 140.0
        elif travel <= 180:
            local_bonus = 70.0
        productive_bonus = 0.75 * useful_on_path
        turn_penalty = direction_penalty(G, previous_node, current, su)
        length_bonus = min(80.0, 0.08 * job.length_m)
        return travel + priority_penalty + turn_penalty - local_bonus - productive_bonus - length_bonus

    while unserved:
        candidates = [by_uid[uid] for uid in unserved]
        best = min(candidates, key=lambda j: (score_job(j), j.priority, best_orientation_for(j)[0], j.uid))
        travel, su, sv, sk = best_orientation_for(best)
        node_path = path_to(paths, current, su) if travel < BIG else None
        old_current = current
        step = add_path_segments(G, node_path, unserved, by_service, segments, counters, step, kind='link')
        
        if node_path and len(node_path) >= 2:
            previous_node = node_path[-2]
            current = node_path[-1]
        elif node_path and len(node_path) == 1:
            current = node_path[-1]
            
        update_finish_times(counters, total_by_prio, finish)
        
        if best.uid in unserved:
            unserved.remove(best.uid)
            kk, actual_len = min_edge_key_length(G, su, sv)
            if kk is None or actual_len >= BIG:
                kk, actual_len = (sk, best.length_m)
            counters['total'] += actual_len
            counters['service'] += actual_len
            counters['covered'] += 1
            counters['covered_by_prio'][best.priority] += 1
            segments.append(Segment(su, sv, kk, actual_len, True, False, best.priority, best.uid, step, 'service'))
            previous_node = su
            current = sv
            step += 1
            update_finish_times(counters, total_by_prio, finish)
        else:
            current = node_path[-1] if node_path else old_current
            
    back_path = path_to(paths, current, depot_node) if dist_to(lengths, current, depot_node) < BIG else None
    step = add_path_segments(G, back_path, set(), by_service, segments, counters, step, kind='return')
    
    for p in (1, 2, 3):
        if total_by_prio[p] == 0:
            finish[p] = 0.0
        elif finish[p] == 0.0:
            finish[p] = hours(counters['total'])
            
    return Route(truck_id=truck_id, segments=segments, meters_total=counters['total'], meters_service=counters['service'], meters_repeat=counters['repeat'], finish_priority_h=finish, covered_jobs=counters['covered'])

def solve_for_k(G, jobs, depot_node, k, scenario, lengths, paths):
    sectors = split_sectors(G, jobs, depot_node, k, scenario)
    routes = []
    for i, sector in enumerate(sectors):
        routes.append(route_sector(G, lengths, paths, sector, depot_node, i, scenario))
    return routes

def truck_cost(meters):
    km = meters / 1000
    h = hours(meters)
    return COST_FIXED_PER_TRUCK + COST_PER_KM * km + COST_HOUR_FIRST_8 * min(h, 8) + COST_HOUR_AFTER_8 * max(h - 8, 0)

def stats(routes, total_jobs):
    total = sum((r.meters_total for r in routes))
    service = sum((r.meters_service for r in routes))
    repeat = sum((r.meters_repeat for r in routes))
    finish = {p: max((r.finish_priority_h.get(p, 0.0) for r in routes), default=0.0) for p in (1, 2, 3)}
    return {'k': len(routes), 'cost': sum((truck_cost(r.meters_total) for r in routes)), 'hours': max((hours(r.meters_total) for r in routes), default=0.0), 'km': total / 1000, 'service_km': service / 1000, 'repeat_km': repeat / 1000, 'repeat_rate': repeat / total if total else 0.0, 'finish_p1': finish[1], 'finish_p2': finish[2], 'finish_p3': finish[3], 'covered_jobs': sum((r.covered_jobs for r in routes)), 'total_jobs': total_jobs}

def add_score(s, scenario):
    t = TARGETS[scenario]
    late_total = max(0.0, s['hours'] - t['total_h'])
    late_p1 = max(0.0, s['finish_p1'] - t['p1_h'])
    late_p2 = max(0.0, s['finish_p2'] - t['p2_h'])
    repeat_over = max(0.0, s['repeat_rate'] - t['max_repeat_rate'])
    coverage_penalty = 0 if s['covered_jobs'] == s['total_jobs'] else 1000000
    s['feasible'] = s['covered_jobs'] == s['total_jobs'] and s['hours'] <= t['total_h'] and (s['finish_p1'] <= t['p1_h']) and (s['finish_p2'] <= t['p2_h']) and (s['repeat_rate'] <= t['max_repeat_rate'])
    s['score'] = s['cost'] + 70 * s['repeat_km'] + 1200 * late_total ** 2 + 1800 * late_p1 ** 2 + 900 * late_p2 ** 2 + 15000 * repeat_over ** 2 + coverage_penalty
    return s

def choose_k(stats_by_k, scenario):
    for st in stats_by_k.values():
        add_score(st, scenario)
    feasible = [(k, s) for k, s in stats_by_k.items() if s['feasible']]
    if feasible:
        k, _ = min(feasible, key=lambda item: (item[1]['cost'], item[0]))
        return (k, 'plus petit coût parmi les solutions respectant les contraintes')
    k, _ = min(stats_by_k.items(), key=lambda item: (item[1]['score'], item[0]))
    return (k, 'aucun k totalement faisable : meilleur compromis pénalisé')