import json
import os
import time
import requests
from django.conf import settings
from .helpers import identify_item_types, tradable_text, exterior_text, extract_stickers, rarity_details

def steam_get(params, tries=3, backoff=4):
    """Call Steam API with retries and exponential backoff."""
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/114.0.5735.199 Safari/537.36")
    }
    for attempt in range(tries):
        r = requests.get(settings.STEAM_API_URL, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            body = r.json().get("response", {})
            if body.get("assets"):
                return body
        if attempt < tries - 1:
            time.sleep(backoff)
    raise RuntimeError(f"Steam API returned {r.status_code} or empty response")

def fetch_inventory_from_api():
    """Fetch inventory from Steam API and process the data."""
    params = {
        "access_token": settings.STEAM_ACCESS_TOKEN,
        "steamid": settings.STEAM_ID,
        "appid": settings.STEAM_APP_ID,
        "contextid": settings.STEAM_CONTEXT_ID,
        "get_descriptions": "true",
        "language": "english",
        "count": "1000"
    }

    data = steam_get(params)
    assets, descriptions = data["assets"], data["descriptions"]
    desc_map = {(d["classid"], d.get("instanceid", "0")): d for d in descriptions}
    
    # Count total items before filtering
    total_before_filters = sum(int(asset.get("amount", 1)) for asset in assets)

    # Define categories to skip
    CATEGORIES_TO_SKIP = ["C4", "Graffiti", "Pass", "Tag", "Tool"]

    skins = []
    for asset in assets:
        key, count = (asset["classid"], asset.get("instanceid", "0")), int(asset.get("amount", 1))
        desc = desc_map.get(key, {})
        name = desc.get("name", "Unknown")
        
        # Check tradability before doing other processing
        tradable_status = tradable_text(desc)
        if tradable_status == "No":
            continue  # Skip non-tradable items
            
        # Pass the full description object for better type detection
        weapon_type, item_type = identify_item_types(name, desc)
        
        # Skip items with unwanted types
        if item_type in CATEGORIES_TO_SKIP:
            continue
        
        stickers = extract_stickers(desc)
        rarity_name, rarity_color = rarity_details(desc)

        for _ in range(count):  # Don't stack items
            skins.append({
                "name": name,
                "icon_url": desc.get("icon_url", ""),
                "exterior": exterior_text(desc),
                "tradable": tradable_status,
                "selected": False,  # Default to not selected
                "weapon_type": weapon_type or "Other",
                "item_type": item_type or "Other",
                "stickers": stickers.copy() if stickers else [],
                "rarity": rarity_name,
                "rarity_color": rarity_color
            })
    return skins, len(skins), total_before_filters

def save_inventory_to_file(skins, filtered_total, total_before_filters=None):
    """Save inventory data to JSON file."""
    
    if total_before_filters is None:
        total_before_filters = filtered_total
        
    data = {
        "skins": skins,
        "total": filtered_total,
        "total_before_filters": total_before_filters
    }
        
    os.makedirs(os.path.dirname(settings.LOCAL_DATA_FILE), exist_ok=True)
    
    # Debug prints to verify data before saving
    print(f"\nSaving {len(skins)} skins, {sum(1 for skin in skins if skin.get('selected', False))} selected")
    
    with open(settings.LOCAL_DATA_FILE, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)
        
    # Verify the file was written correctly
    print(f"File saved to {settings.LOCAL_DATA_FILE}")

def load_inventory_from_file():
    """Load inventory data from JSON file."""
    try:
        if os.path.exists(settings.LOCAL_DATA_FILE) and os.path.getsize(settings.LOCAL_DATA_FILE) > 0:
            with open(settings.LOCAL_DATA_FILE, encoding="utf-8") as fp:
                data = json.load(fp)
            return data.get("skins", []), data.get("total_before_filters", data.get("total", 0))
        else:
            # Create default data structure and save it
            default_data = {"skins": [], "total": 0, "total_before_filters": 0}
            save_inventory_to_file(default_data["skins"], default_data["total"], default_data["total_before_filters"])
            return default_data["skins"], default_data["total_before_filters"]
    except json.JSONDecodeError as e:
        print(f"Error loading inventory data: {e}")
        # If the file is corrupted, create a new one with default data
        default_data = {"skins": [], "total": 0, "total_before_filters": 0}
        save_inventory_to_file(default_data["skins"], default_data["total"], default_data["total_before_filters"])
        return default_data["skins"], default_data["total_before_filters"]

def update_inventory():
    """Update inventory data from Steam API while preserving selection state."""
    try:
        # First load current inventory to get selection states
        current_skins, _ = load_inventory_from_file()
        
        # Create a lookup map for selected state based on item name
        selection_map = {}
        for skin in current_skins:
            key = skin['name']
            if skin.get('exterior'):
                key += f"_{skin['exterior']}"
            selection_map[key] = skin.get('selected', False)
        
        # Get new inventory data
        skins, filtered_total, total_before_filters = fetch_inventory_from_api()
        
        # Update selection state based on previous selections
        for skin in skins:
            key = skin['name']
            if skin.get('exterior'):
                key += f"_{skin['exterior']}"
            skin['selected'] = selection_map.get(key, False)
        
        # Save updated inventory
        save_inventory_to_file(skins, filtered_total, total_before_filters)
        # Return all three values
        return skins, filtered_total, total_before_filters
    except Exception as e:
        print(f"Error updating inventory: {e}")
        raise
