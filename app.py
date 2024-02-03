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


# Utility functions
def miles_to_meters(miles):
    return miles * 1609.34

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

mapping, information = st.columns((3, 2))

first_input, second_input, third_input = mapping.columns(3)
postcode = first_input.text_input('Please enter valid postcode', value="", max_chars=None, key=None, type="default", help=None)
distance_miles = second_input.number_input('Please enter distance (in miles)', min_value=0, max_value=100, value=15)
map_settings = third_input.expander('Map settings', expanded=False)

map_width= map_settings.slider(label = 'Modify map width', min_value=500, max_value=3000, value=1000)
map_height = map_settings.slider(label = 'Modify map height', min_value=500, max_value=3000, value=600)
base_map = map_settings.selectbox(label ='Select basemap', options = ['OpenStreetMap', 'CartoDB Positron', 'CartoBD Voyager', 'NASAGIBS Blue Marble'], index=0)

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
    df_with_selections.loc[0, "Show weather forecast"] = True

    # Get dataframe row-selections from user with st.data_editor
    edited_df = st.data_editor(
        df_with_selections,
        hide_index=True,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=df.columns,
        use_container_width=True,
        height = 220
        
    )

    # Filter the dataframe using the temporary column, then drop the column
    selected_rows = edited_df[edited_df["Show weather forecast"]]
    return selected_rows.drop("Show weather forecast", axis=1)
    

gdf['distance'] = gdf['geometry'].apply(distance_from_poly)
nearby_parks = gdf[gdf['distance'] <= distance_miles]

nearby_parks = nearby_parks[['NNR_NAME', 'distance', 'Shape__Area']].rename(columns  = {'NNR_NAME': 'Name', 'distance':'distance (miles)',  'Shape__Area': 'Land area'})


m = folium.Map(tiles=base_map, location=(lat, lon), zoom_start=9)
folium.Marker(location=(lat, lon), popup="Central Point").add_to(m)

radius_miles = miles_to_meters(distance_miles)

# Create a CircleMarker to represent the distance
circle_marker = folium.Circle(
    location=(lat, lon),
    radius=radius_miles,
    color='green',
    fill=False,
    dash_array='3',  # Set dash_array for a dotted line
    popup=f"{distance_miles} radius",
    z_index=0
)

popup = folium.GeoJsonPopup(
    fields=["NNR_NAME", 'distance'],
    aliases=["Name", 'Distance (in miles)'],
    localize=True,
    labels=True,
    style="background-color: yellow;",
)
tooltip = folium.GeoJsonTooltip(
    fields=["NNR_NAME"],
    aliases=["Name"],
    localize=True,
    sticky=False,
    labels=True,
    style="""
        background-color: #F0EFEF;
        border: 2px solid black;
        border-radius: 3px;
        box-shadow: 3px;
    """,
    max_width=800,
)
condition = lambda feature: 'blue' if feature['properties']['distance']<distance_miles else 'red'

folium.GeoJson(gdf.to_json(), name='geojson_layer', 
    tooltip=tooltip,
    popup=popup, style_function=lambda feature: {
        'fillColor': condition(feature),
        'fillOpacity': 0.9,
        'color': 'grey',
        'weight': 0.1
    },).add_to(m)


circle_marker.add_to(m)

folium.LayerControl().add_to(m)

with mapping:
    folium_static(m, width=int(map_width),height=int(map_height))



with information:
    selection = dataframe_with_selections(nearby_parks.sort_values(by = 'distance (miles)', ascending = True).reset_index(drop=True))

locations = gdf[gdf.NNR_NAME.isin(selection.Name.to_list())]['geometry'].centroid.to_list()

# Get weather data for selected locations
# Create connection to DataPoint with your API key
conn = datapoint.connection(api_key=API_KEY)


locs_forecast = []
for locs, name in zip(locations, selection.Name.to_list()):
# Get the nearest site for my latitude and longitude
    site = conn.get_nearest_forecast_site(locs.y, locs.x)

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
    forecast_df['location'] = name

    locs_forecast.append(forecast_df)

forecast_df = pd.concat(locs_forecast)

fig = px.line(forecast_df, x ='date', y='tempurature', color='location')
information.plotly_chart(fig, use_container_width=True)





