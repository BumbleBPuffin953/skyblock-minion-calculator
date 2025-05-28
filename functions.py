import requests
import itertools
import math
import copy
import json
import pandas as pd

def is_compatible(minion, upgrade):
    """
    Checks if a minion is compatible with an upgrade.
    
    Args:
        minion (Dict): The minion dictionary, containing relevant attributes such as 'Family' and 'Mob Spawning'.
        upgrade (Dict): The upgrade dictionary, potentially containing a 'Condition' key specifying compatibility requirements.

    Returns:
        bool: True if the minion meets the conditions for the upgrade, False otherwise.
    """
    condition = upgrade.get('Condition')
    if not condition: #Upgrade is universal
        return True
    if 'Family' in condition and minion.get('Family') != condition['Family']: #Upgrade is for specific type of minion
        return False
    if 'Mob Spawning' in condition and not minion.get('Mob Spawning', 0): #Minions that spawn mobs
        return False
    if 'Name' in condition and minion.get('Name') != condition['Name']:
        return False
    return True

def apply_all_drop_modifiers(minion, fuel, u1,u2):
    """
    Modifies the minion's drops in-place based on fuel and upgrade modifiers.

    Args:
        minion (Dict): The minion dictionary containing 'Drops'.
        fuel (Dict): Fuel dictionary with optional 'Drops' multiplier.
        upgrades (Tuple[Dict, Dict]): Two upgrade dictionaries.
    """
    drop_multiplier = fuel.get("Drops", 1)
    chance_modifier = math.prod([u.get('Chance', 1) for u in (u1,u2)])

    for drop in minion['Drops']:
        drop['Amount'] *= drop_multiplier
        drop['Chance'] *= chance_modifier

def base_cpa(minion, bazaar, bazaar_cache):
    """
    Calculates and sets the minion's base Coins Per Action (CPA) from its drops.

    Args:
        minion (Dict): The minion dictionary, containing 'Drops'.
        bazaar (bool): Whether to use bazaar prices or NPC prices.
        bazaar_cache (Dict): A cache mapping item IDs to their bazaar prices.
    """
    minion['CPA'] = 0

    for drop in minion['Drops']:
        if bazaar:
            enchanted_id, enchanted_craft = next(iter(drop['Enchanted'].items()))

            enchanted_drops = drop['Amount'] * drop['Chance'] / enchanted_craft
            enchanted_price = bazaar_cache[enchanted_id]['Instant Buy']

            minion['CPA'] += enchanted_drops * drop['Chance'] * enchanted_price
        else:
            minion['CPA'] += drop['Amount'] * drop['Chance'] * drop['NPC Price']

def upgrade_cpa(minion, udrops, bazaar, bazaar_cache):
    """
    Calculates the CPA from the upgrade drops and adds it to the base CPA.

    Args:
        minion (Dict): The minion dictionary, containing 'Drops'.
        udrops (list): List of dictionaries, each prepresenting a drop
        bazaar (bool): Whether to use bazaar prices or NPC prices.
        bazaar_cache (Dict): A cache mapping item IDs to their bazaar prices.
    """
    minion['Flat Coins'] = 0
    for drop in udrops:
        cd = drop.get('Cooldown')
        enchanted_id, enchanted_craft = next(iter(drop['Enchanted'].items()))

        if cd:
            num_drops = 86400 / cd
            if bazaar:
                flat_coins = bazaar_cache[enchanted_id]['Instant Buy'] * num_drops / enchanted_craft

            else:
                flat_coins = num_drops * drop['NPC Price']
            
            minion['Flat Coins'] += flat_coins
        else:
            if bazaar:
                minion['CPA'] += drop['Amount'] / enchanted_craft * drop['Chance'] * bazaar_cache[enchanted_id]['Instant Buy']

            else:
                minion['CPA'] += drop['Amount'] * drop['Chance'] * drop['NPC Price']

def calculate_profit(minion,flags={},bazaar=False,bazaar_cache={},misc_upgrades={}):
    """
    Calculates the daily profit of each tier of each minion setup.

    Args: 
        minion (Dict): The minion dictionary, containing 'Drops'.
        flags (Dict): holds minion fuel and upgrades as well as their properties
        bazaar (bool): Whether to use bazaar prices or NPC prices.
        bazaar_cache (Dict): A cache mapping item IDs to their bazaar prices.
        misc_upgrades (Dict): holds miscellaneous upgrades like mithril infusion

    Returns:
        Tuple containing
            Upgrade combination key (tuple of the names of the fuel and upgrades)
            List of dictionaries representing minion profit for each tier
    """
    fuel = flags.get('Fuel',{})
    u1 = flags.get('Upgrade 1',{})
    u2 = flags.get('Upgrade 2',{})
    
    upgrade_cost = fuel.get('Cost',0) + u1.get('Cost',0) + u2.get('Cost',0)
    apply_all_drop_modifiers(minion, fuel, u1,u2)
    upgrade_drops = [drop for u in (u1,u2) if 'Drops' in u for drop in u['Drops']]

    speed_modifier = fuel.get('Speed',0) + u1.get('Speed',0) + u2.get('Speed',0)
    
    base_cpa(minion, bazaar, bazaar_cache)
    upgrade_cpa(minion, upgrade_drops, bazaar, bazaar_cache)

    return (
    (fuel.get('Name', ""), u1.get('Name', ""), u2.get('Name', "")),
    {
        "Speed Mod": round(speed_modifier,2),
        "Tiers": [
            {
                "Tier": tier['Tier'],
                "Speed": tier['Speed'],
                "CPA": minion['CPA'],
                "Flat": minion['Flat Coins'],
                "Cost": round(tier['Cost'] + upgrade_cost, 1)
            }
            for tier in minion['Tiers']
        ]
    }
)

