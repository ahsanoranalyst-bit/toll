import streamlit as st
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz
import requests
import polyline

st.set_page_config(page_title="Pro Dispatcher: Smart Route & Toll AI", layout="wide")

# Fixed Toll Database (Safe Maximum Estimates for Negotiation)
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

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'calculate_pressed' not in st.session_state:
    st.session_state['calculate_pressed'] = False

def get_us_zone_name(tz_string):
    if "Puerto_Rico" in tz_string or "Halifax" in tz_string: return "Zone 1 (AST)"
    elif "New_York" in tz_string or "Detroit" in tz_string or "Indiana" in tz_string or "Eastern" in tz_string: return "Zone 2 (EST)"
    elif "Chicago" in tz_string or "Knox" in tz_string or "Central" in tz_string: return "Zone 3 (CST)"
    elif "Denver" in tz_string or "Phoenix" in tz_string or "Boise" in tz_string or "Mountain" in tz_string: return "Zone 4 (MST)"
    elif "Los_Angeles" in tz_string or "Pacific" in tz_string: return "Zone 5 (PST)"
    elif "Anchorage" in tz_string or "Juneau" in tz_string: return "Zone 6 (AKST)"
    elif "Honolulu" in tz_string: return "Zone 7 (HST)"
    else: return f"Unknown Zone"

def get_time_zone_info(lat, lon):
    try:
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lng=lon, lat=lat)
        if tz_name:
            tz = pytz.timezone(tz_name)
            current_time = datetime.now(tz).strftime('%I:%M %p')
            zone_number = get_us_zone_name(tz_name)
            return zone_number, current_time
        return "Unknown", "N/A"
    except:
        return "Unknown", "N/A"

def get_actual_route(coordinates):
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full"
    try:
        response = requests.get(url).json()
        if response.get("code") == "Ok":
            route = response["routes"][0]
            route_geometry = polyline.decode(route['geometry'])
            total_miles = route['distance'] * 0.000621371
            return route_geometry, total_miles
    except:
        pass
    return None, 0

if not st.session_state['logged_in']:
    st.title("🔒 Pro Dispatcher Login")
    with st.form("login_form"):
        if st.form_submit_button("Secure Login"):
            st.session_state['logged_in'] = True
            st.rerun()

else:
    st.title("🚛 Smart Route, Zone & Negotiation Toll AI")
    
    st.sidebar.header("📍 Route Setup")
    origin = st.sidebar.text_input("1. Parked At (Origin)", "Cincinnati, OH")
    waypoint = st.sidebar.text_input("2. Pickup Stop", "Marion, IN")
    destination = st.sidebar.text_input("3. Final Delivery", "Eugene, OR")

    if st.sidebar.button("Calculate Data"):
        st.session_state['calculate_pressed'] = True

    if st.session_state['calculate_pressed']:
        geolocator = Nominatim(user_agent="smart_dispatcher_v3")
        locations_data = []
        coordinates = []
        states_visited = set()
        
        with st.spinner("Analyzing routes, zones, and toll risk..."):
            for loc_name in [origin, waypoint, destination]:
                if loc_name.strip():
                    try:
                        loc = geolocator.geocode(loc_name, addressdetails=True)
                        if loc:
                            lat, lon = loc.latitude, loc.longitude
                            coordinates.append((lat, lon))
                            
                            state = loc.raw.get('address', {}).get('state')
                            if state: states_visited.add(state)
                                
                            zone_name, current_time = get_time_zone_info(lat, lon)
                            locations_data.append({"Query": loc_name, "Zone": zone_name, "Time": current_time})
                    except: pass

        if len(coordinates) >= 2:
            route_geometry, total_miles = get_actual_route(coordinates)
            
            # Hybrid Toll Calculation
            total_toll = sum(STATE_TOLLS[s] for s in states_visited if s in STATE_TOLLS)
            
            col1, col2 = st.columns([1.2, 1.8])
            
            with col1:
                st.metric(label="🛣️ Total Route Distance", value=f"{total_miles:,.1f} Miles")
                
                st.markdown("---")
                if total_toll > 0:
                    st.error(f"💰 Broker Negotiation Toll: ${total_toll:.2f}")
                    st.write("⚠️ **Risk States Detected:**", ", ".join([s for s in states_visited if s in STATE_TOLLS]))
                    st.info("💡 **پرو ٹپ:** بروکر سے ریٹ فائنل کرتے وقت اس اماؤنٹ کو اپنے ذہن میں رکھیں تاکہ آپ کا نقصان نہ ہو۔")
                else:
                    st.success("✅ Commercial Toll-Free Route")
                    st.write("اس روٹ کی مین لوکیشنز پر کوئی بھاری ٹول اسٹیٹ نہیں ہے۔")

                st.markdown("---")
                st.markdown("### ⏱️ Truck Zone Tracking")
                for idx, data in enumerate(locations_data):
                    status = "🅿️ Origin" if idx == 0 else "📦 Pickup" if idx == 1 and len(locations_data)==3 else "🚚 Delivery"
                    st.markdown(f"**{status}:** {data['Query']}  \n➤ `{data['Zone']}` (Local: {data['Time']})")

            with col2:
                m = folium.Map(location=coordinates[0], zoom_start=5)
                if route_geometry: folium.PolyLine(route_geometry, color="red", weight=5).add_to(m)
                else: folium.PolyLine(coordinates, color="blue", weight=3).add_to(m)
                
                for i, coord in enumerate(coordinates):
                    folium.Marker(location=coord, icon=folium.Icon(color="green" if i==0 else "red" if i==len(coordinates)-1 else "orange")).add_to(m)
                st_folium(m, width=800, height=550, returned_objects=[])
