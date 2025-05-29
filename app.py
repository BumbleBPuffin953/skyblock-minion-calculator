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

st.title("Skyblock Minion Calculator")

if 'last_updated' not in st.session_state:
    st.session_state.last_updated = datetime.now()

time_diff = datetime.now() - st.session_state.last_updated
minutes_since_update = time_diff.total_seconds() / 60  

st.write(f"{int(minutes_since_update)} minutes since last update")

start_time = time.time()
df = create_final_df()
run_time = time.time() - start_time

new_order = ['Minion','Tier','Fuel','Upgrade 1','Upgrade 2','Misc Upgrades','Profit','Cost']
df = df[new_order]

st.write(f"Program took {int(run_time)} seconds to load")

with st.sidebar:
    st.header("Filter Options")
    
    minion_whitelist = st.multiselect("Minions Whitelist", options=df['Minion'].unique())
    minion_blacklist = st.multiselect("Minions Blacklist", options=df['Minion'].unique())

    fuel_whitelist = st.multiselect("Fuel Whiteliist", options=df['Fuel'].unique())
    fuel_blacklist = st.multiselect("Fuel Blacklist", options=df['Fuel'].unique())

    all_upgrades = pd.unique(df[['Upgrade 1', 'Upgrade 2']].values.ravel('K'))
    all_upgrades = sorted([x for x in all_upgrades if pd.notna(x)])

    upgrade_whitelist = st.multiselect("Upgrade Whitelist", options=all_upgrades)
    upgrade_blacklist = st.multiselect("Upgrade Blacklist", options=all_upgrades)

    cost_ranges = st.multiselect(
        "Craft Cost",
        ["< 2M", "2M - 10M", "10M - 50M", "50M+"]
    )

    misc_upgrades = st.multiselect(
        "Miscellaneous Upgrades",
        ["Floating Crystal", "Beacon", "Power Crystal", "Mithril Infusion", "Free Will", "Postcard"],
    )

if not upgrade_whitelist and not upgrade_blacklist:
    upgrade_mask = pd.Series(True, index=df.index)
else:
    upgrade_mask = pd.Series(True, index=df.index)
    if upgrade_whitelist:
        upgrade_mask &= (
            df['Upgrade 1'].isin(upgrade_whitelist) |
            df['Upgrade 2'].isin(upgrade_whitelist)
        )
    if upgrade_blacklist:
        upgrade_mask &= ~(
            df['Upgrade 1'].isin(upgrade_blacklist) |
            df['Upgrade 2'].isin(upgrade_blacklist)
        )
    
minion_mask = pd.Series(True, index=df.index)
if minion_whitelist:
    minion_mask &= df['Minion'].isin(minion_whitelist)
if minion_blacklist:
    minion_mask &= ~df['Minion'].isin(minion_blacklist)

fuel_mask = pd.Series(True, index=df.index)
if fuel_whitelist:
    fuel_mask &= df['Fuel'].isin(fuel_whitelist)
if fuel_blacklist:
    fuel_mask &= ~df['Fuel'].isin(fuel_blacklist)

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
filtered_df = filtered_df.drop('Misc Upgrades', axis=1).reset_index(drop=True)
filtered_df = filtered_df.reset_index(drop=True)
df_display = filtered_df.copy()

df_display["Profit"] = df_display["Profit"] / 1_000 
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