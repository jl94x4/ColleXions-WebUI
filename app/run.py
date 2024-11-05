
from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os

app = Flask(__name__)

# Paths to configuration and data files
CONFIG_PATH = '/app/data/config.json'
DATA_PATH = '/app/data/data.json'
SELECTED_COLLECTIONS_PATH = '/app/data/selected_collections.json'

# Load configuration to get interval time
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        return config  # Ensure it returns the full config dictionary

    # Default structure if config file does not exist
    return {
        "plex_url": "",
        "plex_token": "",
        "library_names": [],
        "next_run_interval": "Not set",
        "number_of_collections_to_pin": {},
        "special_collections": [],
        "categories": {}
    }

# Save configuration to JSON file
def save_config(config_data):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config_data, f, indent=4)

# Load last 5 collections from selected_collections.json
def load_recent_collections():
    if os.path.exists(SELECTED_COLLECTIONS_PATH):
        with open(SELECTED_COLLECTIONS_PATH, 'r') as f:
            collections = json.load(f)
            # Return the last 5 entries
            return collections[-5:] if len(collections) > 5 else collections
    return []

# Load data for the dashboard, including interval and selected collections
def load_data():
    # Load interval from config
    config_data = load_config()
    previously_pinned = load_recent_collections()
    
    # Check if previously_pinned is a list and contains items
    if isinstance(previously_pinned, list) and len(previously_pinned) > 0:
        currently_pinned = [previously_pinned[-1]]
    else:
        currently_pinned = []

    # Return a data dictionary for the dashboard
    return {
        "interval": config_data.get("next_run_interval", "Not set"),
        "currently_pinned": currently_pinned,
        "previously_pinned": previously_pinned
    }

@app.route('/')
def home():
    data = load_data()
    return render_template('dashboard.html', data=data)

@app.route('/config')
def config():
    config_data = load_config()
    return render_template('config.html', config=config_data)

@app.route('/api/status')
def status():
    data = load_data()
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=2000)
