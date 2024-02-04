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
    '''
    Convert miles to meters
    '''
    return miles * 1609.34

def distance_from_poly(polygon, start_lat, start_lon):
    '''
    Find distance from point to polygon centroid
    '''
    end_lat = polygon.centroid.y
    end_lon = polygon.centroid.x
    return haversine((start_lat, start_lon), (end_lat, end_lon), unit=Unit.MILES)

def dataframe_with_selections(df):
    '''
    Create dataframe with selection column
    '''
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

# Function to bring in NNR data
@st.cache_data
def fetch_geojson():
    url = 'https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/National_Nature_Reserves_England/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson'
    r = requests.get(url)
    gdf = gpd.GeoDataFrame.from_features(r.json()["features"], crs='EPSG:4326')
    return gdf

# Streamlit application 
st.set_page_config(page_title='Local Nature Reserve Finder', 
                   layout='wide', 
                  )

st.title('Local Nature Reserve Finders')
st.caption("Natural England’s National Nature Reserves (NNR) are designated areas that are managed and conserved to protect and enhance some of the most important habitats, species and geology (see more [here](https://www.gov.uk/government/collections/national-nature-reserves-in-england#:~:text=National%20Nature%20Reserves%20(%20NNRs%20)%20were,'outdoor%20laboratories'%20for%20research.)).\nThis app helps you find local NNR relative to a postcode you can specify. The distance is then calculated (as the crow flies) and suggests reserves that are within distances you can specify.")

with st.expander("Expand to see instructions on using this application"):
    st.write('''
        Guidlines on using this app:\n
        1. Input valid UK postcode.\n
        2. Specify distance from postcode to travel to a NNR (this is as the crow flies distance).\n
        3. Visualise the reserve on the map. In addition to the map, the following breakdown is also supplied:\n
            *(i)* A table for local NNR (ordered by locality), alongside other information (downloadable to CSV).\n
            *(ii)* A five day weather forecast (provided by the Met Office) on temperature, precipitation and wind speed, to make informed decision of which reserve to visit.
    ''')

# An application that helps you find local nature reserves in England. The application suggests a reserve based on locality and short term weather forecasts.')

# Bring in NNR data
gdf = fetch_geojson()

# Split streamlit app into two columns
mapping, information = st.columns((3, 2))

# First column, user settings
postcode_settings, distance_settings, map_settings = mapping.columns(3)

postcode = postcode_settings.text_input('Please enter valid UK postcode', value="", max_chars=None, key=None, type="default", help=None)
distance_miles = distance_settings.number_input('Please enter distance (in miles) from postcode', min_value=0, max_value=100, value=15)
map_type = map_settings.selectbox(label ='Select basemap', options = [
    'OpenStreetMap',
    'cartodbpositron',
    'Cartodb dark_matter'

], index=0)

try:
    loc = requests.get(f'https://api.postcodes.io/postcodes/{postcode}').json()
    lat = loc['result']['latitude']
    lon = loc['result']['longitude']
    postcode_entered = True
except:
    st.warning('Please enter valid postcode to use this application', icon="⚠️")
    postcode_entered = False


if postcode_entered:

    gdf['distance'] = gdf['geometry'].apply(distance_from_poly, args=(lat, lon))
    nearby_parks = gdf[gdf['distance'] <= distance_miles]

    nearby_parks = nearby_parks[['NNR_NAME', 'distance', 'Shape__Area']].rename(columns  = {'NNR_NAME': 'Name', 'distance':'distance (miles)',  'Shape__Area': 'Land area'})


    m = folium.Map(tiles=map_type, location=(lat, lon), zoom_start=9)
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

    )
    # condition = lambda feature: 'blue' if feature['properties']['distance']<distance_miles else 'red'

    folium.GeoJson(gdf.to_json(), name='geojson_layer', 
        tooltip=tooltip,
        popup=popup, style_function=lambda feature: {
            'fillColor': 'indianred',
            'fillOpacity': 0.9,
            'color': 'grey',
            'weight': 0.1
        },).add_to(m)


    circle_marker.add_to(m)

    folium.LayerControl().add_to(m)

    with mapping:
        # ref: https://github.com/gee-community/geemap/issues/713
        st.markdown("""
                <style>
                iframe {
                    width: 100%;
                    min-height: 400px;
                    height: 100%:
                }
                </style>
                """, unsafe_allow_html=True)

        # Display the map
        folium_static(m, width=1000,height=650)

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
        wind_list = []
        for day in forecast.days:

            # Loop through time steps and print out info
            for timestep in day.timesteps:
                date_list.append(timestep.date)
                text_list.append(timestep.weather.text)
                temp_list.append(timestep.temperature.value)
                prec_list.append(timestep.precipitation.value)
                wind_list.append(timestep.wind_speed.value)
                
        forecast_df=pd.DataFrame()
        forecast_df['date']=date_list
        forecast_df['text']=text_list
        forecast_df['Tempurature (°C)']=temp_list
        forecast_df['Chance of precipitation (%)']=prec_list
        forecast_df['Wind speed (mph)']=wind_list
        forecast_df['location'] = name

        locs_forecast.append(forecast_df)

    forecast_df = pd.concat(locs_forecast)

    weather_type = information.radio('Select weather feature', ['Tempurature (°C)', 'Chance of precipitation (%)', 'Wind speed (mph)'], index=0, horizontal=True)


    fig = px.line(forecast_df, x ='date', y=weather_type, color='location')
    fig.update_layout(template = 'seaborn', 
    title = 'Five day weather forecast', 
    xaxis_title='',
    yaxis_title = f'{weather_type}',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.6,
        xanchor="right",
        x=1
    ))
    information.plotly_chart(fig, use_container_width=True)





