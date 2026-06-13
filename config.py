MAX_TRUCKS = 6
SPEED_KMH = 10.0
BIG = 10 ** 15

COST_FIXED_PER_TRUCK = 500.0
COST_PER_KM = 1.1
COST_HOUR_FIRST_8 = 1.1
COST_HOUR_AFTER_8 = 1.3

TARGETS = {
    'A': {'total_h': 8.0, 'p1_h': 6.0, 'p2_h': 7.0, 'max_repeat_rate': 0.45},
    'B': {'total_h': 8.0, 'p1_h': 4.0, 'p2_h': 6.0, 'max_repeat_rate': 0.45},
    'C': {'total_h': 8.0, 'p1_h': 3.6, 'p2_h': 6.0, 'max_repeat_rate': 0.45},
}

PRIORITY_WEIGHTS = {'A': 80.0, 'B': 260.0, 'C': 260.0}
TRUCK_COLORS = ['#e6194B', '#4363d8', '#3cb44b', '#f58231', '#911eb4', '#46f0f0']
PRIO_LABEL = {1: 'P1 urgent', 2: 'P2 important', 3: 'P3 local'}

MAJOR = {'motorway', 'trunk', 'primary', 'primary_link', 'trunk_link', 'motorway_link'}
SECONDARY = {'secondary', 'secondary_link', 'tertiary', 'tertiary_link'}
IGNORED = {'footway', 'path', 'cycleway', 'pedestrian', 'steps', 'construction', 'bridleway'}

DISTRICTS = {
    'Verdun': {
        'sector': 'Verdun, Montréal, Québec, Canada', 
        'depot': (45.4617, -73.5722), 
        'poi_sante': [(45.4639, -73.5638), (45.4583, -73.5694), (45.4601, -73.5722)], 
        'poi_police': [(45.4656, -73.5683)], 
        'poi_pompiers': [(45.4678, -73.5681), (45.4617, -73.5722)], 
        'poi_metro': [(45.4594, -73.5717), (45.4708, -73.5664), (45.4558, -73.5753)], 
        'poi_ecoles': [
            (45.4633, -73.5756), (45.4611, -73.57), (45.4694, -73.5675), 
            (45.4636, -73.5719), (45.465, -73.5736), (45.4583, -73.5756), 
            (45.47, -73.568), (45.468, -73.5672)
        ], 
        'bus_streets': {
            'wellington', 'de verdun', 'verdun', 'lasalle', 'la salle', 
            'bannantyne', 'de l eglise', "de l'église", 'gaetan laberge', 
            'gaëtan-laberge', 'champlain', 'galt', 'desmarchais', 'rue church'
        }
    }, 
    'Outremont': {
        'sector': 'Outremont, Montréal, Québec, Canada', 
        'depot': (45.5177, -73.6093), 
        'poi_sante': [(45.508, -73.6155), (45.5195, -73.605)], 
        'poi_police': [(45.5143, -73.6083)], 
        'poi_pompiers': [(45.516, -73.61)], 
        'poi_metro': [(45.5156, -73.6158), (45.5225, -73.6083), (45.5102, -73.6142)], 
        'poi_ecoles': [
            (45.5165, -73.6125), (45.519, -73.607), (45.513, -73.609), 
            (45.521, -73.611), (45.5148, -73.606), (45.5175, -73.6145)
        ], 
        'bus_streets': {
            'van horne', 'bernard', 'laurier', 'cote sainte catherine', 
            'côte-sainte-catherine', 'acadie', 'outremont', 'maplewood'
        }
    }, 
    'Anjou': {
        'sector': 'Anjou, Montréal, Québec, Canada', 
        'depot': (45.605, -73.56), 
        'poi_sante': [(45.601, -73.554), (45.608, -73.562)], 
        'poi_police': [(45.604, -73.557)], 
        'poi_pompiers': [(45.6065, -73.558)], 
        'poi_metro': [(45.5958, -73.5528), (45.5992, -73.5463)], 
        'poi_ecoles': [
            (45.602, -73.561), (45.6055, -73.5545), (45.6085, -73.5595), 
            (45.6015, -73.556), (45.607, -73.5615), (45.6035, -73.558)
        ], 
        'bus_streets': {
            'jean talon', 'jean-talon', 'metropolitaine', 'métropolitaine', 
            'anjou', 'des roseraies', 'beaubien', 'galeries d anjou', 
            "galeries d'anjou", 'pierre de coubertin', 'pierre-de-coubertin'
        }
    }, 
    'RDP-PAT': {
        'sector': 'Rivière-des-Prairies-Pointe-aux-Trembles, Montréal, Québec, Canada', 
        'depot': (45.662, -73.529), 
        'poi_sante': [(45.66, -73.512)], 
        'poi_police': [(45.665, -73.52), (45.64, -73.5)], 
        'poi_pompiers': [(45.664, -73.524), (45.637, -73.491)], 
        'poi_metro': [], 
        'poi_ecoles': [
            (45.658, -73.531), (45.665, -73.518), (45.644, -73.506), 
            (45.65, -73.515), (45.639, -73.497), (45.662, -73.526), 
            (45.635, -73.493), (45.668, -73.52)
        ], 
        'bus_streets': {
            'sherbrooke', 'notre dame', 'notre-dame', 'de la rousseliere', 
            'de la rousselière', 'perras', 'rodolphe forget', 'rodolphe-forget', 
            'pointe aux trembles', 'pointe-aux-trembles', 'riviere des prairies', 
            'rivière-des-prairies'
        }
    }
}