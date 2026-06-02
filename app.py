import streamlit as st
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz
import requests
import polyline
from fpdf import FPDF

st.set_page_config(page_title="Pro Dispatcher | Toll & Route Intelligence", layout="wide")

# Baseline Maximum Tolls for specific heavy toll states
STATE_TOLLS_5_AXLE = {
    "Ohio": 75.00, "Indiana": 65.00, "Illinois": 45.00, "Pennsylvania": 150.00,
    "New York": 90.00, "New Jersey": 60.00, "West Virginia": 25.00,
    "Kentucky": 15.00, "Florida": 40.00, "Texas": 50.00, "California": 30.00
}

# Vehicle Multipliers based on Axles
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

# Helper function to generate PDF
def create_pdf(text_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    # Split by \r\n to process line by line
    for line in text_data.split('\r\n'):
        # Clean text for simple FPDF encoding
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(200, 7, txt=clean_line, ln=True)
    return pdf.output(dest='S').encode('latin-1')

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
    st.title("🚛 Route, Zone & Toll Intelligence System")
    st.write("Smart logistics dashboard. Fully automated toll risk and time zone tracking.")
    
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

    if st.session_state['calculate_pressed']:
        geolocator = Nominatim(user_agent="pro_dispatcher_final")
        locations_data = []
        coordinates = []
        states_visited = set()
        
        with st.spinner("System is analyzing highway geography, vehicle weights, and regional zones..."):
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
                    except:
                        pass

        if len(coordinates) >= 2:
            route_geometry, total_miles = get_route_data(coordinates)
            
            calculated_toll = 0.0
            if total_miles < 50.0:
                calculated_toll = 0.0
                toll_reason = "Local trip under 50 miles detected. Automatically marked as Toll-Free."
            else:
                base_state_toll = sum(STATE_TOLLS_5_AXLE[s] for s in states_visited if s in STATE_TOLLS_5_AXLE)
                distance_factor = min(1.0, total_miles / 600.0)
                vehicle_multiplier = VEHICLE_MULTIPLIERS[vehicle_type]
                calculated_toll = base_state_toll * distance_factor * vehicle_multiplier
                
                if calculated_toll > 0:
                    toll_reason = f"Calculated based on a {total_miles:.1f} mile route crossing toll-active regions for a {vehicle_type}."
                else:
                    toll_reason = "This route does not trigger any commercial toll multipliers in our database."

            col1, col2 = st.columns([1.2, 1.8])
            
            with col1:
                st.metric(label="🗺️ Estimated Route Mileage", value=f"{total_miles:,.1f} Miles")
                st.write(f"**Equipment Profile:** `{vehicle_type}`")
                st.markdown("---")
                
                if calculated_toll > 0:
                    st.error(f"💰 Automated Dynamic Toll: ${calculated_toll:.2f}")
                    st.write(f"ℹ️ **System Intelligence:** {toll_reason}")
                else:
                    st.success("✅ Automated Dynamic Toll: $0.00")
                    st.write(f"ℹ️ **System Intelligence:** {toll_reason}")

                st.markdown("---")
                st.markdown("### ⏱️ Logistics Zone Tracking")
                
                # Using \r\n explicitly so Windows Notepad formats it properly
                dispatch_sheet_text = "======================================\r\n"
                dispatch_sheet_text += "      DRIVER DISPATCH ITINERARY\r\n"
                dispatch_sheet_text += "======================================\r\n"
                dispatch_sheet_text += f"DATE: {datetime.now().strftime('%Y-%m-%d')}\r\n"
                dispatch_sheet_text += f"EQUIPMENT: {vehicle_type}\r\n"
                dispatch_sheet_text += f"TOTAL DISTANCE: {total_miles:,.1f} Miles\r\n"
                dispatch_sheet_text += f"ESTIMATED TOLL: ${calculated_toll:.2f}\r\n\r\n"
                dispatch_sheet_text += "--- ROUTE DETAILS ---\r\n"

                for idx, data in enumerate(locations_data):
                    status = "ORIGIN" if idx == 0 else "PICKUP" if idx == 1 and len(locations_data)==3 else "DELIVERY"
                    st.markdown(f"**{status.capitalize()}:** {data['Query']}  \n➤ `{data['Zone']}` (Local Time: {data['Time']})")
                    dispatch_sheet_text += f"{idx+1}. {status}: {data['Query']}\r\n   Zone: {data['Zone']} | Local Time: {data['Time']}\r\n\r\n"
                
                dispatch_sheet_text += "======================================\r\n"
                dispatch_sheet_text += "Drive Safely!"

                st.markdown("---")
                
                # Placing buttons side by side
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    st.download_button(
                        label="📄 Download TXT",
                        data=dispatch_sheet_text,
                        file_name="Driver_Dispatch_Itinerary.txt",
                        mime="text/plain"
                    )
                with btn_col2:
                    st.download_button(
                        label="🖨️ Download PDF",
                        data=create_pdf(dispatch_sheet_text),
                        file_name="Driver_Dispatch_Itinerary.pdf",
                        mime="application/pdf"
                    )

            with col2:
                m = folium.Map(location=coordinates[0], zoom_start=5)
                if route_geometry: 
                    folium.PolyLine(route_geometry, color="blue", weight=5, opacity=0.8).add_to(m)
                else: 
                    folium.PolyLine(coordinates, color="blue", weight=3).add_to(m)
                
                for i, coord in enumerate(coordinates):
                    folium.Marker(location=coord, icon=folium.Icon(color="green" if i==0 else "red" if i==len(coordinates)-1 else "orange")).add_to(m)
                st_folium(m, width=800, height=600, returned_objects=[])
