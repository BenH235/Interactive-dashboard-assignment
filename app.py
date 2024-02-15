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


# Utility functions
def miles_to_meters(miles):
    '''
    Convert miles to meters
    Args:
        miles (float): Distance in miles
    Returns:
        float: Distance in meters
    '''
    return miles * 1609.34

def distance_from_poly(polygon, start_lat, start_lon):
    '''
    Find distance from point to polygon centroid
    Args
        Polygon: Shape from which centroid will be calculated
        start_lat (float): Latitude
        start_lon (float): Longitude
    Returns
        float: Haversine distance
    '''
    end_lat = polygon.centroid.y
    end_lon = polygon.centroid.x
    return round(haversine((start_lat, start_lon), (end_lat, end_lon), unit=Unit.MILES), 2)

def dataframe_with_selections(df):
    '''
    Create dataframe with selection column
    Args
        df (pandas.DataFrame): Input dataframe
    Returns
        pandas.DataFrame: With addition "Show weather forecast" column.
    '''
    df_with_selections = df.copy()
    df_with_selections.insert(0, "Show weather forecast", False)
    df_with_selections.loc[0, "Show weather forecast"] = True

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

# Function to bring in LNR geoJSON data
@st.cache_data
def fetch_geojson():
    url = 'https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/Local_Nature_Reserves_England/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson'
    r = requests.get(url)
    gdf = gpd.GeoDataFrame.from_features(r.json()["features"], crs='EPSG:4326')
    return gdf


# Streamlit application 
st.set_page_config(page_title='Local Nature Reserve Finder', 
                   layout='wide', 
                  )

st.title('Local Nature Reserve Finder')
st.caption("Local Nature Reserves (LNRs) are designated areas for conservation and enjoyment of nature \
within the local community. They provide natural habitats for wildlife and offer people the opportunity to learn, study, and enjoy nature \
(find more information [here](https://naturalengland-defra.opendata.arcgis.com/datasets/Defra::local-nature-reserves-england/about)).\nThis application helps you find the location of nearby LNRs (within a certain travelling distance). \
In addition to highlighting nearby reserves, a five-day weather forecast at each local site is also provided in order to help make a more informed decision on which reserve to visit.")

with st.expander("**Application instructions**"):
    st.write('''
        **Step 1.** Input valid UK postcode (note, this application only shows nature reserves in England).\n
        **Step 2.** Specify maximum travelling distance (this will be "as the crow flies" distance) from postcode to a nature reserve (in miles).\n
        **Step 3.** Select type of weather forecast to show for each reserve (this can be temperature, chance of precipitation or wind speed).\n
        **Step 4.** (Optional) Change the base map, this can be adjusted to make the nature reserves more visible.\n
        **Step 5.** Press the 'Confirm' button.\n
        Once these inputs have been specified and the 'Confirm' button clicked, you can visualise local reserves on the output map. In addition to an interactive map, the following breakdown is also supplied:\n
        * A table showing the reserves within the distance threshold (ordered by locality), which can be downloaded to CSV.
        * A five-day weather forecast on temperature, precipitation and wind speed.
    ''')

# Bring in LNR data
gdf = fetch_geojson()

# User settings
postcode_settings, distance_settings, weather_settings, map_settings, run_button = st.columns((2, 2, 2, 2, 1))
# Position button below empty space
run_button.write('')
postcode = postcode_settings.text_input('Enter valid UK postcode', value="", 
max_chars=None, 
key=None, 
type="default", 
help=None)
distance_miles = distance_settings.number_input('Enter maximum travel distance (* **in miles** *)', 
min_value=0, 
max_value=100, 
value=15)
map_type = map_settings.selectbox(label ='Change basemap (* **optional** *)', options = [
    'OpenStreetMap',
    'cartodbpositron',
    'Cartodb dark_matter'
], index=0)
# User input type of weather
weather_type = weather_settings.selectbox(label = 'Select weather feature', options = ['Tempurature (°C)', 
'Chance of precipitation (%)', 'Wind speed (mph)'], index=0)


# setting lat/lon based on postcode 
try:
    loc = requests.get(f'https://api.postcodes.io/postcodes/{postcode}').json()
    lat = loc['result']['latitude']
    lon = loc['result']['longitude']
    postcode_entered = True
except:
    st.warning('Please enter valid postcode to use this application', icon="⚠️")
    postcode_entered = False

# Split streamlit app into two columns
mapping, information = st.columns((3, 2))

