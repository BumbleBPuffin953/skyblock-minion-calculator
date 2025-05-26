from functions import minion_processing

import streamlit as st
import pandas as pd
import json
import copy
import requests
from datetime import datetime
import pytz 

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
        recipe = fuel.get('Recipe')
        if recipe:
            fuels[name]['Cost'] = 0
            for item in recipe:
                fuels[name]['Cost'] += bazaar_cache[item['Item']].get('Instant Sell',0) * item['Amount']
        else:
            fuels[name]['Cost'] = bazaar_cache.get(name, {}).get('Instant Sell', 0) if fuel['Duration'] == -1 else 86400 / fuel['Duration'] * bazaar_cache.get(name, {}).get('Instant Sell', 0)
        fuels[name]['Daily Cost'] = 0 if fuel['Duration'] == -1 else 86400 / fuel['Duration'] * bazaar_cache.get(name, {}).get('Instant Sell', 0)
        
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
    df = df.sort_values(by=['Minion', 'Fuel', 'Upgrade 1', 'Upgrade 2'], ascending=[True, True, True, True])

    # Apply number formatting
    def format_cost(value):
        return f"{value / 1_000_000:.1f}M"  # For millions
    def format_profit(value):
        return f"{value / 1_000:.1f}K"  # For thousands


    df['Daily Coins'] = df['Daily Coins'].apply(format_cost)
    df['Craft Cost'] = df['Craft Cost'].apply(format_profit)

    return df

st.set_page_config(layout="wide")

# Streamlit UI
st.title("Skyblock Minion Calculator")

# Initialize a session state variable to store the last updated timestamp
if 'last_updated' not in st.session_state:
    st.session_state.last_updated = datetime.now()

# Calculate the time difference in minutes
time_diff = datetime.now() - st.session_state.last_updated
minutes_since_update = time_diff.total_seconds() / 60  # Convert to minutes

# Display the time difference (minutes since last update) underneath the title
st.write(f"{int(minutes_since_update)} minutes since last update")

# Fetch and process data after the reload button has been clicked or app is loaded
df = fetch_and_process_data()

# Filters
minion_filter = st.multiselect("Filter Minions", options=df['Minion'].unique())
fuel_filter = st.multiselect("Filter Fuel", options=df['Fuel'].unique())

all_upgrades = pd.unique(df[['Upgrade 1', 'Upgrade 2']].values.ravel('K'))
all_upgrades = sorted([x for x in all_upgrades if pd.notna(x)])  # also remove NaNs if any
upgrade_filter = st.multiselect("Filter Upgrades", options=all_upgrades)

cost_ranges = st.multiselect(
    "Select one or more Craft Cost Ranges",
    ["All", "< 2M", "2M - 10M", "10M - 50M", "50M+"]
)

filtered_df = df[
    ((df['Minion'].isin(minion_filter)) | (len(minion_filter) == 0)) &
    ((df['Fuel'].isin(fuel_filter)) | (len(fuel_filter) == 0)) &
    (
        (df['Upgrade 1'].isin(upgrade_filter)) |
        (df['Upgrade 2'].isin(upgrade_filter)) |
        (len(upgrade_filter) == 0)
    )
]

if cost_ranges:
    cost_filtered = pd.DataFrame()

    if "< 2M" in cost_ranges:
        cost_filtered = pd.concat([cost_filtered, filtered_df[filtered_df["Craft Cost"] < 2]])
    if "2M - 10M" in cost_ranges:
        cost_filtered = pd.concat([cost_filtered, filtered_df[(filtered_df["Craft Cost"] >= 2) & (filtered_df["Craft Cost"] < 10)]])
    if "10M - 50M" in cost_ranges:
        cost_filtered = pd.concat([cost_filtered, filtered_df[(filtered_df["Craft Cost"] >= 10) & (filtered_df["Craft Cost"] < 50)]])
    if "50M+" in cost_ranges:
        cost_filtered = pd.concat([cost_filtered, filtered_df[filtered_df["Craft Cost"] >= 50]])

    filtered_df = cost_filtered.drop_duplicates()

st.dataframe(filtered_df)