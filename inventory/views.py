from django.shortcuts import render

# Create your views here.
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect
from django.conf import settings
from .steam_api import (
    load_inventory_from_file,
    save_inventory_to_file,
    update_inventory_from_manual,
    _normalize_price,
)
from .helpers import WEAPON_TYPES, ITEM_TYPES, get_filter_counts

startup_error = None

# Helper to build Steam inventory URLs for manual import
def _steam_inventory_urls():
    steam_id = settings.STEAM_ID
    app_id = settings.STEAM_APP_ID
    base = "https://steamcommunity.com/inventory"
    return {
        'main': f"{base}/{steam_id}/{app_id}/2?l=english&count=2500",
        'protected': f"{base}/{steam_id}/{app_id}/16?l=english&count=2500",
    }

# {"appid":730,"classid":"2076633109","instanceid":"7517088041","currency":0,"background_color":"","icon_url":"i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGIGz3UqlXOLrxM-vMGmW8VNxu5Dx60noTyLijZGwpR1Y-s29e6M9eM-XHGaXzuBwufNscDqwmg0ijDGMnYftbyrFPVAoWcQjELQOuxO4k4e1N-nnsQfW2I5Mz3ivi3wb7Stj5ukAUKY7uvqAqS55_Pw","descriptions":[{"type":"html","value":"Exterior: Factory New","name":"exterior_wear"},{"type":"html","value":" ","name":"blank"},{"value":"Name Tag: ''远赴人间惊鸿宴 一睹人间盛世颜''","color":"b0c3d9","name":"nametag"},{"type":"html","value":" ","name":"blank"},{"type":"html","value":"The SSG08 bolt-action is a low-damage but very cost-effective sniper rifle, making it a smart choice for early-round long-range marksmanship. It has been given a hydrographic of a monstrous dragon snorting fire.\n\n<i>Sit on your horde and wait for any who come to take it</i>","name":"description"},{"type":"html","value":" ","name":"blank"},{"type":"html","value":"The Glove Collection","color":"9da1a9","name":"itemset_name"},{"type":"html","value":" ","name":"blank"},{"type":"html","value":"<br><div id=\"sticker_info\" class=\"sticker_info\" style=\"border: 2px solid rgb(102, 102, 102); border-radius: 6px; width=100; margin:4px; padding:8px;\"><center><img width=64 height=48 src=\"https://cdn.steamstatic.com/apps/730/icons/econ/stickers/illuminate_capsule_01/chinese_dragon.304b654d32117c442284e3a969bbf63074ee28d9.png\" title=\"Sticker: Guardian Dragon\"><br>Sticker: Guardian Dragon</center></div>","name":"sticker_info"}],"tradable":1,"actions":[{"link":"steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20S%owner_steamid%A%assetid%D5208664502278462180","name":"Inspect in Game..."}],"name":"SSG 08 | Dragonfire","name_color":"D2D2D2","type":"Covert Sniper Rifle","market_name":"SSG 08 | Dragonfire (Factory New)","market_hash_name":"SSG 08 | Dragonfire (Factory New)","market_actions":[{"link":"steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20M%listingid%A%assetid%D5208664502278462180","name":"Inspect in Game..."}],"commodity":0,"market_tradable_restriction":7,"market_marketable_restriction":7,"marketable":1,"tags":[{"category":"Type","internal_name":"CSGO_Type_SniperRifle","localized_category_name":"Type","localized_tag_name":"Sniper Rifle"},{"category":"Weapon","internal_name":"weapon_ssg08","localized_category_name":"Weapon","localized_tag_name":"SSG 08"},{"category":"ItemSet","internal_name":"set_community_15","localized_category_name":"Collection","localized_tag_name":"The Glove Collection"},{"category":"Quality","internal_name":"normal","localized_category_name":"Category","localized_tag_name":"Normal"},{"category":"Rarity","internal_name":"Rarity_Ancient_Weapon","localized_category_name":"Quality","localized_tag_name":"Covert","color":"eb4b4b"},{"category":"Exterior","internal_name":"WearCategory0","localized_category_name":"Exterior","localized_tag_name":"Factory New"}],"sealed":0},
# TODO pridat Inspect in Game link to the item details – po kliku a potvrdeni vyskakovacieho okna otvorí náhľad skinu v hre pomocou Steam linku


def index(request):
    """Public view showing selected inventory items."""
    if startup_error:
        context = {
            'error': startup_error,
            'access_token_url': settings.STEAM_ACCESS_TOKEN_URL,
            'filters': {'tradable': [], 'weapon_types': [], 'item_types': []},
            'skins': [],
            'total': 0
        }
    else:
        # Load the most recent inventory data
        skins, _ = load_inventory_from_file()
        
        # Filter to only selected skins
        selected_skins = [skin for skin in skins if skin.get("selected", False)]
        
        # Get filters with counts
        filters = get_filter_counts(selected_skins)
        
        context = {
            'skins': selected_skins,
            'total': len(selected_skins),
            'error': None,
            'access_token_url': None,
            'filters': filters
        }
    
    return render(request, 'inventory/index.html', context)

