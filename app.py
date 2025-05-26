import streamlit as st
import pandas as pd
import json
import copy
import requests
import csv
from functions import minion_processing  # assuming this is your function

@st.cache_data(ttl=3600)
def fetch_and_process_data():
    # Load your static JSON data
    with open("_data.json","r") as file:
        minions = json.load(file)

    with open("_fuels.json","r") as file:
        fuels = json.load(file)

    with open("_upgrades.json","r") as file:
        upgrades = json.load(file)

    # Fetch Bazaar prices
    bazaar_cache = {
        k: {
            "Instant Sell": v["quick_status"]["sellPrice"],
            "Instant Buy": v["quick_status"]["buyPrice"]
        }
        for k, v in requests.get("https://api.hypixel.net/v2/skyblock/bazaar").json()['products'].items()
    }

    # Calculate costs
    for name, minion in minions.items():
        for tier in minion['Tiers']:
            tier['Cost'] = 0
            for item in tier.get('Recipe', []):
                if item['Item'] == "Coins":
                    tier['Cost'] += item['Amount']
                else:
                    tier['Cost'] += bazaar_cache.get(item['Item'], {}).get('Instant Sell', 0) * item['Amount']

    for name,fuel in fuels.items():
        fuels[name]['Daily Cost'] = 0 if fuel['Duration'] == -1 else 86400 / fuel['Duration'] * bazaar_cache.get(name, {}).get('Instant Sell', 0)
        fuels[name]['Cost'] = bazaar_cache.get(name, {}).get('Instant Sell', 0) if fuel['Duration'] == -1 else 86400 / fuel['Duration'] * bazaar_cache.get(name, {}).get('Instant Sell', 0)

    for name,upgrade in upgrades.items():
        upgrades[name]['Cost'] = bazaar_cache.get(name, {}).get('Instant Sell', 0)

    minion_dict = minion_processing(copy.deepcopy(minions), copy.deepcopy(fuels), copy.deepcopy(upgrades), copy.deepcopy(bazaar_cache))

    rows = []
    for minion, configs in minion_dict.items():
        for upgrades_combo, tier_values in configs.items():
            for tiers in tier_values:
                tier = tiers['Tier']
                profit = tiers['Profit']
                cost = tiers['Cost']
                rows.append([minion, tier, upgrades_combo[0], upgrades_combo[1], upgrades_combo[2], profit, cost])

    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=["Minion", "Tier", "Fuel", "Upgrade 1", "Upgrade 2", "Daily Coins", "Craft Cost"])

    # Sort by Daily Coins descending
    df = df.sort_values(by="Daily Coins", ascending=False)
    return df

# Streamlit UI
st.title("Skyblock Minion Calculator")

df = fetch_and_process_data()

# Filters
minion_filter = st.multiselect("Filter Minions", options=df['Minion'].unique(), default=df['Minion'].unique())
fuel_filter = st.multiselect("Filter Fuel", options=df['Fuel'].unique(), default=df['Fuel'].unique())

min_cost, max_cost = st.slider("Craft Cost Range", 
                                             float(df['Craft Cost'].min()), 
                                             float(df['Craft Cost'].max()), 
                                             (float(df['Craft Cost'].min()), float(df['Craft Cost'].max())))

filtered_df = df[
    (df['Minion'].isin(minion_filter)) &
    (df['Fuel'].isin(fuel_filter)) &
    (df['Craft Cost'] >= min_cost) &
    (df['Craft Cost'] <= max_cost)
]

st.dataframe(filtered_df)
