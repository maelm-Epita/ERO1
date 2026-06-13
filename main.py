import sys
from collections import Counter
import osmnx as ox

from config import DISTRICTS, MAX_TRUCKS
from graph_tools import precompute_shortest_paths, scenario_A, scenario_B, scenario_C
from solver import solve_for_k, stats, choose_k
from visualization import draw_animation_map

def run_scenario(G, lengths, paths, scenario_fn, scenario_name, district, d):
    print(f"\n{'=' * 72}\nSCÉNARIO {scenario_name} — {district}\n{'=' * 72}")
    depot = ox.distance.nearest_nodes(G, X=d['depot'][1], Y=d['depot'][0])
    jobs = scenario_fn(G, d)
    counts = Counter((j.priority for j in jobs))
    print(f'Arcs à déneiger : {len(jobs)} | P1={counts[1]} P2={counts[2]} P3={counts[3]}')
    
    routes_by_k = {}
    stats_by_k = {}
    
    for k in range(1, min(MAX_TRUCKS, len(jobs)) + 1):
        print(f'  Routage k={k}...')
        routes = solve_for_k(G, jobs, depot, k, scenario_name, lengths, paths)
        st = stats(routes, len(jobs))
        routes_by_k[k] = routes
        stats_by_k[k] = st
        
    k_rec, reason = choose_k(stats_by_k, scenario_name)
    
    print('\n  k | coût $ | h max | km | utile | répété | taux | fin P1 | score | choix')
    print('  ' + '-' * 94)
    for k, st in stats_by_k.items():
        mark = '<-- RETENU' if k == k_rec else ''
        print(f"  {k} | {st['cost']:6.0f} | {st['hours']:5.2f} | {st['km']:5.1f} | {st['service_km']:5.1f} | {st['repeat_km']:6.1f} | {100 * st['repeat_rate']:4.0f}% | {st['finish_p1']:6.2f} | {st['score']:7.0f} | {mark}")
    
    print(f'  Choix : k={k_rec} — {reason}')
    
    animation_file = draw_animation_map(G, routes_by_k[k_rec], stats_by_k[k_rec], jobs, district, scenario_name, d)
    print(f'  Carte interactive : {animation_file}')
    
    out = dict(stats_by_k[k_rec])
    out['counts'] = counts
    return out

def print_comparison(district, results):
    print(f"\n{'=' * 100}\nCOMPARAISON — {district.upper()}\n{'=' * 100}")
    print('Scén | P1 | P2 | P3 | k | coût $ | h max | km | utile | répété | taux | fin P1 | couverture')
    print('-' * 112)
    for name, st in results.items():
        c = st['counts']
        print(f" {name:<3} | {c[1]:>3} | {c[2]:>3} | {c[3]:>3} | {st['k']} | {st['cost']:6.0f} | {st['hours']:5.2f} | {st['km']:5.1f} | {st['service_km']:5.1f} | {st['repeat_km']:6.1f} | {100 * st['repeat_rate']:4.0f}% | {st['finish_p1']:6.2f} | {st['covered_jobs']}/{st['total_jobs']}")

def parse_cli():
    print('\nChoisis le quartier à traiter :')
    keys = list(DISTRICTS.keys())
    
    for i, key in enumerate(keys, 1):
        print(f'  {i}. {key}')
    print(f'  {len(keys) + 1}. Tous')
    
    choice = input('Quartier [1] : ').strip()
    if not choice:
        choice = '1'
        
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(keys):
            return [keys[idx - 1]]
        elif idx == len(keys) + 1:
            return keys
        else:
            print('Choix invalide.')
            sys.exit(1)
    else:
        print('Veuillez entrer un numéro valide.')
        sys.exit(1)

def main():
    print('VERSION CHINESE_INTERACTIVE_FINAL')
    ox.settings.use_cache = True
    ox.settings.log_console = False
    
    districts = parse_cli()
    
    for district in districts:
        d = DISTRICTS[district]
        print(f"\n{'#' * 76}\n# TRAITEMENT DE : {district}\n{'#' * 76}")
        print('Téléchargement OSM...')
        
        G = ox.graph_from_place(d['sector'], network_type='drive', simplify=True)
        print(f'Graphe dirigé : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arcs')
        
        print('Pré-calcul des plus courts chemins (Veuillez patienter)...')
        lengths, paths = precompute_shortest_paths(G)
        
        results = {
            'A': run_scenario(G, lengths, paths, scenario_A, 'A', district, d), 
            'B': run_scenario(G, lengths, paths, scenario_B, 'B', district, d), 
            'C': run_scenario(G, lengths, paths, scenario_C, 'C', district, d)
        }
        
        print_comparison(district, results)

if __name__ == '__main__':
    main()