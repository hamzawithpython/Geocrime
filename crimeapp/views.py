from django.shortcuts import render
import pandas as pd
import os
from django.conf import settings
import folium
from folium.plugins import HeatMap, MarkerCluster
from django.views.decorators.csrf import csrf_exempt
import openrouteservice
from openrouteservice import convert
from geopy.distance import geodesic
from django.http import JsonResponse
import json
from .route_engine import get_crime_aware_route

GOOGLE_API_KEY = "AIzaSyCb52P3sm3JpZXDmeXhN_tmhO2bbp-WPLg"


def index(request):
    csv_path = os.path.join(settings.BASE_DIR, 'data', 'cleaned_dataset.csv')
    df = pd.read_csv(csv_path)
    total_crimes = len(df)
    return render(request, 'crimeapp/index.html', {'total_crimes': total_crimes})

def crime_map(request):
    csv_path = os.path.join(settings.BASE_DIR, 'data', 'cleaned_dataset.csv')
    df = pd.read_csv(csv_path)

    # Creating Folium map centered on Chicago
    folium_map = folium.Map(location=[41.8781, -87.6298], zoom_start=11)

    # Preparing heatmap data
    heat_data = [[row['Latitude'], row['Longitude']] for index, row in df.iterrows() if not pd.isnull(row['Latitude']) and not pd.isnull(row['Longitude'])]

    # Adding heatmap to map
    HeatMap(heat_data).add_to(folium_map)

    # Saving generated map as static HTML file
    map_path = os.path.join(settings.BASE_DIR, 'crimeapp', 'templates', 'crimeapp', 'crime_map.html')
    folium_map.save(map_path)

    return render(request, 'crimeapp/crime_map.html')

@csrf_exempt
def map_with_input(request):
    lat = 41.8781
    lon = -87.6298
    selected_type = None
    map_view = 'heatmap'

    if request.method == 'POST':
        lat = float(request.POST.get('lat'))
        lon = float(request.POST.get('lon'))
        selected_type = request.POST.get('crime_type')
        map_view = request.POST.get('map_view')


    csv_path = os.path.join(settings.BASE_DIR, 'data', 'cleaned_dataset.csv')
    df = pd.read_csv(csv_path)

    # Filtering by crime type
    if selected_type:
        df = df[df['Primary Type'].str.upper() == selected_type.upper()]

    folium_map = folium.Map(location=[lat, lon], zoom_start=12)

    # Adding user location marker
    folium.Marker([lat, lon], tooltip='Your Location', icon=folium.Icon(color='blue')).add_to(folium_map)

    # Preparing data
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

    map_path = os.path.join(settings.BASE_DIR, 'crimeapp', 'static', 'crime_map.html')
    folium_map.save(map_path)

    return render(request, 'crimeapp/map_with_input.html', {
        'selected_type': selected_type,
        'map_view': map_view
    })

