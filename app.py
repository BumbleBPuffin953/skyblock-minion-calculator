from functions import create_all_combos,fetch_and_process_data,create_minion_df,apply_all_combos

import streamlit as st
from streamlit.column_config import NumberColumn

import pandas as pd
import json
import copy
import requests
from datetime import datetime
import time

@st.cache_data(ttl=3600)
def create_final_df():
    bazaar_cache = {
        k: {
            "Instant Sell": v["quick_status"]["sellPrice"],
            "Instant Buy": v["quick_status"]["buyPrice"]
        }
        for k, v in requests.get("https://api.hypixel.net/v2/skyblock/bazaar").json()['products'].items()
    }
    all_combos = create_all_combos(bazaar_cache)
    
    minion_dict,minion_info = fetch_and_process_data()

    all_minion_results = []
    for minion_name,minion_data in minion_dict.items():
        base_df = create_minion_df(minion_data)
        combo_df = apply_all_combos(base_df.copy(),all_combos,minion_info[minion_name])
        combo_df['Minion'] = minion_name
        all_minion_results.append(combo_df)

    return pd.concat(all_minion_results,ignore_index=True)

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

start_time = time.time()
df = create_final_df()
run_time = time.time() - start_time

new_order = ['Minion', 'Tier', 'Fuel', 'Upgrade 1', 'Upgrade 2', 'Misc Upgrades','Speed Mod', 'Profit', 'Cost']
df = df[new_order]

st.write(f"Program took {int(run_time)} seconds to load")
# Then process other filters (in any order you want in code)
minion_filter = st.multiselect("Filter Minions", options=df['Minion'].unique())
fuel_filter = st.multiselect("Filter Fuel", options=df['Fuel'].unique())

all_upgrades = pd.unique(df[['Upgrade 1', 'Upgrade 2']].values.ravel('K'))
all_upgrades = sorted([x for x in all_upgrades if pd.notna(x)])  # remove NaNs

upgrade_filter = st.multiselect("Filter Upgrades", options=all_upgrades)

cost_ranges = st.multiselect(
    "Select one or more Craft Cost Ranges",
    ["< 2M", "2M - 10M", "10M - 50M", "50M+"]
)

misc_upgrades = st.multiselect(
    "Select one or more miscellaneous upgrade",
    ["Floating Crystal", "Beacon", "Power Crystal", "Mithril Infusion", "Free Will", "Postcard"],
)

if len(upgrade_filter) == 0:
    upgrade_mask = pd.Series(True, index=df.index)
elif len(upgrade_filter) == 1:
    upgrade_mask = (df['Upgrade 1'].isin(upgrade_filter)) | (df['Upgrade 2'].isin(upgrade_filter))
else:
    upgrade_mask = (df['Upgrade 1'].isin(upgrade_filter)) & (df['Upgrade 2'].isin(upgrade_filter))
    
if minion_filter:
    minion_mask = df['Minion'].isin(minion_filter)
else:
    minion_mask = pd.Series(True, index=df.index)

if fuel_filter:
    fuel_mask = df['Fuel'].isin(fuel_filter)
else:
    fuel_mask = pd.Series(True, index=df.index)

filtered_df = df[minion_mask & fuel_mask & upgrade_mask]

if cost_ranges:
    cost_filtered = pd.DataFrame()

    if "< 2M" in cost_ranges:
        cost_filtered = pd.concat([cost_filtered, filtered_df[filtered_df["Cost"] < 2_000_000]])
    if "2M - 10M" in cost_ranges:
        cost_filtered = pd.concat([cost_filtered, filtered_df[(filtered_df["Cost"] >= 2_000_000) & (filtered_df["Cost"] < 10_000_000)]])
    if "10M - 50M" in cost_ranges:
        cost_filtered = pd.concat([cost_filtered, filtered_df[(filtered_df["Cost"] >= 10_000_000) & (filtered_df["Cost"] < 50_000_000)]])
    if "50M+" in cost_ranges:
        cost_filtered = pd.concat([cost_filtered, filtered_df[filtered_df["Cost"] >= 50_000_000]])

    filtered_df = cost_filtered.drop_duplicates()

filtered_df = filtered_df[filtered_df['Misc Upgrades'] == tuple(sorted(misc_upgrades))]
df_display = filtered_df.copy()

# Scale values
df_display["Profit"] = df_display["Profit"] / 1_000       # Now in thousands
df_display["Cost"] = df_display["Cost"] / 1_000_000 

st.dataframe(
    df_display,
    column_config={
        "Profit": NumberColumn(
            "Profit",
            format="%.1fK",
            help="Daily profit in thousands of coins"
        ),
        "Cost": NumberColumn(
            "Cost",
            format="%.2fM",
            help="Cost to craft this minion setup, in millions"
        ),
    },
    use_container_width=True
)