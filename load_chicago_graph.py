import osmnx as ox
import networkx as nx

place = "Chicago, Illinois, USA"
print("Downloading road network for:", place)

G = ox.graph_from_place(place, network_type='drive')

# Removing or converting unsupported edge attributes
for u, v, k, data in G.edges(keys=True, data=True):
    keys_to_delete = []
    for key, value in data.items():
        # Removing unsupported types (like LineString or list)
        if isinstance(value, (list, dict)) or "geometry" in key:
            keys_to_delete.append(key)
    for key in keys_to_delete:
        del data[key]

#writing to GraphML safely
nx.write_graphml(G, "chicago_road_graph.graphml")
print("Graph saved successfully as 'chicago_road_graph.graphml'")
