import streamlit as st
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz
import requests
import polyline

# 1. Page Configuration
st.set_page_config(page_title="Pro Dispatcher: Smart Route & Toll AI", layout="wide")

# 2. Initialize Session States
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'calculate_pressed' not in st.session_state:
    st.session_state['calculate_pressed'] = False

# --- HELPER FUNCTIONS ---

# Function to map Timezone to standard US 9 Zones
def get_us_zone_name(tz_string):
    if "Puerto_Rico" in tz_string or "Halifax" in tz_string:
        return "Zone 1 (Atlantic Time - AST)"
    elif "New_York" in tz_string or "Detroit" in tz_string or "Indiana/Indianapolis" in tz_string or "Eastern" in tz_string:
        return "Zone 2 (Eastern Time - EST)"
    elif "Chicago" in tz_string or "Indiana/Knox" in tz_string or "Central" in tz_string:
        return "Zone 3 (Central Time - CST)"
    elif "Denver" in tz_string or "Phoenix" in tz_string or "Boise" in tz_string or "Mountain" in tz_string:
        return "Zone 4 (Mountain Time - MST)"
    elif "Los_Angeles" in tz_string or "Pacific" in tz_string:
        return "Zone 5 (Pacific Time - PST)"
    elif "Anchorage" in tz_string or "Juneau" in tz_string:
        return "Zone 6 (Alaska Time - AKST)"
    elif "Honolulu" in tz_string:
        return "Zone 7 (Hawaii-Aleutian Time - HST)"
    elif "Samoa" in tz_string:
        return "Zone 8 (Samoa Time - SST)"
    elif "Guam" in tz_string or "Saipan" in tz_string:
        return "Zone 9 (Chamorro Time - ChST)"
    else:
        return f"Unknown Zone ({tz_string})"

def get_time_zone_info(lat, lon):
    try:
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lng=lon, lat=lat)
        if tz_name:
            tz = pytz.timezone(tz_name)
            current_time = datetime.now(tz).strftime('%I:%M %p')
            zone_number = get_us_zone_name(tz_name)
            return zone_number, current_time
        return "Unknown Zone", "N/A"
    except:
        return "Unknown Zone", "N/A"

# Function to fetch actual highway route and dynamic toll via OSRM
def get_actual_route_and_toll(coordinates):
    # Format coordinates for OSRM: lon,lat;lon,lat...
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&steps=true&annotations=true"
    
    try:
        response = requests.get(url).json()
        if response.get("code") == "Ok":
            route = response["routes"][0]
            # Decode the geometry to draw exact highway paths
            route_geometry = polyline.decode(route['geometry'])
            
            # Calculate total miles
            total_miles = route['distance'] * 0.000621371
            
            # Detect Toll Roads exactly on the path
            toll_meters = 0
            for leg in route['legs']:
                for step in leg['steps']:
                    is_toll = False
                    if 'intersections' in step:
                        for intersection in step['intersections']:
                            if 'classes' in intersection and 'toll' in intersection['classes']:
                                is_toll = True
                                break
                    if is_toll:
                        toll_meters += step['distance']
            
            toll_miles = toll_meters * 0.000621371
            # Commercial 5-Axle average rate: $0.45 per mile on toll roads
            estimated_toll = toll_miles * 0.45 
            
            return route_geometry, total_miles, toll_miles, estimated_toll
    except Exception as e:
        pass
    
    return None, 0, 0, 0

# --- MAIN APP LOGIC ---

# 3. Login System
if not st.session_state['logged_in']:
    st.title("🔒 Pro Dispatcher Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Secure Login"):
            if username == "admin" and password == "admin123":
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("Access Denied.")

