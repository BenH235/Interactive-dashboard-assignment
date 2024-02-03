# Required libraries
import streamlit as st
import pandas as pd
import numpy as np
# Data visualisations
import plotly.express as px
import plotly.graph_objects as go
# Mapping & geospatial analysis
import folium
from folium import GeoJson, Choropleth
from streamlit_folium import st_folium, folium_static
import geopandas as gpd
import requests
from shapely.geometry import Point
from haversine import haversine, Unit
import datapoint
from config import API_KEY

@st.cache_data
def fetch_geojson():
    url = 'https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/National_Nature_Reserves_England/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson'
    r = requests.get(url)
    gdf = gpd.GeoDataFrame.from_features(r.json()["features"], crs='EPSG:4326')
    return gdf

# Streamlit application main code
st.set_page_config(page_title='Local Nature Reserve Finder', 
                   layout='wide', 
                  )

st.title('Local Nature Reserve Finders')
st.caption('An application that helps you find local nature reserves in England. The application suggests a reserve based on locality and short term weather forecasts.')

gdf = fetch_geojson()
postcode = st.text_input('Please enter valid postcode', value="", max_chars=None, key=None, type="default", help=None)

loc = requests.get(f'https://api.postcodes.io/postcodes/{postcode}').json()
lat = loc['result']['latitude']
lon = loc['result']['longitude']

def distance_from_poly(polygon, start_lat=lat, start_lon=lon):
    end_lat = polygon.centroid.y
    end_lon = polygon.centroid.x
    
    return haversine((start_lat, start_lon), (end_lat, end_lon), unit=Unit.MILES)

def dataframe_with_selections(df):
    df_with_selections = df.copy()
    df_with_selections.insert(0, "Show weather forecast", False)

    # Get dataframe row-selections from user with st.data_editor
    edited_df = st.data_editor(
        df_with_selections,
        hide_index=True,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=df.columns,
    )

    # Filter the dataframe using the temporary column, then drop the column
    selected_rows = edited_df[edited_df["Show weather forecast"]]
    return selected_rows.drop("Show weather forecast", axis=1)
    

gdf['distance'] = gdf['geometry'].apply(distance_from_poly)
nearby_parks = gdf[gdf['distance'] <= 10]

mapping, information = st.columns(2)

nearby_parks = nearby_parks[['NNR_NAME', 'distance', 'Shape__Area']].rename(columns  = {'NNR_NAME': 'Name', 'distance':'distance (miles)',  'Shape__Area': 'Land area'})

# information.write(nearby_parks.sort_values(by = 'distance (miles)', ascending = True).reset_index(drop=True))

with information:
    selection = dataframe_with_selections(nearby_parks.sort_values(by = 'distance (miles)', ascending = True).reset_index(drop=True))

locations = gdf[gdf.NNR_NAME.isin(selection.Name.to_list())]['geometry'].centroid.to_list()

# Get weather data for selected locations
# Create connection to DataPoint with your API key
conn = datapoint.connection(api_key=API_KEY)

# Get the nearest site for my latitude and longitude
site = conn.get_nearest_forecast_site(locations[0].y, locations[0].x)

# Get a forecast for my nearest site with 3 hourly timesteps
forecast = conn.get_forecast_for_site(site.id, "daily")

date_list = []
text_list = []
temp_list = []
prec_list = []
for day in forecast.days:

    # Loop through time steps and print out info
    for timestep in day.timesteps:
        date_list.append(timestep.date)
        text_list.append(timestep.weather.text)
        temp_list.append(timestep.temperature.value)
        prec_list.append(timestep.precipitation.value)
        
forecast_df=pd.DataFrame()
forecast_df['date']=date_list
forecast_df['text']=text_list
forecast_df['tempurature']=temp_list
forecast_df['precipitation']=prec_list

information.write(forecast_df)

m = folium.Map(tiles='OpenStreetMap', location=(50, 3), zoom_start=6)

folium.GeoJson(gdf.to_json(), name='geojson_layer').add_to(m)
folium.Marker(location=(lat, lon), popup="Central Point").add_to(m)

# Create a CircleMarker to represent the distance
circle_marker = folium.Circle(
    location=(lat, lon),
    radius=25_000,
    color='blue',
    fill=True,
    fill_color='blue',
    fill_opacity=0.1,
    popup="5000 meter radius"
)



circle_marker.add_to(m)

folium.LayerControl().add_to(m)

with mapping:
    folium_static(m, width=800)




# st.write(cliked_lat, clicked_lon)


# if cliked_lat is not None:
#     map_container.empty()
    
#     m = folium.Map(tiles='OpenStreetMap', location=(50, 3), zoom_start=6)
#     cliked_lat = st_data["last_clicked"]['lat']
#     clicked_lon = st_data["last_clicked"]['lng']
    
#     folium.Marker(location=(cliked_lat, clicked_lon), popup="Central Point").add_to(m)

#     # Create a CircleMarker to represent the distance
#     circle_marker = folium.Circle(
#         location=(cliked_lat, clicked_lon),
#         radius=50,
#         color='blue',
#         fill=True,
#         fill_color='blue',
#         fill_opacity=0.1,
#         popup="5000 meter radius"
#     )
#     circle_marker.add_to(m)

#     geojson_data = fetch_geojson()
#     folium.GeoJson(geojson_data, name='geojson_layer').add_to(m)


#     folium_static(m, width=800)
    
    

# # try:
    
#     cliked_lat = st_data["last_clicked"]['lat']
#     clicked_lon = st_data["last_clicked"]['lng']
    
#     folium.Marker(location=(cliked_lat, clicked_lon), popup="Central Point").add_to(m)

#     # Create a CircleMarker to represent the distance
#     circle_marker = folium.CircleMarker(
#         location=(cliked_lat, clicked_lon),
#         radius=5000,
#         color='blue',
#         fill=True,
#         fill_color='blue',
#         fill_opacity=0.2,
#         popup="5000 meter radius"
#     )
#     circle_marker.add_to(m)
#     with placeholder.container():
#         st_folium(m, width=800, height = 500)
# try:
#     placeholder.empty()
#     st.info('Click a point on the map to get started', icon="ℹ️")
#     with placeholder.container():
#         st_folium(m, width=800)
# except:
#     pass




