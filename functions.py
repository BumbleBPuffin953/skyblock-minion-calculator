import math
import itertools
import copy
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

    misc_speed = sum(misc_upgrades.values())
    if "Power Crystal" in misc_upgrades and "Beacon" not in misc_upgrades:
        misc_speed -= misc_upgrades["Power Crystal"]
    if minion['Family'] not in ["Mining", "Farming", "Foraging"] and "Floating Crystal" in misc_upgrades:
        misc_speed -= misc_upgrades["Floating Crystal"]

    speed_modifier = 1 + fuel.get('Speed',0) + u1.get("Speed",0) + u2.get("Speed",0) + misc_speed
    
    base_cpa(minion, bazaar, bazaar_cache)
    upgrade_cpa(minion, upgrade_drops, bazaar, bazaar_cache)

    for tier in minion['Tiers']:
        tier['Speed'] /= speed_modifier
        tier['Actions'] = 86400 / (tier['Speed'] * 2) #Every other action generates items
        tier['Profit'] = round(minion['CPA'] * tier['Actions'] + minion['Flat Coins'] - fuel['Daily Cost'],1)
        
    return ((fuel.get('Name',""), u1.get('Name',""), u2.get('Name',"")),[
        {
            "Tier": tier['Tier'],
            "Profit": tier['Profit'],
            "Cost": round(tier['Cost'] + upgrade_cost,1)
        }
        for tier in minion['Tiers']])

def minion_processing(minions, fuels, upgrades, bazaar_cache):
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
    misc_combinations = generate_misc_combinations()
    fuel_list = list(fuels.values())
    upgrade_items = list(upgrades.items())

    misc_results = {}

    for misc_upgrade_set in misc_combinations:
        misc_key = tuple(sorted(misc_upgrade_set.keys()))
        misc_results[misc_key] = []

        for minion in minions.values():
            for fuel in fuel_list:
                if not is_compatible(minion,fuel):
                    continue

                for (key1, up1), (key2, up2) in itertools.combinations_with_replacement(upgrade_items,2):
                    if minion['Name'] == "Gravel Minion":
                        key2 = "FLINT_SHOVEL"
                        up2 = upgrades[key2]
                    if minion['Name'] in ['Iron Minion', 'Gold Minon', 'Cactus Minion']:
                        key2 = "DWARVEN_COMPACTOR"
                        up2 = upgrades[key2]
                    if key1 == key2 and not up1.get('Dupe',False):
                        continue
                    if not all(is_compatible(minion,u) for u in (up1,up2)):
                        continue
                    
                    flags = {
                        "Fuel": fuel,
                        "Upgrade 1": up1,
                        "Upgrade 2": up2
                    }
                    
                    bazaar = any(u.get('Name') == "Super Compactor" for u in (up1,up2))

                    combination,tiers = calculate_profit(
                        copy.deepcopy(minion),
                        flags,
                        bazaar,
                        bazaar_cache,
                        misc_upgrade_set
                    )

                    for tier in tiers:
                        result = {
                            "Minion": minion['Name'],
                            "Tier": tier['Tier'],
                            "Fuel": combination[0],
                            "Upgrade 1": combination[1],
                            "Upgrade 2": combination[2],
                            **{k: v for k, v in tier.items() if k != "Tier"}
                        }
                        misc_results[misc_key].append(result)
        print(misc_key,misc_results)
    misc_dfs = {key: pd.DataFrame(rows) for key,rows in misc_results.items()}
    return misc_dfs

def generate_misc_combinations():
    """
    Generate all valid combinations of misc upgrades.
    Power Crystal is only included if Beacon is also present.
    
    Returns:
        List of dictionaries with misc upgrade names as keys and their speed bonuses as values.
    """
    NEW_MISC_UPGRADES = {
        "Floating Crystal": 0.1,
        "Beacon": 0.1,
        "Power Crystal": 0.01, 
        "Infusion": 0.1,
        "Free Will": 0.1,
        "Postcard": 0.05
    }

    misc_names = list(NEW_MISC_UPGRADES.keys())
    all_combos = []

    for r in range(len(misc_names) + 1):
        for combo in itertools.combinations(misc_names, r):
            if "Power Crystal" in combo and "Beacon" not in combo:
                continue  # Skip invalid combo
            combo_dict = {name: NEW_MISC_UPGRADES[name] for name in combo}
            all_combos.append(combo_dict)

    return all_combos