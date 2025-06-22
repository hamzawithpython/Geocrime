import networkx as nx
import osmnx as ox
from geopy.distance import geodesic

# Load the crime-weighted graph
G = nx.read_graphml("chicago_crime_weighted.graphml")

# Convert node keys to integers
G = nx.convert_node_labels_to_integers(G, label_attribute="osmid")

# Rebuild spatial index for nearest node search
nodes = [(float(data['y']), float(data['x'])) for _, data in G.nodes(data=True)]
node_ids = list(G.nodes)

def find_nearest_node(lat, lng):
    """Return node in G closest to given (lat, lng)."""
    min_dist = float('inf')
    nearest = None
    for node, coords in zip(node_ids, nodes):
        dist = geodesic((lat, lng), coords).meters
        if dist < min_dist:
            min_dist = dist
            nearest = node
    return nearest

def get_crime_aware_route(origin_lat, origin_lng, dest_lat, dest_lng):
    source_node = find_nearest_node(origin_lat, origin_lng)
    target_node = find_nearest_node(dest_lat, dest_lng)

    # Run A* using our custom edge weights
    path = nx.astar_path(G, source_node, target_node, weight="crime_weight")

    # Extract lat/lng coordinates from path
    latlng_path = []
    for node in path:
        lat = float(G.nodes[node]['y'])
        lng = float(G.nodes[node]['x'])
        latlng_path.append([lat, lng])

    return latlng_path


if __name__ == "__main__":
    origin = (41.831, -87.628)  # Example: near downtown Chicago
    destination = (41.844, -87.64)

    route = get_crime_aware_route(*origin, *destination)
    print("Route:")
    for point in route:
        print(point)