# Setting session_state for button
if st.button('Confirm', use_container_width=True):
    session_state.button_clicked = True

# Only running code once postcode has been entered
if postcode_entered and session_state.button_clicked:

    # Get distance from postcode to each polygon
    gdf['distance'] = gdf['geometry'].apply(distance_from_poly, args=(lat, lon))
    # Check distance within specified distance
    _nearby_parks = gdf[gdf['distance'] <= distance_miles]

    if len(_nearby_parks) == 0:
        st.error('No nature reserves found near postcode. Please increase travelling distance and ensure postcode resides in England.', icon="🚨")
    else:

        with st.spinner('Loading...'):
            # Filter datafram 
            nearby_parks = _nearby_parks[['LNR_NAME', 'distance']].rename(columns  = \
            {'LNR_NAME': 'Name', 'distance':'distance (miles)'})

            # Further information in app (local reserves table)
            with information:
                # Dataframe
                st.subheader("Local nature reserves", help='Downloadable table showing sites within distance threshold (ordered by locality). Check boxes in the "Show weather forecast" column if you wish visualise the weather forecast for the chosen sites below (by default, the weather for the closest reserve is selected). Note, you can check multiple sites to compare the forecast across different LNRs.')
                selection = dataframe_with_selections(nearby_parks.sort_values(by = 'distance (miles)', 
                ascending = True).reset_index(drop=True))

            # Folium map
            m = folium.Map(tiles=map_type, location=(lat, lon), zoom_start=9.5)
            # Add marker
            folium.Marker(location=(lat, lon), popup=f"{postcode}").add_to(m)
            # Convert distance to meters
            radius_miles = miles_to_meters(distance_miles)
            # Define circle around marker
            circle_marker = folium.Circle(
            location=(lat, lon),
            radius=radius_miles,
            color='grey',
            fill=False,
            dash_array='3',  # Set dash_array for a dotted line
            popup=f"{distance_miles} radius",
            z_index=0
            )
            # Define popup over polygons
            popup = folium.GeoJsonPopup(
                fields=["LNR_NAME", 'distance'],
                aliases=["Name", 'Distance (in miles)'],
                localize=True,
                labels=True,
                style="background-color: yellow;",
            )
            tooltip = folium.GeoJsonTooltip(
                fields=["LNR_NAME"],
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
            condition = lambda feature: '#3776ab' if feature['properties']['LNR_NAME'] in selection['Name'].to_list() else 'indianred'

            # Add polygons
            folium.GeoJson(gdf.to_json(), name='geojson_layer', 
                tooltip=tooltip,
                popup=popup, style_function=lambda feature: {
                    'fillColor': condition(feature),
                    'fillOpacity': 0.9,
                    'color': 'grey',
                    'weight': 0.1
                },).add_to(m)

            # Add circle
            circle_marker.add_to(m)
            # Add layer control
            folium.LayerControl().add_to(m)

            # Add map to app 
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
                st.subheader('Mapping nature reserves', help='If the nature reserves are difficult to spot, try changing the basemap in the above settings. The shaded areas represent nature reserves (blue for reserves with "Show weather forecast" rows checked in the right hand table and all other reserves are shaded red). If colours are difficult to differentiate, hovering over the shaded region will show the name of the site.', divider='green')
                st.caption('The dashed circle represents the threshold travel distance (centered at the input postcode). Hover over a nature reserve (shaded regions on the map) to show the name of the reserve. The map is interactive, so feel free to change the zoom or use your mouse to click and drag inside the map to explore other nature reserves.')
                # Display the map
                folium_static(m, width=1000,height=650)

            # Get lat/lon list of LNR's within distance threshold
            locations = gdf[gdf.LNR_NAME.isin(selection.Name.to_list())]['geometry'].centroid.to_list()

            # Get weather data for selected locations
            conn = datapoint.connection(api_key=st.secrets['API_KEY'])
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

            # Add plotly figure showing weather
            fig = px.line(forecast_df, x ='date', y=weather_type, color='location')
            fig.update_layout(template = 'seaborn', 
            title = f'Five day weather forecast: {weather_type}', 
            xaxis_title='',
            yaxis_title = f'{weather_type}',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.3,
                xanchor="right",
                x=1
            ))
            # Add Plotly graph to app
            information.plotly_chart(fig, use_container_width=True)
            information.caption('Forecasts are provided at 12am and 12pm for the next 5 days and are updated hourly. For more information on the forecasts [click here](https://www.metoffice.gov.uk/services/data/datapoint/api-reference).')





