from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.conf import settings
from .steam_api import load_inventory_from_file, update_inventory, save_inventory_to_file
from .helpers import WEAPON_TYPES, ITEM_TYPES, get_filter_counts

startup_error = None

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
        
        if action == 'refresh_inventory':
            try:
                # This will update everything including both counts
                skins, total, total_before_filters = update_inventory()
            except Exception as e:
                # Get filters with counts despite error
                filters = get_filter_counts(skins)
                context = {
                    'skins': skins,
                    'total': total,
                    'total_before_filters': total_before_filters,
                    'error': str(e),
                    'access_token_url': settings.STEAM_ACCESS_TOKEN_URL,
                    'filters': filters
                }
                return render(request, 'inventory/admin.html', context)
        
        elif action == 'save_selection':
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