@csrf_exempt
def route_view(request):
    map_generated = False
    from .models import SavedRoute
    saved_routes = SavedRoute.objects.all()

    danger_count = 0
    danger_points = []
    selected_crime_type = ""
    safety_score = ("", "")  # Default for GET

    if request.method == 'POST':
        saved_id = request.POST.get('saved_route')

        # Loading saved route or get input
        if saved_id:
            try:
                saved = SavedRoute.objects.get(id=saved_id)
                start_lat = saved.start_lat
                start_lon = saved.start_lon
                end_lat = saved.end_lat
                end_lon = saved.end_lon
            except SavedRoute.DoesNotExist:
                start_lat = float(request.POST['start_lat'])
                start_lon = float(request.POST['start_lon'])
                end_lat = float(request.POST['end_lat'])
                end_lon = float(request.POST['end_lon'])
        else:
            start_lat = float(request.POST['start_lat'])
            start_lon = float(request.POST['start_lon'])
            end_lat = float(request.POST['end_lat'])
            end_lon = float(request.POST['end_lon'])

        # Saving route if user entered a name
        route_name = request.POST.get('save_name', '').strip()
        if route_name and not SavedRoute.objects.filter(name=route_name).exists():
            SavedRoute.objects.create(
                name=route_name,
                start_lat=start_lat,
                start_lon=start_lon,
                end_lat=end_lat,
                end_lon=end_lon
            )

        # OpenRouteService directions
        client = openrouteservice.Client(key=API_KEY)
        coords = ((start_lon, start_lat), (end_lon, end_lat))
        route = client.directions(coords)
        geometry = route['routes'][0]['geometry']
        decoded = convert.decode_polyline(geometry)
        route_points = [(pt[1], pt[0]) for pt in decoded['coordinates']]

        # Loading crimes
        csv_path = os.path.join(settings.BASE_DIR, 'data', 'cleaned_dataset.csv')
        df = pd.read_csv(csv_path).dropna(subset=['Latitude', 'Longitude'])
        selected_crime_type = request.POST.get('crime_type', '').strip().upper()
        if selected_crime_type:
            df = df[df['Primary Type'] == selected_crime_type]

        # Analyzing danger points
        max_distance_m = 200
        for _, crime in df.iterrows():
            crime_point = (crime['Latitude'], crime['Longitude'])

            for route_point in route_points:
                distance = geodesic(crime_point, route_point).meters
                if distance <= max_distance_m:
                    danger_count += 1
                    danger_points.append((crime_point, crime['Primary Type']))
                    break

        # Safety score logic
        if danger_count <= 2:
            safety_score = ("Safe", "green")
        elif danger_count <= 6:
            safety_score = ("Moderate Risk", "yellow")
        else:
            safety_score = ("Risky", "red")

        # Generating map
        mid_lat = (start_lat + end_lat) / 2
        mid_lon = (start_lon + end_lon) / 2
        folium_map = folium.Map(location=[mid_lat, mid_lon], zoom_start=13)

        folium.PolyLine(route_points, color="blue", weight=5, opacity=0.8).add_to(folium_map)
        folium.Marker([start_lat, start_lon], tooltip='Start', icon=folium.Icon(color='green')).add_to(folium_map)
        folium.Marker([end_lat, end_lon], tooltip='End', icon=folium.Icon(color='red')).add_to(folium_map)

        for (lat, lon), crime_type in danger_points:
            try:
                if crime_type in ['ASSAULT', 'ROBBERY']:
                    marker_color = 'red'
                elif crime_type in ['BATTERY', 'BURGLARY']:
                    marker_color = 'orange'
                else:
                    marker_color = 'green'

                folium.Marker(
                    location=[float(lat), float(lon)],
                    icon=folium.Icon(color=marker_color, icon='info-sign'),
                    popup=folium.Popup(f"⚠️ {crime_type}", max_width=250)
                ).add_to(folium_map)
            except Exception as e:
                print(f"Error adding marker at ({lat}, {lon}): {e}")

        map_path = os.path.join(settings.BASE_DIR, 'crimeapp', 'static', 'route_map.html')
        folium_map.save(map_path)
        map_generated = True

    return render(request, 'crimeapp/route_map.html', {
        'map_generated': map_generated,
        'danger_count': danger_count,
        'selected_crime_type': selected_crime_type,
        'safety_score': safety_score,
        'saved_routes': saved_routes
    })

def mapbox_test(request):
    return render(request, 'crimeapp/mapbox_test.html', {
        'mapbox_token': 'pk.eyJ1IjoiaGFtamFhamVlIiwiYSI6ImNtYno5N2FsajE4MTMya3M2NGJpNDJvaWQifQ.627r71W4Bj_3PrYFgdhqLw'
    })

def google_route_view(request):
    return render(request, 'crimeapp/google_route.html', {
        'google_api_key': GOOGLE_API_KEY,
        'center_lat': 41.8781,
        'center_lon': -87.6298
    })

def mapbox_route(request):
    start_lat = 41.8781
    start_lon = -87.6298
    end_lat = 41.8858
    end_lon = -87.6205

    # Loading crime data
    csv_path = os.path.join(settings.BASE_DIR, 'data', 'cleaned_dataset.csv')
    df = pd.read_csv(csv_path).dropna(subset=['Latitude', 'Longitude'])

    crimes = df.head(100)[['Latitude', 'Longitude', 'Primary Type']].to_dict(orient='records')

    return render(request, 'crimeapp/mapbox_route.html', {
        'mapbox_token': 'pk.eyJ1IjoiaGFtamFhamVlIiwiYSI6ImNtYno5N2FsajE4MTMya3M2NGJpNDJvaWQifQ.627r71W4Bj_3PrYFgdhqLw',
        'start_lat': start_lat,
        'start_lon': start_lon,
        'end_lat': end_lat,
        'end_lon': end_lon,
        'mid_lat': (start_lat + end_lat) / 2,
        'mid_lon': (start_lon + end_lon) / 2,
        'crimes': crimes
    })

@csrf_exempt
def get_custom_route(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            origin = data.get("origin")
            destination = data.get("destination")

            if not origin or not destination:
                return JsonResponse({"error": "Missing origin or destination"}, status=400)

            result = get_crime_aware_route(
                origin_lat=origin["lat"],
                origin_lng=origin["lng"],
                dest_lat=destination["lat"],
                dest_lng=destination["lng"]
            )

            return JsonResponse({
                "route": result["route"],
                "safety_info": result["safety_info"]
            }, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Only POST allowed"}, status=405)











