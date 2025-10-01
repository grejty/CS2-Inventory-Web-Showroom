import re
from datetime import datetime
from html import unescape

# Common weapon and item type detection
WEAPON_TYPES = [
    "AK-47", "M4A4", "M4A1-S", "AWP", "Desert Eagle", "USP-S", "Glock-18", 
    "P250", "Five-SeveN", "Tec-9", "CZ75-Auto", "Dual Berettas", "P90", "MP9",
    "MAC-10", "UMP-45", "PP-Bizon", "MP7", "MP5-SD", "Nova", "XM1014", "MAG-7",
    "Sawed-Off", "M249", "Negev", "Galil AR", "FAMAS", "SG 553", "AUG", "SSG 08",
    "G3SG1", "SCAR-20", "Zeus x27", "Knife", "Bayonet", "Bowie Knife", "Butterfly Knife",
    "Falchion Knife", "Flip Knife", "Gut Knife", "Huntsman Knife", "Karambit", 
    "M9 Bayonet", "Shadow Daggers", "Navaja", "Stiletto Knife", "Talon Knife", 
    "Ursus Knife", "Classic Knife", "Paracord Knife", "Survival Knife", "Skeleton Knife",
    "Nomad Knife", "C4"
]

ITEM_TYPES = [
    "Agent", "Collectible", "Equipment", "Gloves", "Knife",
    "Machinegun", "Music Kit", "Pistol", "Rifle",
    "Shotgun", "SMG", "Sniper Rifle", "Sticker"
]


# Regex for tradable date
_TRADABLE_RE = re.compile(r"Tradable/Marketable After\s+(.*)\s+GMT", re.I)
_TRADE_PROTECTED_RE = re.compile(r"trade-protected.*until\s+(.*)\s+GMT", re.I)
_TRADE_PROTECTED_DISPLAY_RE = re.compile(
    r"(?:until|after)\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*\((\d{1,2}):(\d{2})(?::(\d{2}))?\)",
    re.I,
)

# Regex for sticker images embedded in HTML blobs
_STICKER_IMG_RE = re.compile(r'<img[^>]+src="([^\"]+)"[^>]*title="([^\"]+)"', re.I)


def extract_stickers(desc):
    """Parse sticker thumbnails from Steam description HTML."""
    if not isinstance(desc, dict):
        return []

    sticker_html = None
    for d in desc.get("descriptions", []):
        if d.get("name") == "sticker_info":
            sticker_html = d.get("value", "")
            break

    if not sticker_html:
        return []

    stickers = []
    for match in _STICKER_IMG_RE.finditer(sticker_html):
        src, title = match.groups()
        if src.startswith("//"):
            src = "https:" + src
        cleaned_title = unescape(title).strip() if title else ""
        if cleaned_title.lower().startswith("sticker:"):
            cleaned_title = cleaned_title.split(":", 1)[1].strip()
        stickers.append({
            "icon_url": src.strip(),
            "name": cleaned_title
        })

    return stickers


def rarity_details(desc):
    """Return rarity display name and color from a description object."""
    if not isinstance(desc, dict):
        return None, None

    rarity_name = None
    rarity_color = None

    for tag in desc.get("tags", []):
        if tag.get("category") == "Rarity":
            rarity_name = tag.get("localized_tag_name") or rarity_name
            rarity_color = tag.get("color") or rarity_color
            break

    if not rarity_color:
        rarity_color = desc.get("name_color")

    if isinstance(rarity_color, str):
        rarity_color = rarity_color.strip()
        if rarity_color and not rarity_color.startswith('#'):
            rarity_color = f'#' + rarity_color
    else:
        rarity_color = None

    return rarity_name, rarity_color

def tradable_text(desc):
    """Extract tradable status from item description, force time to 9:00:00."""
    if desc.get("tradable"):
        return "Yes"
    
    for od in desc.get("owner_descriptions", []):
        m = _TRADABLE_RE.search(od.get("value", ""))
        if m:
            date_time_str = m.group(1).strip()
            # Replace the time part with 9:00:00 using regex
            updated = re.sub(r"\(\d{1,2}:\d{2}:\d{2}\)", "(9:00:00)", date_time_str)
            return updated
        m2 = _TRADE_PROTECTED_RE.search(od.get("value", ""))
        if m2:
            date_time_str = m2.group(1).strip()
            updated = re.sub(r"\(\d{1,2}:\d{2}:\d{2}\)", "(9:00:00)", date_time_str)
            return f"Trade Protected until {updated}"

    return "No"


