import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go

# Vesta Equity API key (replace with your actual key)
VESTA_API_KEY = '550d3726-b629-4432-9e64-41cf5686d63be'

# ATTOM API key
ATTOM_API_KEY = '2b1eb5ef0054d8fd5804e1d8b8e30ac2'

# Function to fetch property data from Vesta Equity API
def fetch_vesta_properties():
    url = "https://app.vestaequity.net/api/listings/"
    headers = {
        "apikey": VESTA_API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['results']
    else:
        st.error(f"Error fetching data from Vesta Equity API: {response.status_code}")
        return None

# Function to get AVM history and geoIdV4 from ATTOM API
def get_avm_history_and_geoid(address):
    url = f"https://api.gateway.attomdata.com/propertyapi/v1.0.0/avmhistory/detail"
    headers = {
        'apikey': ATTOM_API_KEY,
        'accept': 'application/json'
    }
    params = {'address': address}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        avm_history = data['property'][0].get('avmhistory', [])
        geo_id_v4 = data['property'][0]['location']['geoIdV4'].get('CO')
        return [
            {
                "eventDate": entry['eventDate'],
                "value": entry['amount']['value']
            } for entry in avm_history
        ], geo_id_v4
    return [], None

# Function to get environmental factors from ATTOM API
def get_environmental_factors(geoIdV4):
    url = f"https://api.gateway.attomdata.com/v4/neighborhood/community"
    headers = {
        'apikey': ATTOM_API_KEY,
        'accept': 'application/json'
    }
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

# Main Streamlit app
def main():
    st.title("Investor Portfolio ROI Estimator")

    # Fetch properties from Vesta Equity API
    properties = fetch_vesta_properties()

    if properties:
        # Create a dropdown for property selection
        selected_properties = st.multiselect(
            "Select properties to invest in:",
            options=[f"{p['property']['street_address']}, {p['property']['city']}, {p['property']['state']}" for p in properties],
            format_func=lambda x: x
        )

        # Create a dictionary to store investment details for each property
        investments = {}

        for prop in selected_properties:
            st.subheader(prop)
            
            # Find the corresponding property data
            property_data = next(p for p in properties if f"{p['property']['street_address']}, {p['property']['city']}, {p['property']['state']}" == prop)
            
            col1, col2 = st.columns(2)
            
            with col1:
                investment_amount = st.number_input(f"Investment amount for {prop}", 
                                                    min_value=float(property_data['property']['minimum_investment_amount']), 
                                                    max_value=float(property_data['available_equity_amount']),
                                                    step=1000.0)
            
            with col2:
                tenure = st.selectbox(f"Investment tenure for {prop}", [5, 10, 15])
            
            st.write(f"Equity Percentage Available: {property_data['listed_equity_percentage']}%")
            st.write(f"Homeowner's Requested Amount: ${property_data['available_equity_amount']:,.2f}")
            
            appreciation_rate = property_data['property']['analysis']['ten_year_historical_cagr']
            st.write(f"Projected Annual Home Appreciation: {appreciation_rate:.2%}")
            
            roi, future_value = calculate_roi(investment_amount, tenure, appreciation_rate)
            st.write(f"Estimated ROI after {tenure} years: {roi:.2%}")
            st.write(f"Estimated future value: ${future_value:,.2f}")
            
            # Fetch AVM history and geoIdV4
            avm_history, geo_id_v4 = get_avm_history_and_geoid(prop)
            
            if geo_id_v4:
                # Fetch environmental factors
                env_factors = get_environmental_factors(geo_id_v4)
                if env_factors:
                    st.write("### Environmental Factors")
                    for factor, value in env_factors.items():
                        st.write(f"**{factor.replace('_', ' ').title()}:** {value}")
            
            if avm_history:
                st.write("### AVM History")
                df_avm = pd.DataFrame(avm_history)
                df_avm['eventDate'] = pd.to_datetime(df_avm['eventDate'])
                df_avm.set_index('eventDate', inplace=True)
                
                fig_avm = go.Figure()
                fig_avm.add_trace(go.Scatter(x=df_avm.index, y=df_avm['value'], mode='lines', name="Value"))
                fig_avm.update_layout(title="AVM Value Over Time", xaxis_title="Date", yaxis_title="Value")
                st.plotly_chart(fig_avm)
            
            investments[prop] = {
                "amount": investment_amount,
                "tenure": tenure,
                "roi": roi,
                "future_value": future_value
            }
        
        if investments:
            st.subheader("Investment Summary")
            summary_data = pd.DataFrame.from_dict(investments, orient='index')
            st.table(summary_data.style.format({
                'amount': '${:,.2f}',
                'roi': '{:.2%}',
                'future_value': '${:,.2f}'
            }))
            
            # Plotting ROI comparison
            fig = go.Figure(data=[
                go.Bar(name='ROI', x=summary_data.index, y=summary_data['roi'], text=summary_data['roi'].apply(lambda x: f'{x:.2%}'), textposition='auto')
            ])
            fig.update_layout(title='ROI Comparison')
            st.plotly_chart(fig)
    else:
        st.error("Failed to fetch properties from Vesta Equity API. Please try again later.")

if __name__ == "__main__":
    main()