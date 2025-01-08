from flask import Flask, render_template_string, jsonify
import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration
API_URL = "https://api.steampowered.com/IEconService/GetInventoryItemsWithDescriptions/v1/"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
STEAM_ID = "76561198096622937"
APP_ID = "730"
CONTEXT_ID = "2"

if not ACCESS_TOKEN:
    raise Exception("Access token not found in environment variables.")

# Initialize Flask application
app = Flask(__name__)

# HTML template for displaying inventory
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CS2 Inventory Showroom</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            text-align: center;
            margin: 0;
            padding: 0;
        }
        #inventory {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            padding: 20px;
        }
        .skin-item {
            margin: 10px;
            padding: 10px;
            background-color: white;
            border: 1px solid #ccc;
            width: 200px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        .skin-item img {
            width: 100%;
            height: auto;
        }
        h3 {
            font-size: 16px;
            color: #333;
        }
        .float-value {
            font-size: 14px;
            color: #666;
        }
        #total {
            margin: 20px 0;
            font-size: 20px;
            color: #555;
        }
    </style>
</head>
<body>
    <h1>My CS2 Inventory</h1>
    <div id="total">Total items: {{ total }}</div>
    <div id="inventory">
        {% for skin in skins %}
        <div class="skin-item">
            <img src="https://steamcommunity-a.akamaihd.net/economy/image/{{ skin.icon_url }}" alt="{{ skin.name }}">
            <h3>{{ skin.name }}</h3>
            {% if skin.float_value %}
            <div class="float-value">Float: {{ skin.float_value }}</div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

# Function to fetch inventory from the API
def fetch_inventory():
    params = {
        "access_token": ACCESS_TOKEN,
        "steamid": STEAM_ID,
        "appid": APP_ID,
        "contextid": CONTEXT_ID,
        "get_descriptions": "true",
        "language": "english",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36",
    }

    try:
        response = requests.get(API_URL, params=params, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        data = response.json()

        total = data.get("response", {}).get("total_inventory_count", 0)
        descriptions = data.get("response", {}).get("descriptions", [])

        # Format skins
        skins = []
        for description in descriptions:
            skin = {
                "name": description.get("market_hash_name", "Unknown Name"),
                "icon_url": description.get("icon_url", ""),
                "float_value": None,  # Default value
            }

            # Check for float value in attributes
            if "tags" in description:
                for tag in description["tags"]:
                    if tag.get("category") == "Wear" and "float" in tag.get("internal_name", "").lower():
                        skin["float_value"] = tag["localized_tag_name"]

            skins.append(skin)

        return skins, total
    except requests.RequestException as e:
        raise Exception(f"Error fetching inventory from API: {e}")


# Route to display inventory
@app.route("/")
def display_inventory():
    try:
        skins, total = fetch_inventory()
        return render_template_string(html_template, skins=skins, total=total)
    except Exception as e:
        return f"Error: {e}"


# Route to fetch inventory as JSON
@app.route("/api/inventory")
def get_inventory_json():
    try:
        skins, total = fetch_inventory()
        return jsonify({"total": total, "skins": skins})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Run the app
if __name__ == "__main__":
    app.run(debug=True)
