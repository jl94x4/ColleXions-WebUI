import json
import os

# Define the path to the shared configuration file and logs
CONFIG_PATH = '/app/config.json'
LOG_PATH = '/logs/collexions.log'

def load_config():
    """Load ColleXions configuration from the shared volume."""
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def update_config(new_config):
    """Update ColleXions configuration file."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(new_config, f, indent=4)

def get_logs():
    """Retrieve the latest logs from ColleXions."""
    with open(LOG_PATH, 'r') as f:
        return f.read()
