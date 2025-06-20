from functions import create_all_combos,fetch_and_process_data,create_minion_df,apply_all_combos

import streamlit as st
from streamlit.column_config import NumberColumn

import pandas as pd
import json
import copy
import requests
from datetime import datetime
import math
import numpy as np

@st.cache_data(ttl=3600)
def create_final_df():
    INT32_MAX = 2_147_483_647
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
        combo_df['ROI'] = np.where(combo_df['Profit'] > 0, combo_df['Cost'] / combo_df['Profit'], INT32_MAX)
        all_minion_results.append(combo_df)

    return pd.concat(all_minion_results,ignore_index=True)

st.set_page_config(layout="wide")
st.title("Skyblock Minion Calculator")

df = create_final_df()
df['Misc Upgrades'] = pd.Categorical(df['Misc Upgrades'])

new_order = ['Minion','Tier','Fuel','Upgrade 1','Upgrade 2','Misc Upgrades','Profit','Cost','ROI']
df = df[new_order]

max_craft_cost = float(math.ceil(df['Cost'].max()/1000000))

if 'filters_applied' not in st.session_state:
    st.session_state.filters_applied = True

with st.sidebar.form("Filters_Form"):
    st.header("Filter Options")
    
    minion_whitelist = st.multiselect("Minions Whitelist", options=df['Minion'].unique())
    minion_blacklist = st.multiselect("Minions Blacklist", options=df['Minion'].unique())

    minion_tier_range = st.slider("Minion Tier Range", min_value=1,max_value=12,value=(1,12),step=1)

    fuel_whitelist = st.multiselect("Fuel Whitelist", options=df['Fuel'].unique())
    fuel_blacklist = st.multiselect("Fuel Blacklist", options=df['Fuel'].unique())

    all_upgrades = pd.unique(df[['Upgrade 1', 'Upgrade 2']].values.ravel('K'))
    all_upgrades = sorted([x for x in all_upgrades if pd.notna(x)])

    upgrade_whitelist = st.multiselect("Upgrade Whitelist", options=all_upgrades)
    upgrade_blacklist = st.multiselect("Upgrade Blacklist", options=all_upgrades)

    col5, col6 = st.columns(2)
    with col5:
        min_cost = st.number_input("Craft Cost Lower Bound (M)",step=0.01,value=0.00) * 1000000

    with col6:
        max_cost = st.number_input("Craft Cost Upper Bound (M)",step=0.01,value=max_craft_cost) * 1000000

    if min_cost > max_cost:
        min_cost, max_cost = max_cost, min_cost

    misc_upgrades = st.multiselect(
        "Miscellaneous Upgrades",
        ["Floating Crystal", "Beacon", "Power Crystal", "Mithril Infusion", "Free Will", "Postcard"],
    )

    if st.form_submit_button("Apply Filters"):
        st.session_state.filters_applied = True

if st.session_state.filters_applied:
    st.session_state.filters_applied = False

    target_tuple = tuple(sorted(misc_upgrades))
    target_cat = pd.Categorical([target_tuple],categories=df['Misc Upgrades'].cat.categories)[0]

    mask = pd.Series(True,index=df.index)

    if minion_tier_range:
        mask &= df['Tier'].between(*minion_tier_range)

    if minion_whitelist:
        mask &= df['Minion'].isin(minion_whitelist)
    if minion_blacklist:
        mask &= ~df['Minion'].isin(minion_blacklist)

    if fuel_whitelist:
        mask &= df['Fuel'].isin(fuel_whitelist)
    if fuel_blacklist:
        mask &= ~df['Fuel'].isin(fuel_blacklist)

    if upgrade_whitelist:
        upgrade_whitelist_set = set(upgrade_whitelist)
        if len(upgrade_whitelist_set) == 1:
            mask &= df['Upgrade 1'].isin(upgrade_whitelist_set) | df['Upgrade 2'].isin(upgrade_whitelist_set)
        else:
            mask &= df['Upgrade 1'].isin(upgrade_whitelist_set) & df['Upgrade 2'].isin(upgrade_whitelist_set)   
    if upgrade_blacklist:
        mask &= ~(df['Upgrade 1'].isin(upgrade_blacklist) |df['Upgrade 2'].isin(upgrade_blacklist))

    mask &= (df['Cost'] >= min_cost) & (df['Cost'] <= max_cost)
    mask &= (df['Misc Upgrades'] == target_cat)

    filtered_df = df[mask].copy().drop('Misc Upgrades', axis=1).reset_index(drop=True)
    filtered_df['Profit'] = filtered_df['Profit'] / 1_000
    filtered_df['Cost'] = filtered_df['Cost'] / 1_000_000

    st.dataframe(
        filtered_df,
        column_config={
            "Profit": NumberColumn("Profit", format="%.1fK", help="Daily profit in thousands of coins"),
            "Cost": NumberColumn("Cost", format="%.2fM", help="Cost to craft this minion setup, in millions"),
        },
        use_container_width=True
    )