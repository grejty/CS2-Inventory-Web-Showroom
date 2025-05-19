from flask import Flask, render_template_string
import requests
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_URL = "https://api.steampowered.com/IEconService/GetInventoryItemsWithDescriptions/v1/"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
STEAM_ID = "76561198096622937"
APP_ID = "730"
CONTEXT_ID = "2"
LOCAL_DATA_FILE = "inventory_data.json"
ACCESS_TOKEN_URL = "https://store.steampowered.com/pointssummary/ajaxgetasyncconfig"

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
            display: flex;
            flex-direction: column;
            justify-content: space-between; /* Ensures space between name and amount */
            height: 250px; /* Fixed height for consistency */
        }
        .skin-item h3 {
            font-size: 16px;
            color: #333;
            margin: 0; /* Avoid extra spacing */
        }
        .skin-item img {
            width: 100%;
            height: auto;
        }
        h3 {
            font-size: 16px;
            color: #333;
        }
        .amount {
            font-size: 14px;
            color: #666;
            margin-top: auto;
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
        .error-message {
            margin: 20px 0;
            padding: 10px;
            border: 1px solid red;
            background-color: #ffe6e6;
            color: red;
            font-size: 18px;
            display: inline-block;
            border-radius: 5px;
            text-align: center;
            max-width: 400px;
        }
        .access-button {
            display: inline-block;
            margin-top: 10px;
            padding: 10px 20px;
            font-size: 16px;
            color: white;
            background-color: #007bff;
            border: none;
            cursor: pointer;
            text-decoration: none;
            border-radius: 5px;
        }
        .access-button:hover {
            background-color: #0056b3;
        }
    </style>
</head>
<body>
    <h1>My CS2 Inventory</h1>
    {% if error %}
    <div class="error-message">
        <strong>Error updating inventory:</strong><br>
        {{ error.replace("Forbidden:", "").strip() }}
    </div>
    <div>
        <a href="{{ access_token_url }}" target="_blank" class="access-button">Get Access Token</a>
    </div>
{% else %}
    <div id="total">Total items: {{ total }}</div>
    <div id="inventory">
        {% for skin in skins %}
        <div class="skin-item">
            <img src="https://steamcommunity-a.akamaihd.net/economy/image/{{ skin.icon_url }}" alt="{{ skin.name }}"/>
            <h3>{{ skin.name }}</h3>
            <div class="amount">Amount: {{ skin.amount }}</div>
            {% if skin.float_value %}
            <div class="float-value">Float: {{ skin.float_value }}</div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
{% endif %}
</body>
</html>
"""

# Global variable to store the startup error
startup_error = None


# Function to fetch inventory from the API
def fetch_inventory_from_api():
    params = {
        "access_token": ACCESS_TOKEN,
        "steamid": STEAM_ID,
        "appid": APP_ID,
        "contextid": CONTEXT_ID,
        "get_descriptions": "true",
        "language": "english",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/114.0.5735.199 Safari/537.36",
    }

    try:
        response = requests.get(API_URL, params=params, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        data = response.json()
        print(json.dumps(data, indent=2))


        if "response" not in data:
            raise Exception("Invalid API response structure.")

        assets = data.get("response", {}).get("assets", [])
        descriptions = data.get("response", {}).get("descriptions", [])

        # Count classid occurrences
        classid_counts = {}
        for asset in assets:
            classid = asset.get("classid")
            if classid:
                classid_counts[classid] = classid_counts.get(classid, 0) + int(asset.get("amount", 1))

        # Map descriptions to skins
        skins = [
            {
                "name": description.get("market_hash_name", "Unknown Name"),
                "icon_url": description.get("icon_url", ""),
                "amount": classid_counts.get(description.get("classid"), 1),
                "float_value": None,  # Add float value logic later if needed
            }
            for description in descriptions
        ]

        total = sum(classid_counts.values())
        return skins, total

    except requests.HTTPError as e:
        if response.status_code == 403:
            raise Exception("Forbidden: Invalid or expired access token.")
        else:
            raise Exception(f"HTTP Error: {e}")
    except Exception as e:
        raise Exception(f"Error fetching inventory from API: {e}")


# Function to save inventory to a local file
def save_inventory_to_file(skins, total):
    data = {"total": total, "skins": skins}
    with open(LOCAL_DATA_FILE, "w") as file:
        json.dump(data, file)


# Function to load inventory from the local file
def load_inventory_from_file():
    if os.path.exists(LOCAL_DATA_FILE):
        with open(LOCAL_DATA_FILE, "r") as file:
            data = json.load(file)
        return data.get("skins", []), data.get("total", 0)
    return [], 0


# Attempt to update inventory at startup
try:
    skins, total = fetch_inventory_from_api()
    if total > 0:
        save_inventory_to_file(skins, total)
        print(f"Inventory successfully updated at startup. Total items: {total}.")
    else:
        raise Exception("Empty inventory received from Steam API.")
except Exception as e:
    startup_error = f"{e}"
    print(f"Error updating inventory at startup: {startup_error.replace('Forbidden:', '').strip()}")



# Route to display inventory
@app.route("/")
def display_inventory():
    try:
        if startup_error:
            raise Exception(startup_error)

        skins, total = load_inventory_from_file()
        return render_template_string(html_template, skins=skins, total=total, error=None, access_token_url=None)
    except Exception as e:
        return render_template_string(
            html_template,
            skins=[],
            total=0,
            error=f"{e}",
            access_token_url=ACCESS_TOKEN_URL,
        )


# Run the app
if __name__ == "__main__":
    app.run(debug=True)
