import json
import networkx as nx
from geopy.distance import geodesic
from scipy.spatial import KDTree
import numpy as np

# Load road graph
G = nx.read_graphml("chicago_road_graph.graphml")
G = nx.convert_node_labels_to_integers(G, label_attribute='osmid')

# Load crime data
with open("crimeapp/static/crime_data.json", "r") as f:
    crime_data = json.load(f)

crime_coords = [(entry["Latitude"], entry["Longitude"]) for entry in crime_data]

# Build KDTree for fast spatial queries
crime_tree = KDTree(np.radians(crime_coords))  # use radians for haversine queries

# Define constants
CRIME_RADIUS_METERS = 100
CRIME_WEIGHT = 50

EARTH_RADIUS_M = 6371000  # meters
radius_radians = CRIME_RADIUS_METERS / EARTH_RADIUS_M

print("Overlaying crime data with KDTree...")

# Process each edge
for u, v, k, data in G.edges(keys=True, data=True):
    lat_u, lon_u = float(G.nodes[u]['y']), float(G.nodes[u]['x'])
    lat_v, lon_v = float(G.nodes[v]['y']), float(G.nodes[v]['x'])
    midpoint = [(lat_u + lat_v) / 2, (lon_u + lon_v) / 2]

    # Query crimes within radius
    nearby_idx = crime_tree.query_ball_point(np.radians(midpoint), radius_radians)
    crime_count = len(nearby_idx)

    base_length = float(data.get("length", 0))
    total_cost = base_length + (crime_count * CRIME_WEIGHT)

    data["crime_weight"] = total_cost

print("Done assigning crime weights.")
nx.write_graphml(G, "chicago_crime_weighted.graphml")
print("Saved as 'chicago_crime_weighted.graphml'")
