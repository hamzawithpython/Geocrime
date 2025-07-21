import json
import networkx as nx
from scipy.spatial import KDTree
import numpy as np

CRIME_SEVERITY = {
    "HOMICIDE": 10,
    "KIDNAPPING": 9,
    "CRIMINAL SEXUAL ASSAULT": 9,
    "SEX OFFENSE": 8,
    "ROBBERY": 8,
    "ASSAULT": 7,
    "BATTERY": 7,
    "WEAPONS VIOLATION": 7,
    "STALKING": 6,
    "OFFENSE INVOLVING CHILDREN": 6,
    "ARSON": 6,
    "BURGLARY": 5,
    "MOTOR VEHICLE THEFT": 5,
    "CRIMINAL DAMAGE": 4,
    "CRIMINAL TRESPASS": 4,
    "NARCOTICS": 3,
    "PUBLIC PEACE VIOLATION": 3,
    "DECEPTIVE PRACTICE": 2,
    "INTERFERENCE WITH PUBLIC OFFICER": 2,
    "CONCEALED CARRY LICENSE VIOLATION": 2,
    "PROSTITUTION": 2,
    "OTHER OFFENSE": 1,
    "THEFT": 1,
}

print("[INFO] Loading road graph...")
G = nx.read_graphml("chicago_road_graph.graphml")

print("[INFO] Building KDTree of edge midpoints...")
edge_coords = []
edge_keys = []

for u, v, k, data in G.edges(keys=True, data=True):
    try:
        x1, y1 = float(G.nodes[u]['x']), float(G.nodes[u]['y'])
        x2, y2 = float(G.nodes[v]['x']), float(G.nodes[v]['y'])
        midpoint = ((y1 + y2) / 2, (x1 + x2) / 2)
        edge_coords.append(midpoint)
        edge_keys.append((u, v, k))
    except KeyError:
        continue

tree = KDTree(edge_coords)

print("[INFO] Loading crime data...")
with open("crimeapp/static/crime_data.json", "r") as f:
    crime_data = json.load(f)

print("[INFO] Overlaying crime data onto edges...")
for crime in crime_data:
    try:
        crime_lat = float(crime["Latitude"])
        crime_lon = float(crime["Longitude"])
    except (KeyError, ValueError):
        continue

    dist, idx = tree.query((crime_lat, crime_lon), distance_upper_bound=0.0015)
    if np.isinf(dist) or idx >= len(edge_keys):
        continue

    u, v, k = edge_keys[idx]
    edge = G.edges[u, v, k]

    crime_type = crime.get("Primary Type", "").upper()
    severity = CRIME_SEVERITY.get(crime_type, 1)

    edge["crime_weight"] = edge.get("crime_weight", 1.0) + severity

print("[INFO] Saving crime-weighted graph...")
nx.write_graphml(G, "chicago_crime_weighted.graphml")
print("[SUCCESS] Crime-weighted graph saved as 'chicago_crime_weighted.graphml'")
print(f"Overlay complete. Total crimes processed: {len(crime_data)}")
