from flask import Flask, render_template_string, jsonify
import json

# Názov súboru s inventárom
inventory_file = "inventory_data.json"

# Inicializácia Flask aplikácie
app = Flask(__name__)

# HTML šablóna pre zobrazenie skinov
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
            width: 150px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        .skin-item img {
            width: 100%;
        }
        h3 {
            font-size: 14px;
            color: #333;
        }
        #total {
            margin-bottom: 20px;
            font-size: 18px;
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
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

# Funkcia na načítanie inventára zo súboru
def fetch_inventory():
    try:
        with open(inventory_file, "r") as file:
            data = json.load(file)
            # Získanie sekcie "assets" pre celkový počet
            assets = data.get("assets", [])
            descriptions = data.get("descriptions", [])
            # Mapovanie na zobraziteľné položky zo sekcie "descriptions"
            skins = [
                {
                    "name": description.get("market_hash_name", "Unknown Name"),
                    "icon_url": description.get("icon_url", "")
                }
                for description in descriptions
            ]
            return skins, len(assets)  # Počet položiek v "assets"
    except FileNotFoundError:
        raise Exception(f"Súbor {inventory_file} neexistuje.")
    except json.JSONDecodeError:
        raise Exception("Chyba pri čítaní JSON údajov zo súboru.")

# Hlavná trasa (route) pre zobrazenie inventára
@app.route("/")
def display_inventory():
    try:
        skins, total = fetch_inventory()  # Získanie skinov a celkového počtu
        return render_template_string(html_template, skins=skins, total=total)
    except Exception as e:
        return f"Chyba: {e}"

# Endpoint pre získanie inventára ako JSON (voliteľné)
@app.route("/api/inventory")
def get_inventory_json():
    try:
        skins, total = fetch_inventory()
        return jsonify({"total": total, "skins": skins})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Spustenie aplikácie na localhoste
if __name__ == "__main__":
    app.run(debug=True)