def minion_processing(minions, fuels, upgrades, bazaar_cache,misc_upgrades):
    """
    Computes profit outcomes for all compatible fuel and upgrade combinations across all minions

    Args:
        minion (Dict): The minion dictionary, containing 'Drops'.
        fuels (Dict): Stores all the base fuel information and properties.
        upgrades (Dict): Stores all the base upgrade information and properties.
        bazaar_cache (Dict): A cache mapping item IDs to their bazaar prices.

    Returns:
        A nested dict with all of the desireable outputs
    """
    all_combinations = {}
    fuel_list = list(fuels.values())
    upgrade_items = list(upgrades.items())

    for minion in minions.values():
        if minion['Name'] not in all_combinations:
            all_combinations[minion['Name']] = {}

        for fuel in fuel_list:
            if not is_compatible(minion,fuel):
                continue

            for (key1, up1), (key2, up2) in itertools.combinations_with_replacement(upgrade_items, 2):
                if minion['Name'] == "Gravel Minion":
                    key2 = "FLINT_SHOVEL"
                    up2 = upgrades['FLINT_SHOVEL']

                if minion['Name'] in ['Iron Minion', 'Gold Minion', 'Cactus Minion']: 
                    key2 = "SUPER_COMPACTOR_3000"
                    up2 = upgrades['SUPER_COMPACTOR_3000']

                flags = {
                    "Fuel": fuel,
                    "Upgrade 1": up1,
                    "Upgrade 2": up2
                }

                if key1 == key2 and not up1.get("Dupe", False):
                    continue
                if not all(is_compatible(minion, u) for u in (up1, up2)):
                    continue

                bazaar = True if up1.get("Name") == "Super Compactor" or up2.get("Name") == "Super Compactor" else False
                combination,tiers = calculate_profit(copy.deepcopy(minion),flags,bazaar,bazaar_cache,misc_upgrades)
                all_combinations[minion['Name']][combination] = tiers
    return all_combinations

def fetch_and_process_data(misc_upgrades={}):
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

    minion_dict = minion_processing(copy.deepcopy(minions), copy.deepcopy(fuels), copy.deepcopy(upgrades), copy.deepcopy(bazaar_cache),misc_upgrades)
    minion_info = {
    minion_name: {
        "Family": data.get("Family"),
        "Mob Spawning": data.get("Mob Spawning")
    }
    for minion_name, data in minions.items()
}
    
    return minion_dict,minion_info

def create_all_combos(bazaar_cache):
    base_flags = {
        "Floating Crystal": {
            "Speed": 0.1,
            "Cost": 0
            },
        "Beacon": {
            "Speed": 0.1,
            "Cost": bazaar_cache['PLASMA']['Instant Sell'] * 6 + bazaar_cache['REFINED_MITHRIL']['Instant Sell'] * 55 + bazaar_cache['STARFALL']['Instant Sell'] * 64},
        "Power Crystal": {
            "Speed": 0.01,
            "Cost": bazaar_cache['SCORCHED_POWER_CRYSTAL']['Instant Sell'] / 2
            },
        "Mithril Infusion": {
            "Speed": 0.01,
            "Cost": bazaar_cache['MITHRIL_INFUSION']['Instant Sell']
            },
        "Free Will": {
            "Speed": 0.01,
            "Cost": bazaar_cache['FREE_WILL']['Instant Sell']
            },
        "Postcard": {
            "Speed": 0.01,
            "Cost": requests.get('https://sky.coflnet.com/api/auctions/tag/POSTCARD/active/bin').json()[0]['startingBid']
            }
    }
    all_combos = {}

    keys = list(base_flags)
    for r in range(0, len(keys)+1):
        for combo in itertools.combinations(keys, r):
            # Enforce condition: Power Crystal only if Beacon is present
            if 'Power Crystal' in combo and 'Beacon' not in combo:
                continue

            total_speed = sum(base_flags[key]['Speed'] for key in combo)
            total_cost = sum(base_flags[key]['Cost'] for key in combo)
        
            all_combos[tuple(sorted(combo))] = {
                'Speed': round(total_speed, 4),
                'Cost': round(total_cost, 2)
            }
    return all_combos

def create_minion_df(minion_data):
    rows = []
    for setup, setup_data in minion_data.items():
        for tier in setup_data['Tiers']:
            row = {
                'Fuel': setup[0],
                'Upgrade 1': setup[1],
                'Upgrade 2': setup[2],
                'Speed Mod': setup_data['Speed Mod'],
                **tier  # Unpack Tier dictionary (Tier, Speed, CPA, Flat, Cost)
            }
            rows.append(row)
    return pd.DataFrame(rows)

def apply_combo(df,combo,effect,minion_info):
    if "Floating Crystal" in combo and minion_info['Family'] not in ['Mining','Foraging', 'Farming'] or minion_info['Mob Spawning'] == 1:
        df['Speed Mod'] += effect.get('Speed') - 0.1
    else:
        df['Speed Mod'] += effect.get('Speed')
    df['Cost'] += effect.get('Cost')
    df['Profit'] = df['CPA'] * 86400 / (df['Speed'] / df['Speed Mod'] + df['Flat'])
    df = df.drop(columns=['Speed','CPA','Flat'])
    df.insert(df.columns.get_loc('Upgrade 2') + 1, 'Misc Upgrades', [combo]*len(df))
    return df    

def apply_all_combos(df,all_combos,minion_info):
    modified_frame = [
        apply_combo(df.copy(),combo,effect,minion_info)
        for combo,effect in all_combos.items()
    ]
    return pd.concat(modified_frame,ignore_index=True)