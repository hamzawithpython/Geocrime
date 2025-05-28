from django.shortcuts import render
import pandas as pd
import os
from django.conf import settings
import folium
from folium.plugins import HeatMap, MarkerCluster
from django.views.decorators.csrf import csrf_exempt
import openrouteservice
from openrouteservice import convert

def index(request):
    csv_path = os.path.join(settings.BASE_DIR, 'data', 'cleaned_dataset.csv')
    df = pd.read_csv(csv_path)
    total_crimes = len(df)
    return render(request, 'crimeapp/index.html', {'total_crimes': total_crimes})

def crime_map(request):
    csv_path = os.path.join(settings.BASE_DIR, 'data', 'cleaned_dataset.csv')
    df = pd.read_csv(csv_path)

    # Create Folium map centered on Chicago
    folium_map = folium.Map(location=[41.8781, -87.6298], zoom_start=11)

    # Prepare heatmap data
    heat_data = [[row['Latitude'], row['Longitude']] for index, row in df.iterrows() if not pd.isnull(row['Latitude']) and not pd.isnull(row['Longitude'])]

    # Add heatmap to map
    HeatMap(heat_data).add_to(folium_map)

    # Save generated map as static HTML file
    map_path = os.path.join(settings.BASE_DIR, 'crimeapp', 'templates', 'crimeapp', 'map.html')
    folium_map.save(map_path)

    return render(request, 'crimeapp/map.html')

@csrf_exempt
def map_with_input(request):
    lat = 41.8781
    lon = -87.6298
    selected_type = None
    map_view = 'heatmap'  # default view

    if request.method == 'POST':
        lat = float(request.POST.get('lat'))
        lon = float(request.POST.get('lon'))
        selected_type = request.POST.get('crime_type')
        map_view = request.POST.get('map_view')

    csv_path = os.path.join(settings.BASE_DIR, 'data', 'cleaned_dataset.csv')
    df = pd.read_csv(csv_path)

    # Filter by crime type
    if selected_type:
        df = df[df['Primary Type'].str.upper() == selected_type.upper()]

    folium_map = folium.Map(location=[lat, lon], zoom_start=12)

    # Add user location marker
    folium.Marker([lat, lon], tooltip='Your Location', icon=folium.Icon(color='blue')).add_to(folium_map)

    # Prepare data
    filtered_data = df[['Latitude', 'Longitude', 'Primary Type', 'Description']].dropna()

    if map_view == 'heatmap':
        heat_data = [[row['Latitude'], row['Longitude']] for _, row in filtered_data.iterrows()]
        HeatMap(heat_data).add_to(folium_map)
    elif map_view == 'markers':
        marker_cluster = MarkerCluster().add_to(folium_map)
        for _, row in filtered_data.iterrows():
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=f"{row['Primary Type']} - {row['Description']}",
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(marker_cluster)

    map_path = os.path.join(settings.BASE_DIR, 'crimeapp', 'static', 'map.html')
    folium_map.save(map_path)

    return render(request, 'crimeapp/map_with_input.html', {
        'selected_type': selected_type,
        'map_view': map_view
    })

@csrf_exempt
def route_view(request):
    map_generated = False  # new flag

    if request.method == 'POST':
        start_lat = float(request.POST['start_lat'])
        start_lon = float(request.POST['start_lon'])
        end_lat = float(request.POST['end_lat'])
        end_lon = float(request.POST['end_lon'])

        client = openrouteservice.Client(key='5b3ce3597851110001cf62481f0092ec302e4859b7961fa03b5a6575')
        coords = ((start_lon, start_lat), (end_lon, end_lat))
        route = client.directions(coords)
        geometry = route['routes'][0]['geometry']
        decoded = convert.decode_polyline(geometry)

        mid_lat = (start_lat + end_lat) / 2
        mid_lon = (start_lon + end_lon) / 2
        folium_map = folium.Map(location=[mid_lat, mid_lon], zoom_start=13)

        route_coords = [(pt[1], pt[0]) for pt in decoded['coordinates']]
        folium.PolyLine(route_coords, color="blue", weight=5, opacity=0.8).add_to(folium_map)

        folium.Marker([start_lat, start_lon], tooltip='Start', icon=folium.Icon(color='green')).add_to(folium_map)
        folium.Marker([end_lat, end_lon], tooltip='End', icon=folium.Icon(color='red')).add_to(folium_map)

        map_path = os.path.join(settings.BASE_DIR, 'crimeapp', 'static', 'route_map.html')
        folium_map.save(map_path)

        map_generated = True  # set flag

    return render(request, 'crimeapp/route_map.html', {'map_generated': map_generated})




