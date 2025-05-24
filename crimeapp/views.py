from django.shortcuts import render
import pandas as pd
import os
from django.conf import settings
import folium
from folium.plugins import HeatMap

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
