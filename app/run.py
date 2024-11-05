from flask import Flask, render_template, request, redirect, url_for
import json
import os

app = Flask(__name__)

# Set the path to your config.json file
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    """Loads configuration data from config.json"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as file:
            config = json.load(file)
            print("Config data loaded:", config)  # Debug print to confirm data
            return config
    print("Config file not found.")  # Debug print if config is missing
    return {}

def save_config(data):
    """Saves configuration data back to config.json"""
    with open(CONFIG_PATH, 'w') as file:
        json.dump(data, file, indent=4)
        print("Config data saved:", data)  # Debug print to confirm saving

@app.route('/')
def dashboard():
    config = load_config()
    currently_pinned = ["Collection A", "Collection B"]  # Placeholder
    previously_pinned = ["Collection X", "Collection Y", "Collection Z"]  # Placeholder
    next_run_interval = config.get("pinning_interval", 21600)

    return render_template('dashboard.html', 
                           currently_pinned=currently_pinned, 
                           previously_pinned=previously_pinned,
                           next_run_interval=next_run_interval)

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        # Collect form data and prepare it for saving
        config_data = {
            "plex_url": request.form.get("plexUrl"),
            "plex_token": request.form.get("plexToken"),
            "library_names": request.form.getlist("library_names[]"),
            "pinning_interval": int(request.form.get("pinningInterval", 21600)),
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
            # Inclusion and Exclusion Lists
            "use_inclusion_list": "use_inclusion_list" in request.form,
            "inclusion_list": request.form.getlist("inclusion_list[]"),
            "exclusion_list": request.form.getlist("exclusion_list[]"),
            # Discord Webhook URL
            "discord_webhook_url": request.form.get("discordWebhook")
        }
        # Save the config data
        save_config(config_data)
        return redirect(url_for('config'))

    # For GET requests, load config data and pass it to the template
    config = load_config()
    return render_template('config.html', config=config)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2000, debug=True)