def _format_tradable_timestamp(tradable_status):
    """Return (formatted_text, iso_timestamp) for a Trade Protected status string."""
    if not isinstance(tradable_status, str):
        return None, None

    match = _TRADE_PROTECTED_DISPLAY_RE.search(tradable_status)
    if not match:
        return None, None

    date_part, hour_str, minute_str, second_str = match.groups()

    parsed_date = None
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            parsed_date = datetime.strptime(date_part, fmt)
            break
        except ValueError:
            continue

    if not parsed_date:
        return None, None

    hour = int(hour_str)
    minute = int(minute_str)
    second = int(second_str or 0)
    timestamp = parsed_date.replace(hour=hour, minute=minute, second=second)

    formatted = f"{timestamp.day}.{timestamp.month}.{timestamp.year} ({timestamp.hour}:{timestamp.strftime('%M')})"
    return formatted, timestamp.isoformat()


def build_tradable_info(tradable_status):
    """Construct structured tradable metadata for display purposes."""
    info = {
        "raw": tradable_status,
        "is_tradable": True,
        "lock_state": "unlocked",
        "unlock_text": None,
        "unlock_iso": None,
        "state_class": "meta--unlocked",
    }

    if not isinstance(tradable_status, str):
        return info

    normalized = tradable_status.strip()
    if not normalized:
        return info

    lower_status = normalized.lower()
    if lower_status in {"yes", "tradable"}:
        return info

    info["is_tradable"] = False
    info["lock_state"] = "locked"
    info["state_class"] = "meta--locked"

    formatted, iso_value = _format_tradable_timestamp(normalized)
    if formatted:
        info["unlock_text"] = f"Tradable on {formatted}"
        info["unlock_iso"] = iso_value

    return info

def exterior_text(desc):
    """Extract exterior quality from item description."""
    for tag in desc.get("tags", []):
        if tag.get("category") == "Exterior":
            return tag.get("localized_tag_name")
    # fallback – look at descriptions
    for d in desc.get("descriptions", []):
        if d.get("name") == "exterior_wear":
            return d.get("value", "").replace("Exterior:", "").strip()
    return None

