import streamlit as st
import pandas as pd
import requests


# ATTOM API key
API_KEY = '2b1eb5ef0054d8fd5804e1d8b8e30ac2'  # Replace with your actual API key
headers = {
    'apikey': API_KEY,
    'accept': 'application/json'
}

# States where services are not available
states_not_served = ['New York', 'Texas']

# Function to get property profile and retrieve geoIdV4 for CO, total mortgage amount, and current home value
def get_property_profile(address1, address2):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/basicprofile"
    params = {'address1': address1, 'address2': address2}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        try:
            property_data = data['property'][0]
            geo_id_v4 = property_data['location']['geoIdV4'].get('CO')
            state = property_data['address']['countrySubd']
            
            # Retrieve mortgage amounts and calculate total mortgage amount
            mortgage_data = property_data['assessment'].get('mortgage', {})
            total_mortgage_amount = sum(
                item.get('amount', 0) for item in mortgage_data.values() if isinstance(item, dict)
            )

            # Retrieve current home value (mktttlvalue)
            current_home_value = property_data['assessment'].get('market', {}).get('mktTtlValue', 'N/A')
            
            return geo_id_v4, state, total_mortgage_amount, current_home_value
        except (KeyError, IndexError):
            st.error("Required data not found in the property profile.")
            return None, None, None, None
    else:
        st.error(f"Failed to retrieve property profile: {response.status_code}")
        return None, None, None, None

# Function to get neighborhood community data based on geoIdV4
def get_community_data(geo_id_v4):
    url = f"https://api.gateway.attomdata.com/v4/neighborhood/community"
    params = {'geoIdv4': geo_id_v4}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        try:
            # Access the crime index
            crime_index = data['community']['crime'].get('crime_Index')
            return crime_index
        except (KeyError, TypeError):
            st.error("Crime index not found in community data.")
            return None
    else:
        st.error(f"Failed to retrieve community data: {response.status_code}")
        return None

# Function to check eligibility
def check_eligibility(state, home_value, debt_value, crime_index):
    eligible = True
    
    # Check if the state is not served
    if state in states_not_served:
        st.error("Ineligible: This state is not served.")
        eligible = False

    # Check if debt exceeds or equals home value
    if debt_value >= home_value:
        st.error("Ineligible: Debt value exceeds or equals home value.")
        eligible = False

    # Check if crime index exceeds 50
    if crime_index is not None and crime_index >= 50:
        st.error("Ineligible: Crime index exceeds 50.")
        eligible = False

    return eligible

# Streamlit app layout
st.title('Homeowner Eligibility Assessment')
st.write("Enter the property address details to check eligibility.")

# User input form for address and property details
with st.form("property_form"):
    address1 = st.text_input("Street Address (e.g., '4529 Winona Ct')")
    city = st.text_input("City (e.g., 'Denver')")
    state = st.text_input("State (e.g., 'CO')")
    zipcode = st.text_input("Zip Code (e.g., '80212')")
    home_value = st.number_input("Home Value", min_value=0)
    debt_value = st.number_input("Debt Value", min_value=0)
    submitted = st.form_submit_button("Submit")

# Process form submission
if submitted:
    if not (address1 and city and state and zipcode):
        st.error("All address fields (Street Address, City, State, Zip Code) are required. Please fill them in.")
    else:
        # Prepare address components for API
        address2 = f"{city}, {state} {zipcode}"

        # Get geoIdV4 for CO, total mortgage amount, and current home value using the property profile API
        geo_id_v4, property_state, total_mortgage_amount, current_home_value = get_property_profile(address1, address2)
        
        if geo_id_v4 and property_state:
            #st.write(f"geoIdV4 for CO: {geo_id_v4}")
            #st.write(f"State: {property_state}")
            st.write(f"Current Home Value: ${current_home_value}")
            st.write(f"Total Mortgage Amount: ${total_mortgage_amount}")

            # Get crime index using the community data API
            crime_index = get_community_data(geo_id_v4)
            if crime_index is not None:
                st.write(f"Crime Index for the neighborhood: {crime_index}")

                # Perform eligibility check and display result
                if check_eligibility(property_state, home_value, debt_value, crime_index):
                    st.success("Homeowner is eligible for next step.")
                else:
                    st.error("Homeowner does not meet eligibility criteria.")
            else:
                st.error("Could not retrieve crime index for eligibility check.")
        else:
            st.error("Could not retrieve property data for eligibility check.")
