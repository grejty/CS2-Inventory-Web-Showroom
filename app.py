# cs2_showroom.py  ────────────────────────────────────────────────────
from flask import Flask, render_template_string
import requests, os, json, time, re
from dotenv import load_dotenv

load_dotenv()
API_URL          = "https://api.steampowered.com/IEconService/GetInventoryItemsWithDescriptions/v1/"
ACCESS_TOKEN     = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_URL = "https://store.steampowered.com/pointssummary/ajaxgetasyncconfig"

STEAM_ID, APP_ID, CONTEXT_ID = "76561198096622937", "730", "2"
LOCAL_DATA_FILE = "inventory_data.json"

if not ACCESS_TOKEN:
    raise RuntimeError("ACCESS_TOKEN chýba – doplň ho do .env súboru")

app = Flask(__name__)

# ─────────────────────────── HTML šablóna ───────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CS2 Inventory Showroom</title>
<style>
 body{font-family:Arial,sans-serif;background:#f4f4f4;text-align:center;margin:0}
 #inventory{display:flex;flex-wrap:wrap;justify-content:center;padding:20px}
 .skin-item{margin:10px;padding:12px;background:#fff;border:1px solid #ccc;width:240px;
            text-align:center;box-shadow:0 2px 5px rgba(0,0,0,.1);display:flex;
            flex-direction:column;justify-content:flex-start;height:300px}
 .skin-item img{width:100%;height:auto;margin-bottom:8px}
 .skin-item h3{font-size:16px;color:#222;margin:0 0 10px;min-height:42px}
 .meta{font-size:14px;color:#444;margin-top:4px}
 .label{font-weight:bold;color:#222}
 #total{margin:20px 0;font-size:20px;color:#555}
 .error-message{margin:20px 0;padding:10px;border:1px solid red;background:#ffe6e6;
                color:red;font-size:18px;display:inline-block;border-radius:5px;max-width:400px}
 .access-button{display:inline-block;margin-top:10px;padding:10px 20px;font-size:16px;
                color:#fff;background:#007bff;border:none;cursor:pointer;text-decoration:none;border-radius:5px}
 .access-button:hover{background:#0056b3}
</style>
</head>
<body>
<h1>My CS2 Inventory</h1>
{% if error %}
  <div class="error-message"><strong>Error updating inventory:</strong><br>{{ error.replace("Forbidden:", "").strip() }}</div>
  <div><a href="{{ access_token_url }}" target="_blank" class="access-button">Get Access Token</a></div>
{% else %}
  <div id="total">Total items: {{ total }}</div>
  <div id="inventory">
    {% for skin in skins %}
      <div class="skin-item">
        <img src="https://steamcommunity-a.akamaihd.net/economy/image/{{ skin.icon_url }}" alt="{{ skin.name }}">
        <h3>{{ skin.name }}</h3>
        {% if skin.exterior %}
          <div class="meta"><span class="label">Exterior:</span> {{ skin.exterior }}</div>
        {% endif %}
        <div class="meta"><span class="label">Tradable:</span> {{ skin.tradable }}</div>
      </div>
    {% endfor %}
  </div>
{% endif %}
</body>
</html>
"""

startup_error: str | None = None

# ─────────── helper na volanie Steamu s back-offom ──────────────────
def steam_get(params, tries=3, backoff=4):
    headers = {"User-Agent":
               ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.5735.199 Safari/537.36")}
    for attempt in range(tries):
        r = requests.get(API_URL, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            body = r.json().get("response", {})
            if body.get("assets"):
                return body
        if attempt < tries - 1:
            time.sleep(backoff)
    raise RuntimeError(f"Steam API vrátilo {r.status_code} alebo prázdnu odpoveď")

# ────────────────────── parsovanie helperov ─────────────────────────
_TRADABLE_RE = re.compile(r"Tradable/Marketable After\s+(.*)\s+GMT", re.I)

def tradable_text(desc: dict) -> str:
    if desc.get("tradable"):
        return "Yes"
    for od in desc.get("owner_descriptions", []):
        m = _TRADABLE_RE.search(od.get("value", ""))
        if m:
            return m.group(1).strip()
    return "No"

def exterior_text(desc: dict) -> str | None:
    for tag in desc.get("tags", []):
        if tag.get("category") == "Exterior":
            return tag.get("localized_tag_name")
    # fallback – pozri descriptions
    for d in desc.get("descriptions", []):
        if d.get("name") == "exterior_wear":
            return d.get("value", "").replace("Exterior:", "").strip()
    return None  # ak sa nenašlo

# ────────────────────── načítanie inventára ─────────────────────────
def fetch_inventory_from_api():
    params = {
        "access_token": ACCESS_TOKEN,
        "steamid":     STEAM_ID,
        "appid":       APP_ID,
        "contextid":   CONTEXT_ID,
        "get_descriptions": "true",
        "language": "english",
        "count": "1000"
    }

    data = steam_get(params)
    assets, descriptions = data["assets"], data["descriptions"]
    desc_map = {(d["classid"], d.get("instanceid", "0")): d for d in descriptions}

    skins: list[dict] = []
    for asset in assets:
        key, count = (asset["classid"], asset.get("instanceid", "0")), int(asset.get("amount", 1))
        desc = desc_map.get(key, {})
        for _ in range(count):                       # nestackujeme
            skins.append({
                "name":     desc.get("name", "Unknown"),
                "icon_url": desc.get("icon_url", ""),
                "exterior": exterior_text(desc),
                "tradable": tradable_text(desc),
            })
    return skins, len(skins)

# ──────────────────── lokálny JSON cache ────────────────────────────
def save_inventory_to_file(skins, total):
    with open(LOCAL_DATA_FILE, "w", encoding="utf-8") as fp:
        json.dump({"total": total, "skins": skins}, fp, ensure_ascii=False)

def load_inventory_from_file():
    if os.path.exists(LOCAL_DATA_FILE):
        with open(LOCAL_DATA_FILE, encoding="utf-8") as fp:
            data = json.load(fp)
        return data.get("skins", []), data.get("total", 0)
    return [], 0

# ─────────────────── aktualizácia inventára ─────────────────────────
def update_inventory():
    skins, total = fetch_inventory_from_api()
    save_inventory_to_file(skins, total)
    print(f"Inventory updated – {total} items.")

# ───────────────────────── routa / ──────────────────────────────────
@app.route("/")
def index():
    if startup_error:
        return render_template_string(HTML, skins=[], total=0,
                                      error=startup_error, access_token_url=ACCESS_TOKEN_URL)
    skins, total = load_inventory_from_file()
    return render_template_string(HTML, skins=skins, total=total,
                                  error=None, access_token_url=None)

# ───────────────────────── spustenie Flasku ─────────────────────────
if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        try:
            update_inventory()
        except Exception as e:
            startup_error = str(e)
            print(f"Error updating inventory: {startup_error}")
    app.run(debug=True)
