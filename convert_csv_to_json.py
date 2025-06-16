import pandas as pd
import os
import json

base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base_dir, 'data', 'cleaned_dataset.csv')
json_path = os.path.join(base_dir, 'crimeapp', 'static', 'crime_data.json')

df = pd.read_csv(csv_path)

df = df[['Latitude', 'Longitude', 'Primary Type']].dropna()

data = df.to_dict(orient='records')

with open(json_path, 'w') as f:
    json.dump(data, f, indent=2)

print(f"✅ JSON file created at: {json_path}")
