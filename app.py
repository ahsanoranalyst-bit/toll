import streamlit as st
import folium
from streamlit_folium import st_folium
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz
import polyline
import googlemaps

st.set_page_config(page_title="Pro Dispatcher | Google Powered AI", layout="wide")

# ==========================================
# 🛑 GOOGLE MAPS API KEY 🛑
# اپنی گوگل اے پی آئی کی (API Key) نیچے انورٹڈ کوماز کے اندر پیسٹ کریں
GOOGLE_MAPS_API_KEY = "AIzaSyDJ1rZSieOtWsqs4xpOz5R1dtFtY32I7aU"
# ==========================================

# Baseline Maximum Tolls for a standard 5-Axle Truck
STATE_TOLLS_5_AXLE = {
    "Ohio": 75.00, "Indiana": 65.00, "Illinois": 45.00, "Pennsylvania": 150.00,
    "New York": 90.00, "New Jersey": 60.00, "West Virginia": 25.00, 
    "Kentucky": 15.00, "Florida": 40.00, "Texas": 50.00, "California": 30.00
}

# Vehicle Multipliers
VEHICLE_MULTIPLIERS = {
    "Car, SUV or Pickup truck": 0.15,
    "Truck - 2 Axles": 0.35, "Truck - 3 Axles": 0.55, "Truck - 4 Axles": 0.75,
    "Truck - 5 Axles": 1.00, "Truck - 6 Axles": 1.25, "Truck - 7 Axles": 1.50,
    "Truck - 8 Axles": 1.75, "Truck - 9 Axles": 2.00, "Bus": 0.60
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
            return get_us_zone_name(tz_name), current_time
        return "Unknown", "N/A"
    except:
        return "Unknown", "N/A"

# --- DASHBOARD UI ---

if not st.session_state['logged_in']:
    st.title("🔒 Pro Dispatcher Access Portal")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Secure Login"):
            if username == "admin" and password == "admin123":
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("Invalid credentials. Access Denied.")

else:
    st.title("🚛 Automated Route & Toll AI (Google Powered)")
    
    if GOOGLE_MAPS_API_KEY == "YOUR_API_KEY_HERE" or not GOOGLE_MAPS_API_KEY:
        st.warning("⚠️ **System Alert:** Please enter your Google Maps API Key in the `app.py` code to unlock live routing.")
    
    st.sidebar.header("⚙️ Equipment Configuration")
    vehicle_type = st.sidebar.selectbox("Select Vehicle Type (Axles)", list(VEHICLE_MULTIPLIERS.keys()), index=4) 
    
    st.sidebar.markdown("---")
    st.sidebar.header("📍 Itinerary Setup")
    origin = st.sidebar.text_input("1. Origin / Truck Location", "Cincinnati, OH")
    waypoint = st.sidebar.text_input("2. Pickup Stop (Optional)", "Marion, IN")
    destination = st.sidebar.text_input("3. Final Destination", "Eugene, OR")

    if st.sidebar.button("Generate Dispatch Data"):
        st.session_state['calculate_pressed'] = True

    st.sidebar.markdown("---")
    if st.sidebar.button("Log Out"):
        st.session_state['logged_in'] = False
        st.session_state['calculate_pressed'] = False
        st.rerun()

    if st.session_state['calculate_pressed'] and GOOGLE_MAPS_API_KEY != "YOUR_API_KEY_HERE":
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        locations_data = []
        coordinates = []
        states_visited = set()
        
        with st.spinner("Connecting to Google Maps API for precise routing and toll analysis..."):
            try:
                # 1. Geocoding via Google Maps
                for loc_name in [origin, waypoint, destination]:
                    if loc_name.strip():
                        geocode_result = gmaps.geocode(loc_name)
                        if geocode_result:
                            lat = geocode_result[0]['geometry']['location']['lat']
                            lon = geocode_result[0]['geometry']['location']['lng']
                            coordinates.append((lat, lon))
                            
                            # Extract State
                            for component in geocode_result[0]['address_components']:
                                if 'administrative_area_level_1' in component['types']:
                                    states_visited.add(component['long_name'])
                            
                            zone_name, current_time = get_time_zone_info(lat, lon)
                            locations_data.append({"Query": loc_name, "Zone": zone_name, "Time": current_time})

                if len(coordinates) >= 2:
                    # 2. Directions via Google Maps
                    waypoints_param = [waypoint] if waypoint.strip() else None
                    directions_result = gmaps.directions(origin, destination, waypoints=waypoints_param, mode="driving")
                    
                    if directions_result:
                        route = directions_result[0]
                        overview_polyline = route['overview_polyline']['points']
                        route_geometry = polyline.decode(overview_polyline)
                        
                        # Calculate accurate Total Miles from Google
                        total_meters = sum(leg['distance']['value'] for leg in route['legs'])
                        total_miles = total_meters * 0.000621371
                        
                        # --- SMART TOLL ALGORITHM ---
                        calculated_toll = 0.0
                        if total_miles < 50.0:
                            toll_reason = "✅ Local trip under 50 miles detected. Marked as Toll-Free."
                        else:
                            base_state_toll = sum(STATE_TOLLS_5_AXLE[s] for s in states_visited if s in STATE_TOLLS_5_AXLE)
                            distance_factor = min(1.0, total_miles / 600.0)
                            vehicle_multiplier = VEHICLE_MULTIPLIERS[vehicle_type]
                            calculated_toll = base_state_toll * distance_factor * vehicle_multiplier
                            toll_reason = f"⚠️ Calculated based on a {total_miles:.1f} mile route utilizing {vehicle_type} rates."

                        col1, col2 = st.columns([1.2, 1.8])
                        
                        with col1:
                            st.metric(label="🗺️ Exact Google Route Mileage", value=f"{total_miles:,.1f} Miles")
                            st.write(f"**Equipment Profile:** `{vehicle_type}`")
                            st.markdown("---")
                            
                            if calculated_toll > 0:
                                st.error(f"💰 Automated Dynamic Toll: ${calculated_toll:.2f}")
                                st.write(f"ℹ️ **AI Analysis:** {toll_reason}")
                                st.info("💡 **Broker Quote Tip:** Factor this automated estimate directly into your flat-rate negotiation.")
                            else:
                                st.success("✅ Automated Dynamic Toll: $0.00")
                                st.write(f"ℹ️ **AI Analysis:** {toll_reason}")

                            st.markdown("---")
                            st.markdown("### ⏱️ Logistics Zone Tracking")
                            for idx, data in enumerate(locations_data):
                                status = "🅿️ Origin" if idx == 0 else "📦 Pickup" if idx == 1 and len(locations_data)==3 else "🚚 Delivery"
                                st.markdown(f"**{status}:** {data['Query']}  \n➤ `{data['Zone']}` (Local Time: {data['Time']})")

                        with col2:
                            m = folium.Map(location=coordinates[0], zoom_start=5)
                            folium.PolyLine(route_geometry, color="#4285F4", weight=6, opacity=0.8).add_to(m)
                            
                            for i, coord in enumerate(coordinates):
                                folium.Marker(location=coord, icon=folium.Icon(color="green" if i==0 else "red" if i==len(coordinates)-1 else "orange")).add_to(m)
                            st_folium(m, width=800, height=600, returned_objects=[])
                    else:
                        st.error("Google Maps could not find a valid driving route between these locations.")
            except Exception as e:
                st.error(f"API Error: Please check your Google Maps API Key or location names. Details: {e}")
