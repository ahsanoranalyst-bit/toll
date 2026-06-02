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

st.set_page_config(page_title="Pro Dispatcher | Premium Toll Suite", layout="wide")

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

# --- PREMIUM DESIGNER PDF GENERATOR ---
def create_premium_pdf(vehicle_type, total_miles, calculated_toll, locations_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    
    # 1. Header Banner (Dark Blue Corporate Style)
    pdf.set_fill_color(26, 54, 93) # Premium Navy Blue
    pdf.rect(0, 0, 210, 38, 'F')
    
    # Header Text
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", style='B', size=20)
    pdf.cell(0, 5, "LOGISTICS DISPATCH SHEET", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%B %d, %Y | %I:%M %p')}", ln=True, align='C')
    
    pdf.ln(15) # Space after header
    pdf.set_text_color(0, 0, 0) # Reset to black
    
    # 2. Summary Block (Grid Table Setup)
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 8, "1. TRIP SUMMARY", ln=True)
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    
    # Row 1
    pdf.set_font("Arial", style='B', size=10)
    pdf.cell(45, 8, " Equipment Type:", border=1)
    pdf.set_font("Arial", size=10)
    pdf.cell(50, 8, f" {vehicle_type}", border=1)
    
    pdf.set_font("Arial", style='B', size=10)
    pdf.cell(45, 8, " Total Distance:", border=1)
    pdf.set_font("Arial", size=10)
    pdf.cell(40, 8, f" {total_miles:,.1f} Miles", border=1, ln=True)
    
    # Row 2 (Toll Highlight Box)
    pdf.set_font("Arial", style='B', size=10)
    pdf.cell(45, 10, " Estimated Toll Risk:", border=1)
    pdf.set_font("Arial", style='B', size=11)
    if calculated_toll > 0:
        pdf.set_text_color(180, 0, 0) # Red color for toll alert
        pdf.cell(135, 10, f" ${calculated_toll:.2f} (Factored for toll highways)", border=1, ln=True)
    else:
        pdf.set_text_color(0, 120, 0) # Green for free
        pdf.cell(135, 10, " $0.00 (Marked as Toll-Free Route)", border=1, ln=True)
        
    pdf.set_text_color(0, 0, 0) # Reset text
    pdf.ln(8)
    
    # 3. Itinerary Tracking Table
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 8, "2. ITINERARY & TIME ZONE DATA", ln=True)
    
    # Table Header
    pdf.set_fill_color(240, 244, 248) # Light grey-blue table header
    pdf.set_font("Arial", style='B', size=10)
    pdf.cell(30, 8, " Stop Type", border=1, fill=True)
    pdf.cell(65, 8, " Location Name", border=1, fill=True)
    pdf.cell(45, 8, " Time Zone ID", border=1, fill=True)
    pdf.cell(40, 8, " Current Local Time", border=1, fill=True, ln=True)
    
    # Table Rows
    pdf.set_font("Arial", size=10)
    for idx, data in enumerate(locations_data):
        status = "Origin" if idx == 0 else "Pickup Stop" if idx == 1 and len(locations_data)==3 else "Final Delivery"
        pdf.cell(30, 8, f" {status}", border=1)
        pdf.cell(65, 8, f" {data['Query']}", border=1)
        pdf.cell(45, 8, f" {data['Zone']}", border=1)
        pdf.cell(40, 8, f" {data['Time']}", border=1, ln=True)
        
    pdf.ln(12)
    
    # 4. Premium Disclaimer & Safety Box
    pdf.set_fill_color(254, 252, 23BF) # Soft yellow info box background
    pdf.set_draw_color(217, 119, 6) # Orange border
    pdf.rect(15, pdf.get_y(), 180, 24, 'DF')
    
    pdf.set_y(pdf.get_y() + 2)
    pdf.set_font("Arial", style='B', size=9)
    pdf.set_text_color(180, 83, 9)
    pdf.cell(0, 5, "  SAFETY & REIMBURSEMENT NOTICE FOR CARRIERS:", ln=True)
    pdf.set_font("Arial", size=9)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 5, "  - Please verify all timezone shifts before scheduling your pick/drop appointments.", ln=True)
    pdf.cell(0, 5, "  - Keep physical or electronic copies of all toll transponder logs for seamless clearing.", ln=True)
    
    # 5. Sign-off Line
    pdf.set_y(pdf.get_y() + 15)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y() + 10, 75, pdf.get_y() + 10)
    pdf.line(135, pdf.get_y() + 10, 195, pdf.get_y() + 10)
    
    pdf.set_y(pdf.get_y() + 12)
    pdf.set_font("Arial", size=9)
    pdf.cell(120, 5, "Authorized Dispatcher Signature")
    pdf.cell(0, 5, "Carrier / Driver Signature", ln=True)
    
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
        geolocator = Nominatim(user_agent="pro_dispatcher_premium")
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
                
                # Format legacy TXT for Windows notepad just in case
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

                st.markdown("---")
                
                # Premium Side-by-Side Download Buttons
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    st.download_button(
                        label="📄 Download Clean TXT",
                        data=dispatch_sheet_text,
                        file_name="Driver_Dispatch_Itinerary.txt",
                        mime="text/plain"
                    )
                with btn_col2:
                    st.download_button(
                        label="👑 Download Premium PDF Sheet",
                        data=create_premium_pdf(vehicle_type, total_miles, calculated_toll, locations_data),
                        file_name="Premium_Driver_Dispatch_Sheet.pdf",
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
