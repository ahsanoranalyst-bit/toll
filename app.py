import streamlit as st
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz
import requests
import polyline

st.set_page_config(page_title="Pro Dispatcher | Smart Toll & Route AI", layout="wide")

# Exact Per-Mile Rates based on Vehicle Type
VEHICLE_RATES = {
    "Car, SUV or Pickup truck": 0.08,
    "Truck - 2 Axles": 0.15,
    "Truck - 3 Axles": 0.25,
    "Truck - 4 Axles": 0.35,
    "Truck - 5 Axles": 0.45,   # Standard Baseline
    "Truck - 6 Axles": 0.55,
    "Truck - 7 Axles": 0.65,
    "Truck - 8 Axles": 0.75,
    "Truck - 9 Axles": 0.85,
    "Bus": 0.30
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

def get_route_data(coordinates):
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

# --- UI DASHBOARD ---

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
                st.error("Authentication Failed.")

else:
    st.title("🚛 Dynamic Mileage, Toll & Zone Intelligence")
    
    st.sidebar.header("⚙️ Vehicle Configuration")
    vehicle_type = st.sidebar.selectbox("Select Vehicle Type", list(VEHICLE_RATES.keys()), index=4) 
    
    st.sidebar.markdown("---")
    st.sidebar.header("🛣️ Toll Route Control")
    st.sidebar.write("Adjust how much of this route is on Toll Highways:")
    toll_percentage = st.sidebar.slider("Toll Road Percentage (%)", min_value=0, max_value=100, value=15, step=5)
    
    st.sidebar.markdown("---")
    st.sidebar.header("📍 Itinerary Setup")
    origin = st.sidebar.text_input("1. Origin", "Cincinnati, OH")
    waypoint = st.sidebar.text_input("2. Pickup Stop", "Marion, IN")
    destination = st.sidebar.text_input("3. Final Delivery", "Cincinnati, OH")

    if st.sidebar.button("Generate Dispatch Data"):
        st.session_state['calculate_pressed'] = True

    st.sidebar.markdown("---")
    if st.sidebar.button("Log Out"):
        st.session_state['logged_in'] = False
        st.session_state['calculate_pressed'] = False
        st.rerun()

    if st.session_state['calculate_pressed']:
        geolocator = Nominatim(user_agent="pro_dispatcher_v7")
        locations_data = []
        coordinates = []
        
        with st.spinner("Calculating live mileage, zones, and dynamic toll algorithms..."):
            for loc_name in [origin, waypoint, destination]:
                if loc_name.strip():
                    try:
                        loc = geolocator.geocode(loc_name, addressdetails=True)
                        if loc:
                            lat, lon = loc.latitude, loc.longitude
                            coordinates.append((lat, lon))
                            zone_name, current_time = get_time_zone_info(lat, lon)
                            locations_data.append({"Query": loc_name, "Zone": zone_name, "Time": current_time})
                    except:
                        pass

        if len(coordinates) >= 2:
            route_geometry, total_miles = get_route_data(coordinates)
            
            # --- NEW SMART TOLL LOGIC ---
            rate_per_mile = VEHICLE_RATES[vehicle_type]
            calculated_toll = total_miles * rate_per_mile * (toll_percentage / 100.0)
            
            col1, col2 = st.columns([1.2, 1.8])
            
            with col1:
                st.metric(label="🛣️ Total Route Distance", value=f"{total_miles:,.1f} Miles")
                st.write(f"**Equipment:** `{vehicle_type}`")
                st.markdown("---")
                
                if calculated_toll > 0:
                    st.error(f"💰 Dynamic Estimated Toll: ${calculated_toll:.2f}")
                    st.markdown(f"**How was this calculated? (For Carrier/Broker)**")
                    st.code(f"({total_miles:.1f} Miles × ${rate_per_mile:.2f}/mile) × {toll_percentage}% Toll Route = ${calculated_toll:.2f}")
                    st.info("💡 **Negotiation Strategy:** Use the calculation above to justify the toll cost to your carrier or broker.")
                else:
                    st.success("✅ Estimated Toll Cost: $0.00")
                    st.write("Toll percentage is set to 0%. This route is marked as completely toll-free.")

                st.markdown("---")
                st.markdown("### ⏱️ Logistics Zone Tracking")
                for idx, data in enumerate(locations_data):
                    status = "🅿️ Origin" if idx == 0 else "📦 Pickup" if idx == 1 and len(locations_data)==3 else "🚚 Delivery"
                    st.markdown(f"**{status}:** {data['Query']}  \n➤ `{data['Zone']}` (Local: {data['Time']})")

            with col2:
                m = folium.Map(location=coordinates[0], zoom_start=6)
                if route_geometry: 
                    folium.PolyLine(route_geometry, color="red", weight=5, opacity=0.8).add_to(m)
                else: 
                    folium.PolyLine(coordinates, color="blue", weight=3).add_to(m)
                
                for i, coord in enumerate(coordinates):
                    folium.Marker(location=coord, icon=folium.Icon(color="green" if i==0 else "red" if i==len(coordinates)-1 else "orange")).add_to(m)
                st_folium(m, width=800, height=600, returned_objects=[])
