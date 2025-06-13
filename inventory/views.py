from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.conf import settings
from .steam_api import load_inventory_from_file, save_inventory_to_file
from .helpers import WEAPON_TYPES, ITEM_TYPES, get_filter_counts

startup_error = None

# {"category":"ItemSet","internal_name":"set_community_18","localized_category_name":"Collection","localized_tag_name":"The Spectrum 2 Collection"},{"category":"Quality","internal_name":"normal","localized_category_name":"Category","localized_tag_name":"Normal"},{"category":"Rarity","internal_name":"Rarity_Ancient_Weapon","localized_category_name":"Quality","localized_tag_name":"Covert","color":"eb4b4b"},{"category":"Exterior","internal_name":"WearCategory3","localized_category_name":"Exterior","localized_tag_name":"Well-Worn"}]},{"appid":730,"classid":"3113396825","instanceid":"7169386124","currency":0,"background_color":"","icon_url":"-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXH5ApeO4YmlhxYQknCRvCo04DEVlxkKgpot621FAR17PLfYQJM6dO4m4mZqPrxN7LEmyVVsJAijL7D8I2njAzlqkY9Nm_ycYadewY2Z1zX8lPsyO3tjZW_vpmY1zI97fJZpdj_","descriptions":[{"type":"html","value":"Exterior: Field-Tested","name":"exterior_wear"},{"type":"html","value":" ","name":"blank"},{"type":"html","value":"High risk and high reward, the infamous AWP is recognizable by its signature report and one-shot, one-kill policy. It has been custom painted with two stylized blue-magenta women over a grayscale background.\n\n<i>\"They took comfort in each other's despair\"</i>","name":"description"},{"type":"html","value":" ","name":"blank"},{"type":"html","value":"The Danger Zone Collection","color":"9da1a9","name":"itemset_name"},{"type":"html","value":" ","name":"blank"},{"type":"html","value":"<br><div id=\"sticker_info\" class=\"sticker_info\" style=\"border: 2px solid rgb(102, 102, 102); border-radius: 6px; width=100; margin:4px; padding:8px;\"><center><img width=64 height=48 src=\"https://steamcdn-a.akamaihd.net/apps/730/icons/econ/stickers/rio2022/big_glitter.28d9ddc3471709f78951d85d960c61ead259e037.png\" title=\"Sticker: BIG (Glitter) | Rio 2022\"><img width=64 height=48 src=\"https://steamcdn-a.akamaihd.net/apps/730/icons/econ/stickers/paris2023/hero.3f070c87a246fd89415ee21515c8aef6274adb47.png\" title=\"Sticker: Heroic | Paris 2023\"><br>Sticker: BIG (Glitter) | Rio 2022, Heroic | Paris 2023</center></div>","name":"sticker_info"}],"tradable":0,"actions":[{"link":"steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20S%owner_steamid%A%assetid%D5054345336946955845","name":"Inspect in Game..."}],"owner_descriptions":[{"type":"html","value":" "},{"type":"html","value":"Tradable/Marketable After Jun 19, 2025 (7:00:00) GMT","color":"ff4040"}],"name":"AWP | Neo-Noir","name_color":"D2D2D2","type":"Covert Sniper Rifle","market_name":"AWP | Neo-Noir (Field-Tested)","market_hash_name":"AWP | Neo-Noir (Field-Tested)","market_actions":[{"link":"steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20M%listingid%A%assetid%D5054345336946955845","name":"Inspect in Game..."}],"commodity":0,"market_tradable_restriction":7,"market_marketable_restriction":7,"marketable":0,"tags":[{"category":"Type","internal_name":"CSGO_Type_SniperRifle","localized_category_name":"Type","localized_tag_name":"Sniper Rifle"},{"category":"Weapon","internal_name":"weapon_awp","localized_category_name":"Weapon","localized_tag_name":"AWP"},
# TODO pridať nalepky takym sposobm, ze bude niekde v rohu nahlady ich ikoniek a cez hover sa vypise ich nazov
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
            'total_before_filters': 0
        }
        return render(request, 'inventory/admin.html', context)
    
    # Load current inventory data
    skins, total_before_filters = load_inventory_from_file()
    total = len(skins)
    
    # Handle form submission to save selection or refresh inventory
    if request.method == "POST":
        action = request.POST.get('action')
        
        if action == 'save_selection':
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
    
            # Save updated inventory back to file
            save_inventory_to_file(skins, total, total_before_filters)
            
            # Add this line to redirect after saving
            return redirect('inventory:admin')
    
    # Display the admin interface (GET request)
    context = {
        'skins': skins,
        'total': total,
        'total_before_filters': total_before_filters,
        'error': None,
        'access_token_url': None,
        'filters': get_filter_counts(skins)
    }
    return render(request, 'inventory/admin.html', context)