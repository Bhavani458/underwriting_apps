import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# API keys (replace with your actual keys)
VESTA_API_KEY = '550d3726-b629-4432-9e64-41cf5686d63be'
ATTOM_API_KEY = '2b1e86b638620bf2404521e6e9e1b19e'

# Function to fetch property data from Vesta Equity API
def fetch_vesta_properties():
    url = "https://app.vestaequity.net/api/listings/"
    headers = {"apikey": VESTA_API_KEY, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['results']
    else:
        st.error(f"Error fetching data from Vesta Equity API: {response.status_code}")
        return None

# Function to get AVM history and geoIdV4 from ATTOM API
def get_avm_history_and_geoid(address):
    url = f"https://api.gateway.attomdata.com/propertyapi/v1.0.0/avmhistory/detail"
    headers = {'apikey': ATTOM_API_KEY, 'accept': 'application/json'}
    params = {'address': address}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        avm_history = data['property'][0].get('avmhistory', [])
        geo_id_v4 = data['property'][0]['location']['geoIdV4'].get('CO')
        return [
            {"eventDate": entry['eventDate'], "value": entry['amount']['value']}
            for entry in avm_history
        ], geo_id_v4
    return [], None

# Function to get environmental factors from ATTOM API
def get_environmental_factors(geoIdV4):
    url = f"https://api.gateway.attomdata.com/v4/neighborhood/community"
    headers = {'apikey': ATTOM_API_KEY, 'accept': 'application/json'}
    params = {'geoIdv4': geoIdV4}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        try:
            natural_disasters = data['community']['naturalDisasters']
            air_quality = data['community']['airQuality']
            return {
                'earthquake_index': natural_disasters.get('earthquake_Index', 'N/A'),
                'hurricane_index': natural_disasters.get('hurricane_Index', 'N/A'),
                'tornado_index': natural_disasters.get('tornado_Index', 'N/A'),
                'air_pollution_index': air_quality.get('air_Pollution_Index', 'N/A')
            }
        except KeyError:
            st.error("Environmental factors not found in community data.")
            return None
    else:
        st.error(f"Failed to retrieve community data: {response.status_code}")
        return None

# Function to calculate ROI
def calculate_roi(investment_amount, tenure, appreciation_rate):
    future_value = investment_amount * (1 + appreciation_rate) ** tenure
    roi = (future_value - investment_amount) / investment_amount
    return roi, future_value

def best(properties):
    # Highest ROI, lowest environmental risk, highest AVM value
    return sorted(properties, key=lambda x: (x['roi'], -x['env_risk'], x['latest_avm']), reverse=True)[0]

def better(properties):
    # Higher ROI, lower environmental risk, higher AVM value
    sorted_props = sorted(properties, key=lambda x: (x['roi'], -x['env_risk'], x['latest_avm']), reverse=True)
    return sorted_props[1] if len(sorted_props) > 1 else sorted_props[0]

def good(properties):
    # High ROI, low environmental risk, high AVM value
    sorted_props = sorted(properties, key=lambda x: (x['roi'], -x['env_risk'], x['latest_avm']), reverse=True)
    return sorted_props[2] if len(sorted_props) > 2 else sorted_props[0]

# Main Streamlit app
def main():
    st.title("🏠 Investor Portfolio ROI Estimator")

    properties = fetch_vesta_properties()

    if properties:
        selected_properties = st.multiselect(
            "Select properties to invest in:",
            options=[f"{p['property']['street_address']}, {p['property']['city']}, {p['property']['state']}" for p in properties],
            format_func=lambda x: x,
            key='property_selection'
        )

        investments = []

        for i, prop in enumerate(selected_properties):
            st.markdown(f"## 🏡 {prop}")
            
            property_data = next(p for p in properties if f"{p['property']['street_address']}, {p['property']['city']}, {p['property']['state']}" == prop)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                investment_amount = st.number_input(f"Investment amount ($)", 
                                                    min_value=float(property_data['property']['minimum_investment_amount']), 
                                                    max_value=float(property_data['available_equity_amount']),
                                                    step=10000.0,
                                                    key=f'investment_{i}')
            
            with col2:
                tenure = st.selectbox("Investment tenure (years)", [5, 10, 15], key=f'tenure_{i}')
            
            with col3:
                st.metric("Equity % Available", f"{property_data['listed_equity_percentage']}%")

            st.metric("Homeowner's Requested Amount", f"${property_data['available_equity_amount']:,.2f}")
            
            appreciation_rate = property_data['property']['analysis']['ten_year_historical_cagr']
            st.metric("Projected Annual Home Appreciation", f"{appreciation_rate:.2%}")
            
            roi, future_value = calculate_roi(investment_amount, tenure, appreciation_rate)
            col1.metric(f"Estimated ROI ({tenure} years)", f"{roi:.2%}")
            col2.metric("Estimated future value", f"${future_value:,.2f}")
            
            avm_history, geo_id_v4 = get_avm_history_and_geoid(prop)
        
            env_risk_score = 0
            if geo_id_v4:
                env_factors = get_environmental_factors(geo_id_v4)
                if env_factors:
                    env_risk_score += sum(float(env_factors[factor]) for factor in env_factors if env_factors[factor] != 'N/A')
                    st.markdown("### 🌍 Environmental Factors")
                    cols_env = st.columns(4)
                    for j, (factor, value) in enumerate(env_factors.items()):
                        cols_env[j].metric(factor.replace('_', ' ').title(), value)

            # Display AVM history as a line plot
            if avm_history:
                df_avm_history = pd.DataFrame(avm_history)
                df_avm_history['eventDate'] = pd.to_datetime(df_avm_history['eventDate'])
                df_avm_history = df_avm_history.sort_values('eventDate', ascending=False)
                latest_avm_value = df_avm_history.iloc[0]['value']
    
                fig_avm_history = px.line(df_avm_history.sort_values('eventDate'), x='eventDate', y='value', 
                                          title='AVM History',
                                          labels={
                                                'eventDate': 'Date',  # x-axis title
                                                'value': 'AVM Value ($)'})
                st.plotly_chart(fig_avm_history)
            else:
                latest_avm_value = 0
            
            # Display latest AVM value formatted like environmental factors
            st.markdown("### 📈 Latest AVM Value")
            cols_avm = st.columns(1)
            cols_avm[0].metric("Latest AVM Value", f"${latest_avm_value:,.2f}")

            investments.append({
                "address": prop,
                "amount": investment_amount,
                "tenure": tenure,
                "roi": roi,
                "future_value": future_value,
                "latest_avm": latest_avm_value,
                "env_risk": env_risk_score
            })
        
        if len(investments) >= 1:
            best_property_good = good(investments)
            st.markdown("## 🥉 Good Property")
            st.write(f"Address: {best_property_good['address']}")
        
        if len(investments) >= 2:
            best_property_better = better(investments)
            st.markdown("## 🥈 Better Property")
            st.write(f"Address: {best_property_better['address']}")

        if len(investments) >= 3:
            best_property_best = best(investments)
            st.markdown("## 🏆 Best Property")
            st.write(f"Address: {best_property_best['address']}")

if __name__ == "__main__":
    main()