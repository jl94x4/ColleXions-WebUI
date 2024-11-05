from flask import Flask, render_template, request, redirect, url_for
import json
import os

app = Flask(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as file:
            return json.load(file)
    return {}

def save_config(data):
    with open(CONFIG_PATH, 'w') as file:
        json.dump(data, file, indent=4)

@app.route('/')
def dashboard():
    # Dummy data for dashboard; replace with real data as needed
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
            ]
        }
        save_config(config_data)
        return redirect(url_for('config'))

    config = load_config()
    return render_template('config.html', config=config)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2000, debug=True)
