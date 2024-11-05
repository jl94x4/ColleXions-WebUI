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
    next_run_interval = config_data.get("next_run_interval", "No interval set")
    
    # Load last 5 selected collections
    previously_pinned = load_recent_collections()
    
    # Determine currently pinned collection (last one from selected_collections.json)
    currently_pinned = [previously_pinned[-1]] if previously_pinned else []

    return {
        "previously_pinned": previously_pinned[:-1],  # All but the latest as previously pinned
        "currently_pinned": currently_pinned,
        "next_run_interval": next_run_interval
    }

# Home page route displaying the dashboard
@app.route('/')
def home():
    # Load data for the dashboard
    data = load_data()

    # Render the dashboard with actual data
    return render_template('index.html', 
                           previously_pinned=data["previously_pinned"], 
                           currently_pinned=data["currently_pinned"], 
                           next_run_interval=data["next_run_interval"])

# Configuration page route
@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        # Handle form data submission and update the config file
        plex_url = request.form.get('plexUrl')
        plex_token = request.form.get('plexToken')
        library_names = request.form.getlist('library_names[]')
        collections_to_pin_libraries = request.form.getlist('collectionsToPinLibrary[]')
        collections_to_pin_counts = request.form.getlist('collectionsToPinCount[]')

        # Build the data to save
        config_data = load_config()
        config_data['plex_url'] = plex_url
        config_data['plex_token'] = plex_token
        config_data['library_names'] = library_names

        # Combine collections to pin libraries and counts
        config_data['number_of_collections_to_pin'] = {
            library: int(count) for library, count in zip(collections_to_pin_libraries, collections_to_pin_counts)
        }

        # Save the configuration
        save_config(config_data)
        return redirect(url_for('config'))

    # GET request: Load the config data and render the config page
    config_data = load_config()
    return render_template('config.html', config=config_data)

# JSON API endpoint for current status
@app.route('/api/status')
def status():
    # Load data to provide current status
    data = load_data()
    return jsonify({
        "currently_pinned": data.get("currently_pinned", []),
        "next_run_interval": data.get("next_run_interval", "No interval set")
    })
if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=2000)
    except Exception as e:
        print(f"Failed to start Flask app: {e}")