def identify_item_types(name, desc=None):
    """Identify weapon and item types from item name and description."""
    weapon_type = None
    item_type = None
    
    # First identify specific weapon type
    for weapon in sorted(WEAPON_TYPES, key=len, reverse=True):
        if weapon.lower() in name.lower():
            weapon_type = weapon
            break
    
    # Check tags first if we have the full description object
    if desc and isinstance(desc, dict):
        # Check the "type" field directly first
        if "type" in desc and isinstance(desc["type"], str):
            item_type_str = desc["type"]
            # Check for specific item types in the type field
            if "Agent" in item_type_str:
                item_type = "Agent"
            elif "Equipment" in item_type_str:
                item_type = "Equipment"
            elif "Music Kit" in item_type_str:
                item_type = "Music Kit"
            elif "Collectible" in item_type_str:
                item_type = "Collectible"
            elif "Pass" in item_type_str:
                item_type = "Pass"
            elif "Graffiti" in item_type_str:
                item_type = "Graffiti"
            elif "Sticker" in item_type_str:
                item_type = "Sticker"
                
        # Check tags for Type information
        if not item_type:
            tags = desc.get("tags", [])
            for tag in tags:
                if tag.get("category") == "Type":
                    tag_name = tag.get("localized_tag_name", "")
                    if tag_name == "Agent":
                        item_type = "Agent"
                    elif tag_name == "Equipment":
                        item_type = "Equipment"
                    elif tag_name == "Collectible":
                        item_type = "Collectible"
                    elif tag_name == "Gloves":
                        item_type = "Gloves"
    
    # If we still haven't determined the type, use name matching
    if not item_type:
        # For knives
        if any(knife.lower() in name.lower() for knife in ["Knife", "Bayonet", "Karambit", "Daggers"]):
            item_type = "Knife"
        # For pistols
        elif any(x.lower() in name.lower() for x in ["Pistol", "Glock", "USP", "P250", "Five-SeveN", "Tec-9", "CZ75", "Dual Berettas", "Desert Eagle", "P2000", "R8 Revolver"]):
            item_type = "Pistol"
        # For SMGs
        elif any(x.lower() in name.lower() for x in ["SMG", "MP9", "MAC-10", "MP7", "MP5", "UMP", "P90", "PP-Bizon"]):
            item_type = "SMG"
        # For rifles
        elif any(x.lower() in name.lower() for x in ["AK-47", "M4A4", "M4A1", "Galil", "FAMAS", "SG 553", "AUG"]):
            item_type = "Rifle"
        # For sniper rifles
        elif any(x.lower() in name.lower() for x in ["AWP", "SSG 08", "SCAR-20", "G3SG1"]):
            item_type = "Sniper Rifle"
        # For shotguns
        elif any(x.lower() in name.lower() for x in ["Nova", "XM1014", "MAG-7", "Sawed-Off"]):
            item_type = "Shotgun"
        # For machineguns
        elif any(x.lower() in name.lower() for x in ["M249", "Negev"]):
            item_type = "Machinegun"
        # For gloves
        elif "Glove" in name or "Hand Wraps" in name or "Driver Gloves" in name:
            item_type = "Gloves"
        # For agents
        elif "Agent" in name or "Operator" in name or "Enforcer" in name or "Soldier" in name:
            item_type = "Agent"
        # For stickers
        elif "Sticker" in name:
            item_type = "Sticker"
        # For graffiti
        elif "Graffiti" in name or "Spray" in name:
            item_type = "Graffiti"
        # For music kits
        elif "Music Kit" in name:
            item_type = "Music Kit"
        # For cases and containers
        elif "Case" in name or "Container" in name:
            item_type = "Collectible"
        # For keys
        elif "Key" in name:
            item_type = "Tool"
        # For passes
        elif "Pass" in name or "Operation" in name:
            item_type = "Pass"
        # For tools
        elif "Tool" in name or "Kit" in name:
            item_type = "Tool"
        # For tags
        elif "Tag" in name or "Label" in name:
            item_type = "Tag"
        # For equipment
        elif "Equipment" in name or "Defuse Kit" in name:
            item_type = "Equipment"
    
    return weapon_type, item_type


def get_filter_counts(skins):
    """Generate filter options with counts."""
    # Define categories to skip
    CATEGORIES_TO_SKIP = ["C4", "Graffiti", "Pass", "Tag", "Tool"]
    # Initialize counters
    tradable_counts = {}
    weapon_type_counts = {}
    item_type_counts = {}
    
    # Count occurrences
    for skin in skins:
        tradable = skin.get("tradable", "Yes")  # Default to "Yes" since we filter out "No"
        weapon_type = skin.get("weapon_type", "Other")
        item_type = skin.get("item_type", "Other")
        
        # Skip counting unwanted categories
        if item_type in CATEGORIES_TO_SKIP:
            continue
        
        tradable_counts[tradable] = tradable_counts.get(tradable, 0) + 1
        weapon_type_counts[weapon_type] = weapon_type_counts.get(weapon_type, 0) + 1
        item_type_counts[item_type] = item_type_counts.get(item_type, 0) + 1
    
    # Format for display: list of tuples (name, count)
    tradable_filters = [(name, count) for name, count in tradable_counts.items()]
    weapon_filters = [(name, count) for name, count in weapon_type_counts.items()]
    item_filters = [(name, count) for name, count in item_type_counts.items()]
    
    # Sort by name
    tradable_filters.sort(key=lambda x: (x[0] != "Yes", x))
    weapon_filters.sort()
    item_filters.sort()
    
    return {
        'tradable': tradable_filters,
        'weapon_types': weapon_filters,
        'item_types': item_filters,
    }