# 4. Main Dashboard
else:
    st.title("🚛 Smart Route, Zone & Dynamic Toll AI")
    
    st.sidebar.header("👤 Admin Account")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['calculate_pressed'] = False
        st.rerun()
        
    st.sidebar.markdown("---")
    
    st.sidebar.header("📍 Route Setup")
    origin = st.sidebar.text_input("1. Truck Parked At (Origin)", "Cincinnati, OH")
    waypoint = st.sidebar.text_input("2. Pickup Stop (Optional)", "Marion, IN")
    destination = st.sidebar.text_input("3. Final Delivery", "Eugene, OR")

    if st.sidebar.button("Calculate Exact Route"):
        st.session_state['calculate_pressed'] = True

    if st.session_state['calculate_pressed']:
        geolocator = Nominatim(user_agent="smart_dispatcher_tool")
        locations_data = []
        coordinates = []
        
        with st.spinner("Analyzing precise highways, toll steps, and Time Zones..."):
            for loc_name in [origin, waypoint, destination]:
                if loc_name and loc_name.strip():
                    try:
                        loc = geolocator.geocode(loc_name, addressdetails=True)
                        if loc:
                            lat, lon = loc.latitude, loc.longitude
                            coordinates.append((lat, lon))
                            
                            zone_name, current_time = get_time_zone_info(lat, lon)
                            
                            locations_data.append({
                                "Query": loc_name,
                                "Address": loc.address.split(',')[0],
                                "Zone": zone_name,
                                "Local Time": current_time
                            })
                    except Exception as e:
                        st.error(f"Could not find: {loc_name}")

        if len(coordinates) >= 2:
            # Get actual highway route and dynamic toll
            route_geometry, total_miles, toll_miles, total_toll = get_actual_route_and_toll(coordinates)
            
            col1, col2 = st.columns([1.2, 1.8])
            
            with col1:
                st.metric(label="🛣️ Total Route Distance", value=f"{total_miles:,.1f} Miles")
                
                # Dynamic Toll Logic
                if total_toll > 0:
                    st.error(f"💰 Dynamic Toll Estimate: ${total_toll:.2f}")
                    st.write(f"**Toll Road Driven:** {toll_miles:.1f} miles detected.")
                else:
                    st.success("✅ Dynamic Toll Estimate: $0.00")
                    st.write("This route does not cross any active toll highways!")
                
                st.markdown("---")
                st.markdown("### ⏱️ Truck Zone Tracking")
                for idx, data in enumerate(locations_data):
                    status = "🅿️ Parked At" if idx == 0 else "📦 Pickup At" if idx == 1 and len(locations_data)==3 else "🚚 Deliver To"
                    
                    st.markdown(f"**{status}: {data['Query']}**")
                    st.markdown(f"➤ **{data['Zone']}**")
                    st.markdown(f"➤ Local Time: `{data['Local Time']}`")

            with col2:
                st.subheader("🗺️ Exact Highway Map")
                m = folium.Map(location=coordinates[0], zoom_start=5)
                
                # Draw exact highway path if found
                if route_geometry:
                    folium.PolyLine(route_geometry, color="red", weight=5, opacity=0.8).add_to(m)
                else:
                    # Fallback to straight line if API fails
                    folium.PolyLine(coordinates, color="blue", weight=3, opacity=0.5).add_to(m)
                
                # Add descriptive markers
                for i, coord in enumerate(coordinates):
                    status = "Origin" if i == 0 else "Pickup" if i == 1 and len(coordinates)==3 else "Destination"
                    label = f"<b>{status}:</b> {locations_data[i]['Query']}<br><b>Zone:</b> {locations_data[i]['Zone']}"
                    
                    folium.Marker(
                        location=coord, 
                        popup=folium.Popup(label, max_width=300), 
                        tooltip=f"Click to see Zone for {status}",
                        icon=folium.Icon(color="green" if i==0 else "red" if i==len(coordinates)-1 else "orange", icon="info-sign")
                    ).add_to(m)
                
                st_folium(m, width=800, height=600, returned_objects=[])
        else:
            st.error("Please enter valid locations to calculate.")
