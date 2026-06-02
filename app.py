import streamlit as st
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium

# 1. Page Configuration (Must be the first Streamlit command)
st.set_page_config(page_title="Truck Route & Toll Calculator", layout="wide")

# 2. Fixed Toll Database for Commercial 5-Axle Trucks by State
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

# 3. Initialize Session State for Login
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# 4. Login Functionality
if not st.session_state['logged_in']:
    st.title("🔒 Login Required")
    st.write("Please enter your credentials to access the Truck Route & Toll Calculator.")
    
    # Create a login form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            # Check credentials
            if username == "admin" and password == "admin123":
                st.session_state['logged_in'] = True
                st.success("Login successful! Redirecting...")
                st.rerun()
            else:
                st.error("Invalid Username or Password. Please try again.")

# 5. Main Application (Only visible if logged in)
else:
    st.title("🚛 Truck Route, Map & Toll Calculator")
    st.write("Calculate your truck route, view live maps, and estimate toll costs for free.")

    # Sidebar layout
    st.sidebar.header("👤 Account")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()
        
    st.sidebar.markdown("---")
    
    # Sidebar for Location Inputs
    st.sidebar.header("📍 Route Locations")
    origin = st.sidebar.text_input("1. Start Location / Truck Status", "Cincinnati, OH")
    waypoint = st.sidebar.text_input("2. Pickup / Waypoint (Optional)", "Marion, IN")
    destination = st.sidebar.text_input("3. Final Delivery / Destination", "Eugene, OR")

    submit_btn = st.sidebar.button("Calculate Route & Toll")

    if submit_btn:
        geolocator = Nominatim(user_agent="truck_toll_calculator_secure")
        
        locations = []
        coordinates = []
        states_visited = set()
        
        # Geocoding locations to get coordinates and state names
        for loc_name in [origin, waypoint, destination]:
            if loc_name and loc_name.strip():
                try:
                    loc = geolocator.geocode(loc_name, addressdetails=True)
                    if loc:
                        locations.append(loc)
                        coordinates.append((loc.latitude, loc.longitude))
                        
                        # Extract state name for toll calculation
                        address = loc.raw.get('address', {})
                        state = address.get('state')
                        if state:
                            states_visited.add(state)
                except Exception as e:
                    st.error(f"Error finding location: {loc_name}")

        if len(coordinates) >= 2:
            total_toll = 0.0
            detected_tolls = []
            
            # Calculate tolls based on states visited
            for state in states_visited:
                if state in STATE_TOLLS:
                    total_toll += STATE_TOLLS[state]
                    detected_tolls.append(f"• {state}: ${STATE_TOLLS[state]:.2f}")
            
            if total_toll == 0:
                toll_status = "✅ This route appears to be toll-free for commercial trucks!"
            else:
                toll_status = "⚠️ Toll roads detected on this route!"

            # Layout Setup for Results
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.metric(label="💰 Estimated Truck Toll", value=f"${total_toll:.2f}")
                st.subheader("📋 Toll Breakdown")
                st.write(toll_status)
                for item in detected_tolls:
                    st.write(item)
                    
                st.info("💡 Dispatcher Tip: Remember to factor this toll cost when negotiating the rate with the broker.")

            with col2:
                st.subheader("🗺️ Live Route Map")
                # Generate the Map centered at the starting point
                m = folium.Map(location=coordinates[0], zoom_start=5)
                
                # Add Markers for each stop
                for i, coord in enumerate(coordinates):
                    label = f"Stop {i+1}: {locations[i].address.split(',')[0]}"
                    folium.Marker(location=coord, popup=label, tooltip=label).add_to(m)
                
                # Draw the Route Line
                folium.PolyLine(coordinates, color="blue", weight=4, opacity=0.7).add_to(m)
                
                # Render map in Streamlit
                st_folium(m, width=800, height=500)
        else:
            st.error("Please enter at least two valid locations to calculate the route.")
