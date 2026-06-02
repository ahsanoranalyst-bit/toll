import streamlit as st
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz

# 1. Page Configuration
st.set_page_config(page_title="Pro Dispatcher: Route & Toll Calculator", layout="wide")

# 2. Fixed Toll Database (Max State Estimates)
STATE_TOLLS = {
    "Ohio": 75.00,
    "Indiana": 65.00,
    "Illinois": 45.00,
    "Pennsylvania": 150.00,
    "New York": 90.00,
    "New Jersey": 60.00,
    "West Virginia": 25.00,
    "Kentucky": 15.00
}

# 3. Initialize Session States
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'calculate_pressed' not in st.session_state:
    st.session_state['calculate_pressed'] = False

# Helper function to get readable Time Zone
def get_time_zone_info(lat, lon):
    try:
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lng=lon, lat=lat)
        if tz_name:
            tz = pytz.timezone(tz_name)
            current_time = datetime.now(tz).strftime('%I:%M %p')
            return tz_name, current_time
        return "Unknown", "N/A"
    except:
        return "Unknown", "N/A"

# 4. Login System
if not st.session_state['logged_in']:
    st.title("🔒 Dispatcher Portal Login")
    st.write("Please enter your admin credentials to securely access the routing tools.")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Secure Login")
        
        if submit_button:
            if username == "admin" and password == "admin123":
                st.session_state['logged_in'] = True
                st.success("Authentication successful! Loading dashboard...")
                st.rerun()
            else:
                st.error("Access Denied. Invalid credentials.")

# 5. Main Dashboard
else:
    st.title("🚛 Pro Dispatcher: Route, Map & Toll Calculator")
    st.markdown("Analyze routes, estimate max toll risks, and track **Time Zones** for accurate delivery planning.")

    # Sidebar Options
    st.sidebar.header("👤 Admin Account")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['calculate_pressed'] = False
        st.rerun()
        
    st.sidebar.markdown("---")
    
    st.sidebar.header("📍 Route Configuration")
    origin = st.sidebar.text_input("1. Start / Origin", "Cincinnati, OH")
    waypoint = st.sidebar.text_input("2. Pickup / Stop 1 (Optional)", "Marion, IN")
    destination = st.sidebar.text_input("3. Final Destination", "Eugene, OR")

    if st.sidebar.button("Calculate Route Data"):
        st.session_state['calculate_pressed'] = True

    # Main Processing Logic
    if st.session_state['calculate_pressed']:
        geolocator = Nominatim(user_agent="pro_dispatcher_tool")
        
        locations_data = []
        coordinates = []
        states_visited = set()
        
        # Geocode and fetch Time Zones
        with st.spinner("Processing route and time zones..."):
            for loc_name in [origin, waypoint, destination]:
                if loc_name and loc_name.strip():
                    try:
                        loc = geolocator.geocode(loc_name, addressdetails=True)
                        if loc:
                            lat, lon = loc.latitude, loc.longitude
                            coordinates.append((lat, lon))
                            
                            address = loc.raw.get('address', {})
                            state = address.get('state')
                            if state:
                                states_visited.add(state)
                                
                            # Fetch Timezone
                            tz_name, current_time = get_time_zone_info(lat, lon)
                            
                            locations_data.append({
                                "Query": loc_name,
                                "Full Address": loc.address.split(',')[0] + ", " + str(state),
                                "Time Zone": tz_name,
                                "Local Time": current_time
                            })
                    except Exception as e:
                        st.error(f"Error resolving location: {loc_name}")

        # Display Results
        if len(coordinates) >= 2:
            total_toll = 0.0
            detected_tolls = []
            
            for state in states_visited:
                if state in STATE_TOLLS:
                    total_toll += STATE_TOLLS[state]
                    detected_tolls.append(f"• {state}: ${STATE_TOLLS[state]:.2f}")
            
            col1, col2 = st.columns([1, 1.5])
            
            with col1:
                # Toll Information
                st.metric(label="💰 Max Estimated Toll Risk", value=f"${total_toll:.2f}")
                st.markdown("### 📋 State Breakdown")
                if total_toll == 0:
                    st.success("✅ Commercial toll-free route detected.")
                else:
                    st.warning("⚠️ Toll roads exist in these states. Max risk calculated.")
                    for item in detected_tolls:
                        st.write(item)
                
                st.info("💡 **Negotiation Tip:** Use this max estimate to request a higher flat rate from the broker.")
                
                st.markdown("---")
                # Time Zone Information
                st.markdown("### ⏱️ Time Zone Tracking")
                for idx, data in enumerate(locations_data):
                    st.markdown(f"**Stop {idx+1}: {data['Query']}**")
                    st.markdown(f"➤ **Zone:** `{data['Time Zone']}` (Local Time: {data['Local Time']})")

            with col2:
                # Live Map
                st.subheader("🗺️ Live Tracking Map")
                m = folium.Map(location=coordinates[0], zoom_start=5)
                
                for i, coord in enumerate(coordinates):
                    label = f"Stop {i+1}: {locations_data[i]['Query']}"
                    folium.Marker(
                        location=coord, 
                        popup=f"{label}<br>Zone: {locations_data[i]['Time Zone']}", 
                        tooltip=label,
                        icon=folium.Icon(color="darkblue", icon="info-sign")
                    ).add_to(m)
                
                folium.PolyLine(coordinates, color="blue", weight=4, opacity=0.7).add_to(m)
                
                st_folium(m, width=800, height=550, returned_objects=[])
        else:
            st.error("Insufficient data. Please provide at least an Origin and Destination.")
