import json
import os
import re
from json.decoder import JSONDecoder

from django.conf import settings
from .helpers import identify_item_types, tradable_text, exterior_text, extract_stickers, rarity_details



def _resolve_inspect_link(template, asset_id):
    """Replace Steam placeholders in inspect links with concrete values."""
    if not template:
        return None

    link = template
    replacements = {}

    steam_id = getattr(settings, 'STEAM_ID', None)
    if steam_id:
        steam_id = str(steam_id)
        replacements.update({
            '%owner_steamid%': steam_id,
            '%original_owner_steamid%': steam_id,
            '%owner_steamid64%': steam_id,
        })

    if asset_id:
        replacements['%assetid%'] = str(asset_id)

    for placeholder, value in replacements.items():
        if placeholder in link and value:
            link = link.replace(placeholder, value)

    unresolved_tokens = set(re.findall(r'%([A-Za-z_]+)%', link))
    if unresolved_tokens:
        return None

    return link

def _normalize_descriptions(descriptions):
    if isinstance(descriptions, dict):
        if "descriptions" in descriptions:
            descriptions = descriptions.get("descriptions", [])
        else:
            descriptions = list(descriptions.values())
    return descriptions or []


def _merge_inventory_payloads(payloads):
    merged = {
        "assets": [],
        "descriptions": [],
        "asset_properties": []
    }

    seen_assets = set()
    for payload in payloads:
        assets = payload.get("assets", []) or []
        for asset in assets:
            asset_id = asset.get("assetid")
            if asset_id in seen_assets:
                continue
            seen_assets.add(asset_id)
            merged["assets"].append(asset)

        merged["descriptions"].extend(_normalize_descriptions(payload.get("descriptions", [])))

        for props in payload.get("asset_properties", []) or []:
            merged["asset_properties"].append(props)

    return merged


def process_inventory_data(data):
    """Transform raw Steam inventory payload into our skin list."""
    assets = data.get("assets", [])
    descriptions = _normalize_descriptions(data.get("descriptions", []))

    desc_map = {}
    for desc in descriptions:
        classid = desc.get("classid")
        if not classid:
            continue
        instanceid = desc.get("instanceid", "0")
        desc_map[(classid, instanceid)] = desc

    asset_properties_map = {}
    for prop_entry in data.get("asset_properties", []) or []:
        asset_id = prop_entry.get("assetid")
        for prop in prop_entry.get("asset_properties", []) or []:
            if asset_id not in asset_properties_map:
                asset_properties_map[asset_id] = {}
            if prop.get("name") == "Wear Rating" and prop.get("float_value") is not None:
                asset_properties_map[asset_id]["wear_rating"] = float(prop["float_value"])
            elif prop.get("name") == "Pattern Template" and prop.get("int_value") is not None:
                asset_properties_map[asset_id]["pattern_template"] = int(prop["int_value"])

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

        inspect_link = None
        if isinstance(desc.get("actions"), list) and desc["actions"]:
            inspect_link = desc["actions"][0].get("link")
        if not inspect_link and isinstance(desc.get("market_actions"), list) and desc["market_actions"]:
            inspect_link = desc["market_actions"][0].get("link")

        asset_id = asset.get("assetid")
        resolved_inspect_link = _resolve_inspect_link(inspect_link, asset_id)

        for _ in range(count):  # Don't stack items
            prop_data = asset_properties_map.get(asset_id, {})
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
                "rarity_color": rarity_color,
                "inspect_link": resolved_inspect_link,
                "asset_id": asset_id,
                "pattern_template": prop_data.get("pattern_template"),
                "float": prop_data.get("wear_rating")
            })
    return skins, len(skins), total_before_filters


def parse_inventory_json(raw_json):
    """Parse a manual JSON payload copied from Steam community inventory."""
    if isinstance(raw_json, (bytes, bytearray)):
        raw_json = raw_json.decode("utf-8")

    payloads = []

    if isinstance(raw_json, str):
        raw_json = raw_json.strip()
        if not raw_json:
            raise ValueError("Inventory JSON is empty")

        decoder = JSONDecoder()
        idx = 0
        length = len(raw_json)
        while idx < length:
            while idx < length and raw_json[idx] in "\r\n\t ":
                idx += 1
            if idx >= length:
                break
            obj, end = decoder.raw_decode(raw_json, idx)
            payloads.append(obj)
            idx = end
        if not payloads:
            raise ValueError("Invalid JSON payload: could not parse data")
    elif isinstance(raw_json, dict):
        payloads.append(raw_json)
    elif isinstance(raw_json, list):
        payloads.extend(raw_json)
    else:
        raise ValueError("Unsupported inventory payload type")

    normalized_payloads = []
    for payload in payloads:
        if not isinstance(payload, dict) or "assets" not in payload:
            raise ValueError("Each inventory payload must include 'assets' and 'descriptions'")
        normalized_payloads.append(payload)

    merged = _merge_inventory_payloads(normalized_payloads)
    return process_inventory_data(merged)

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

            skins = data.get("skins", [])
            for skin in skins:
                wear = skin.get("wear_rating")
                if wear is None and skin.get("float") is not None:
                    wear = skin.get("float")
                    skin["wear_rating"] = wear
                skin.setdefault("float", wear)
                skin.setdefault("pattern_template", None)

            return skins, data.get("total_before_filters", data.get("total", 0))
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

def update_inventory_from_manual(raw_json):
    """Update inventory using a manually pasted JSON payload."""
    try:
        current_skins, _ = load_inventory_from_file()

        selection_map = {}
        for skin in current_skins:
            key = skin['name']
            if skin.get('exterior'):
                key += f"_{skin['exterior']}"
            selection_map[key] = skin.get('selected', False)

        skins, filtered_total, total_before_filters = parse_inventory_json(raw_json)

        for skin in skins:
            key = skin['name']
            if skin.get('exterior'):
                key += f"_{skin['exterior']}"
            skin['selected'] = selection_map.get(key, False)

        save_inventory_to_file(skins, filtered_total, total_before_filters)
        return skins, filtered_total, total_before_filters
    except Exception as exc:
        print(f"Error updating inventory from manual payload: {exc}")
        raise
