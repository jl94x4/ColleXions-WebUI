from flask import Flask, render_template, request, redirect, url_for
import json
import os
import subprocess
import psutil
import requests

app = Flask(__name__)

# Path to your configuration file
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    """Loads configuration data from config.json."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as file:
            config = json.load(file)
            print("Config data loaded:", config)  # Debug print to confirm data
            return config
    print("Config file not found.")  # Debug print if config is missing
    return {}

def save_config(data):
    """Saves configuration data back to config.json."""
    with open(CONFIG_PATH, 'w') as file:
        json.dump(data, file, indent=4)
        print("Config data saved:", data)  # Debug print to confirm saving

@app.route('/')
def dashboard():
    config = load_config()
    currently_pinned = ["Collection A", "Collection B"]  # Placeholder
    previously_pinned = ["Collection X", "Collection Y", "Collection Z"]  # Placeholder
    next_run_interval = config.get("pinning_interval", 21600)
    collections = fetch_mdb_collections()  # Fetch collections from MDBlist

    return render_template('dashboard.html', 
                           currently_pinned=currently_pinned, 
                           previously_pinned=previously_pinned,
                           next_run_interval=next_run_interval,
                           collections=collections)

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        print("Pinning collections initiated.")  # Debugging line
        # Collect form data and prepare it for saving
        config_data = {
            "plex_url": request.form.get("plexUrl"),
            "plex_token": request.form.get("plexToken"),
            "library_names": request.form.getlist("library_names[]"),
            "pinning_interval": int(request.form.get("pinningInterval", 360)),
            "number_of_collections_to_pin": dict(zip(
                request.form.getlist("collectionsToPinLibrary[]"), 
                map(int, request.form.getlist("collectionsToPinCount[]"))
            )),
            "special_collections": [
                {
                    "start_date": start,
                    "end_date": end,
                    "collection_names": [name.strip() for name in names.split(',')]
                }
                for start, end, names in zip(
                    request.form.getlist("startDate[]"),
                    request.form.getlist("endDate[]"),
                    request.form.getlist("collectionNames[]")
                )
            ],
            "use_inclusion_list": "use_inclusion_list" in request.form,
            "inclusion_list": request.form.getlist("inclusion_list[]"),
            "exclusion_list": request.form.getlist("exclusion_list[]"),
            "discord_webhook_url": request.form.get("discordWebhook"),
            "categories": {
                "Movies": {},
                "TV Shows": {}
            }
        }

        # Collect and save category data
        movie_categories = request.form.getlist("movie_categories[]")
        tv_show_categories = request.form.getlist("tv_show_categories[]")

        for category in movie_categories:
            config_data["categories"]["Movies"][category] = {
                "always_call": request.form.get("always_call_" + category) == "on",
                "collections": request.form.getlist(category + "_collections[]")
            }

        for category in tv_show_categories:
            config_data["categories"]["TV Shows"][category] = {
                "always_call": request.form.get("always_call_" + category) == "on",
                "collections": request.form.getlist(category + "_collections[]")
            }

        # Save the config data
        save_config(config_data)

        # Always restart collexions.py after saving the configuration
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == "python3" and "collexions.py" in proc.cmdline():
                print("Killing existing collexions.py process...")
                proc.kill()  # Kill the existing process

        print("Starting new instance of collexions.py...")
        subprocess.Popen(['python3', os.path.join(os.path.dirname(__file__), 'collexions.py')])  # Ensure the path is correct

        return redirect(url_for('config'))

    # For GET requests, load config data and pass it to the template
    config = load_config()
    return render_template('config.html', config=config)

def fetch_mdb_collections():
    """Fetch collections from MDBlist."""
    mdb_api_url = "https://api.mdblist.com/v1/collections"  # Example endpoint
    response = requests.get(mdb_api_url)

    if response.status_code == 200:
        return response.json()  # Returns a list of collections
    else:
        print("Error fetching data from MDBlist:", response.status_code, response.text)
        return []

if __name__ == '__main__':
    # Start collexions.py as a separate process only if not already running
    print("Checking if collexions.py is running...")
    collexions_running = any(proc.info['name'] == "python3" and "collexions.py" in proc.cmdline() for proc in psutil.process_iter(['pid', 'name']))
    if not collexions_running:
        print("Starting collexions.py...")
        subprocess.Popen(['python3', os.path.join(os.path.dirname(__file__), 'collexions.py')])

    app.run(host='0.0.0.0', port=2000, debug=False)  # Debug set to False for production