def admin_view(request):
    """Admin view for managing inventory selection."""
    if startup_error:
        context = {
            'error': startup_error,
            'access_token_url': settings.STEAM_ACCESS_TOKEN_URL,
            'filters': {'tradable': [], 'weapon_types': [], 'item_types': []},
            'skins': [],
            'total': 0,
            'total_before_filters': 0,
            'steam_inventory_urls': _steam_inventory_urls(),
            'pasted_json_main': '',
            'pasted_json_protected': '',
            'show_manual_import': False
        }
        return render(request, 'inventory/admin.html', context)
    
    # Handle form submission to save selection or refresh inventory
    if request.method == "POST":
        action = request.POST.get('action')
        
        if action == 'refresh_inventory':
            manual_json_main = request.POST.get('inventory_json_main', '').strip()
            manual_json_protected = request.POST.get('inventory_json_protected', '').strip()

            payload_segments = []
            if manual_json_protected:
                payload_segments.append(manual_json_protected)
            if manual_json_main:
                payload_segments.append(manual_json_main)

            if not payload_segments:
                skins, total_before_filters = load_inventory_from_file()
                total = len(skins)
                context = {
                    'error': None,
                    'access_token_url': settings.STEAM_ACCESS_TOKEN_URL,
                    'filters': get_filter_counts(skins),
                    'skins': skins,
                    'total': total,
                    'total_before_filters': total_before_filters,
                    'steam_inventory_urls': _steam_inventory_urls(),
                    'pasted_json_main': manual_json_main,
                    'pasted_json_protected': manual_json_protected,
                    'show_manual_import': True
                }
                return render(request, 'inventory/admin.html', context)

            try:
                combined_payload = "\n".join(payload_segments)
                update_inventory_from_manual(combined_payload)
            except ValueError as exc:
                skins, total_before_filters = load_inventory_from_file()
                total = len(skins)
                context = {
                    'error': str(exc),
                    'access_token_url': settings.STEAM_ACCESS_TOKEN_URL,
                    'filters': get_filter_counts(skins),
                    'skins': skins,
                    'total': total,
                    'total_before_filters': total_before_filters,
                    'steam_inventory_urls': _steam_inventory_urls(),
                    'pasted_json_main': manual_json_main,
                    'pasted_json_protected': manual_json_protected,
                    'show_manual_import': True
                }
                return render(request, 'inventory/admin.html', context)
            except Exception as exc:
                skins, total_before_filters = load_inventory_from_file()
                total = len(skins)
                context = {
                    'error': f'Unexpected error processing inventory: {exc}',
                    'access_token_url': settings.STEAM_ACCESS_TOKEN_URL,
                    'filters': get_filter_counts(skins),
                    'skins': skins,
                    'total': total,
                    'total_before_filters': total_before_filters,
                    'steam_inventory_urls': _steam_inventory_urls(),
                    'pasted_json_main': manual_json_main,
                    'pasted_json_protected': manual_json_protected,
                    'show_manual_import': True
                }
                return render(request, 'inventory/admin.html', context)

            # Redirect after successful refresh
            return redirect('inventory:admin')
        
        elif action == 'save_selection':
            # Load current inventory data for saving selection
            skins, total_before_filters = load_inventory_from_file()
            
            # Get selected indices from form
            selected_indices = request.POST.getlist('selected_skins')
            
            # If clear_all flag is set or no selections were made
            clear_all = request.POST.get('clear_all') == 'true' or not selected_indices
            
            if clear_all:
                # Set all skins to not selected
                for skin in skins:
                    skin['selected'] = False
            else:
                # Convert to integers
                selected_indices = [int(idx) for idx in selected_indices]
                
                # Update selection status for all skins
                for i, skin in enumerate(skins):
                    skin['selected'] = (i in selected_indices)

            # Update price information for each skin
            for i, skin in enumerate(skins):
                price_key = f'price_{i}'
                raw_value = request.POST.get(price_key, '')
                previous_price = skin.get('price_eur')
                if raw_value is None:
                    continue
                raw_value = raw_value.strip()
                if not raw_value:
                    skin['price_eur'] = None
                    continue

                normalized = raw_value.replace(',', '.').replace('€', '').strip()
                try:
                    price_decimal = Decimal(normalized)
                    if price_decimal < 0:
                        raise InvalidOperation
                    sanitized_price = _normalize_price(normalized)
                    if sanitized_price is None:
                        raise InvalidOperation
                    skin['price_eur'] = sanitized_price
                except (InvalidOperation, ValueError):
                    # Keep previous price if parsing fails
                    skin['price_eur'] = previous_price
    
            # Save updated inventory back to file
            save_inventory_to_file(skins, len(skins), total_before_filters)
            
            # Redirect after saving
            return redirect('inventory:admin')
    
    # Load current inventory data for GET request (no automatic refresh)
    skins, total_before_filters = load_inventory_from_file()
    total = len(skins)
    
    # Display the admin interface (GET request)
    context = {
        'skins': skins,
        'total': total,
        'total_before_filters': total_before_filters,
        'error': None,
        'access_token_url': None,
        'filters': get_filter_counts(skins),
        'steam_inventory_urls': _steam_inventory_urls(),
        'pasted_json_main': '',
        'pasted_json_protected': '',
        'show_manual_import': False
    }
    return render(request, 'inventory/admin.html', context)
