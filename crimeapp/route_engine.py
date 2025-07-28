import networkx as nx
import osmnx as ox
from geopy.distance import geodesic
import json

# Loading the crime-weighted graph
G = nx.read_graphml("chicago_crime_weighted.graphml")

with open("crimeapp/static/crime_data.json", "r") as f:
    crime_data = json.load(f)

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


# Converting node keys to integers
G = nx.convert_node_labels_to_integers(G, label_attribute="osmid")

# Rebuilding spatial index for nearest node search
nodes = [(float(data['y']), float(data['x'])) for _, data in G.nodes(data=True)]
node_ids = list(G.nodes)

def find_nearest_node(lat, lng):
    """Returning node in G closest to given (lat, lng)."""
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

    # Running A* using our custom edge weights
    path = nx.astar_path(G, source_node, target_node, weight="crime_weight")

    # Extracting lat/lng coordinates from path
    latlng_path = []
    for node in path:
        lat = float(G.nodes[node]['y'])
        lng = float(G.nodes[node]['x'])
        latlng_path.append([lat, lng])

    stats = analyze_crimes_near_route(latlng_path, crime_data)

    return {
        "route": latlng_path,
        "safety_info": stats
    }


def analyze_crimes_near_route(route_coords, crime_data, radius_m=100):
    seen_crimes = set()
    crime_count = 0
    severity_sum = 0

    for point in route_coords:
        for idx, crime in enumerate(crime_data):
            try:
                crime_lat = float(crime["Latitude"])
                crime_lng = float(crime["Longitude"])
                crime_type = crime.get("Primary Type", "").upper()
            except (ValueError, KeyError):
                continue

            dist = geodesic(point, (crime_lat, crime_lng)).meters
            if dist <= radius_m:
                unique_id = (round(crime_lat, 6), round(crime_lng, 6), crime_type)
                if unique_id not in seen_crimes:
                    seen_crimes.add(unique_id)
                    crime_count += 1
                    severity_sum += CRIME_SEVERITY.get(crime_type, 1)

    if crime_count <= 5:
        risk_label = "Safe"
    elif crime_count <= 15:
        risk_label = "Moderate"
    else:
        risk_label = "High Risk"

    return {
        "nearby_crimes": crime_count,
        "danger_score": severity_sum,
        "risk_level": risk_label
    }



if __name__ == "__main__":
    origin = (41.831, -87.628)
    destination = (41.844, -87.64)

    route = get_crime_aware_route(*origin, *destination)
    print("Route:")
    for point in route:
        print(point)
