import json
import os
import re
from decimal import Decimal, InvalidOperation
from json.decoder import JSONDecoder

from django.conf import settings
from .helpers import (
    identify_item_types,
    tradable_text,
    exterior_text,
    extract_stickers,
    rarity_details,
    build_tradable_info,
)

def _normalize_price(value):
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    try:
        price_decimal = Decimal(str(value))
        if price_decimal < 0:
            return None

        normalized_str = format(price_decimal, 'f')
        if '.' in normalized_str:
            normalized_str = normalized_str.rstrip('0').rstrip('.')
        return normalized_str
    except (InvalidOperation, ValueError, TypeError):
        return None


def _sanitize_note(value):
    if value is None:
        return ""

    if not isinstance(value, str):
        value = str(value)

    cleaned = value.strip()
    if len(cleaned) > 500:
        cleaned = cleaned[:500].rstrip()

    return cleaned


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

        collection_name = None
        for block in desc.get("descriptions", []) or []:
            if block.get("name") == "itemset_name":
                value = block.get("value")
                if isinstance(value, str):
                    collection_name = value.strip() or None
                break

        if not collection_name:
            for tag in desc.get("tags", []) or []:
                if tag.get("category") == "ItemSet":
                    value = tag.get("localized_tag_name") or tag.get("name")
                    if isinstance(value, str):
                        collection_name = value.strip() or None
                    break

        inspect_link = None
        if isinstance(desc.get("actions"), list) and desc["actions"]:
            inspect_link = desc["actions"][0].get("link")
        if not inspect_link and isinstance(desc.get("market_actions"), list) and desc["market_actions"]:
            inspect_link = desc["market_actions"][0].get("link")

        asset_id = asset.get("assetid")
        resolved_inspect_link = _resolve_inspect_link(inspect_link, asset_id)

        for _ in range(count):  # Don't stack items
            prop_data = asset_properties_map.get(asset_id, {})

            sticker_list = stickers.copy() if stickers else []
            patch_list = []
            if (item_type or "").lower() == "agent":
                filtered_stickers = []
                for sticker in sticker_list:
                    name = sticker.get("name") or ""
                    icon_url = sticker.get("icon_url")
                    is_patch = False
                    if isinstance(name, str) and name.strip().lower().startswith("patch:"):
                        is_patch = True
                    elif isinstance(icon_url, str) and "/patches/" in icon_url:
                        is_patch = True

                    if is_patch:
                        cleaned_name = name.split(":", 1)[1].strip() if ":" in name else name.strip()
                        patch_entry = {
                            "icon_url": icon_url,
                            "name": cleaned_name or name.strip(),
                        }
                        patch_list.append(patch_entry)
                    else:
                        filtered_stickers.append(sticker)
                sticker_list = filtered_stickers

            skins.append({
                "name": name,
                "icon_url": desc.get("icon_url", ""),
                "exterior": exterior_text(desc),
                "tradable_info": build_tradable_info(tradable_status),
                "selected": False,  # Default to not selected
                "weapon_type": weapon_type or "Other",
                "item_type": item_type or "Other",
                "stickers": sticker_list,
                "patches": patch_list,
                "rarity": rarity_name,
                "rarity_color": rarity_color,
                "inspect_link": resolved_inspect_link,
                "asset_id": asset_id,
                "pattern_template": prop_data.get("pattern_template"),
                "float": prop_data.get("wear_rating"),
                "collection": collection_name,
                "price_eur": None,
                "note": "",
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
        
    sanitized_skins = []
    for skin in skins:
        normalized_value = _normalize_price(skin.get("price_eur"))
        skin['price_eur'] = normalized_value
        normalized_skin = dict(skin)
        normalized_skin["price_eur"] = normalized_value

        note_value = _sanitize_note(skin.get("note"))
        normalized_skin["note"] = note_value
        skin["note"] = note_value

        patches = []
        for patch in normalized_skin.get("patches", []) or []:
            name = (patch.get("name") or "").strip()
            if name.lower().startswith("patch:"):
                name = name.split(":", 1)[1].strip()
            patches.append({
                "icon_url": patch.get("icon_url"),
                "name": name,
            })
        normalized_skin["patches"] = patches
        skin["patches"] = patches

        sanitized_skins.append(normalized_skin)

    data = {
        "skins": sanitized_skins,
        "total": filtered_total,
        "total_before_filters": total_before_filters
    }
        
    os.makedirs(os.path.dirname(settings.LOCAL_DATA_FILE), exist_ok=True)
    
    # Debug prints to verify data before saving
    print(f"\nSaving {len(sanitized_skins)} skins, {sum(1 for skin in sanitized_skins if skin.get('selected', False))} selected")
    
    with open(settings.LOCAL_DATA_FILE, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)
        
    # Verify the file was written correctly
    print(f"File saved to {settings.LOCAL_DATA_FILE}")

def load_inventory_from_file(auto_resave=True):
    """Load inventory data from JSON file."""
    try:
        if os.path.exists(settings.LOCAL_DATA_FILE) and os.path.getsize(settings.LOCAL_DATA_FILE) > 0:
            with open(settings.LOCAL_DATA_FILE, encoding="utf-8") as fp:
                data = json.load(fp)

            skins = data.get("skins", [])
            needs_resave = False
            for skin in skins:
                wear = skin.get("wear_rating")
                if wear is None and skin.get("float") is not None:
                    wear = skin.get("float")
                    skin["wear_rating"] = wear
                skin.setdefault("float", wear)
                skin.setdefault("pattern_template", None)
                skin.setdefault("patches", [])
                skin.setdefault("collection", None)
                sanitized_note = _sanitize_note(skin.get("note"))
                if skin.get("note") != sanitized_note:
                    needs_resave = True
                skin["note"] = sanitized_note
                # Get existing tradable status from tradable_info.raw or fallback to old tradable field for compatibility
                existing_tradable = skin.get("tradable_info", {}).get("raw") or skin.get("tradable", "Yes")
                skin["tradable_info"] = build_tradable_info(existing_tradable)
                # Remove redundant tradable field if it exists
                if "tradable" in skin:
                    del skin["tradable"]
                    needs_resave = True
                normalized_price = _normalize_price(skin.get("price_eur"))
                if skin.get("price_eur") != normalized_price:
                    needs_resave = True
                skin["price_eur"] = normalized_price

                if (skin.get("item_type") or "").lower() == "agent":
                    stickers = skin.get("stickers") or []
                    migrated_patches = []
                    remaining_stickers = []
                    for sticker in stickers:
                        name = (sticker.get("name") or "").strip()
                        icon_url = sticker.get("icon_url")
                        is_patch = False
                        if name.lower().startswith("patch:"):
                            is_patch = True
                        elif isinstance(icon_url, str) and "/patches/" in icon_url:
                            is_patch = True

                        if is_patch:
                            cleaned_name = name.split(":", 1)[1].strip() if ":" in name else name
                            migrated_patches.append({
                                "icon_url": icon_url,
                                "name": cleaned_name or name,
                            })
                        else:
                            remaining_stickers.append(sticker)

                    if migrated_patches:
                        existing_patches = skin.get("patches") or []
                        # Clean existing patch names and avoid duplicates by icon/name
                        cleaned_existing = []
                        seen = set()
                        for patch in existing_patches + migrated_patches:
                            pname = (patch.get("name") or "").strip()
                            if pname.lower().startswith("patch:"):
                                pname = pname.split(":", 1)[1].strip()
                            icon = patch.get("icon_url")
                            key = (pname.lower(), icon)
                            if key in seen:
                                continue
                            seen.add(key)
                            cleaned_existing.append({
                                "icon_url": icon,
                                "name": pname,
                            })
                        skin["patches"] = cleaned_existing
                        skin["stickers"] = remaining_stickers
                        needs_resave = True

            if needs_resave and auto_resave:
                save_inventory_to_file(
                    skins,
                    data.get("total", len(skins)),
                    data.get("total_before_filters", data.get("total", len(skins)))
                )

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

        # Use asset_id as the primary key for preserving selections, with fallback to name+exterior
        selection_map = {}
        price_map = {}
        note_map = {}
        for skin in current_skins:
            asset_id = skin.get('asset_id')
            if asset_id:
                # Primary key: asset_id (unique identifier)
                selection_map[asset_id] = skin.get('selected', False)
                price_map[asset_id] = _normalize_price(skin.get('price_eur'))
                note_map[asset_id] = _sanitize_note(skin.get('note'))
            else:
                # Fallback key: name + exterior (for items without asset_id)
                key = skin['name']
                if skin.get('exterior'):
                    key += f"_{skin['exterior']}"
                selection_map[key] = skin.get('selected', False)
                price_map[key] = _normalize_price(skin.get('price_eur'))
                note_map[key] = _sanitize_note(skin.get('note'))

        skins, filtered_total, total_before_filters = parse_inventory_json(raw_json)

        for skin in skins:
            asset_id = skin.get('asset_id')
            if asset_id and asset_id in selection_map:
                # Use asset_id for lookup if available
                skin['selected'] = selection_map.get(asset_id, False)
                skin['price_eur'] = _normalize_price(price_map.get(asset_id))
                skin['note'] = note_map.get(asset_id, "")
            else:
                # Fallback to name + exterior
                key = skin['name']
                if skin.get('exterior'):
                    key += f"_{skin['exterior']}"
                skin['selected'] = selection_map.get(key, False)
                skin['price_eur'] = _normalize_price(price_map.get(key))
                skin['note'] = note_map.get(key, "")

        save_inventory_to_file(skins, filtered_total, total_before_filters)
        return skins, filtered_total, total_before_filters
    except Exception as exc:
        print(f"Error updating inventory from manual payload: {exc}")
        raise
