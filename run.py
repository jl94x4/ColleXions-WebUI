import json
import logging
import os
import subprocess
import sys
import time

import psutil
# Add imports for Plex testing
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from plexapi.exceptions import Unauthorized, NotFound as PlexNotFound
from plexapi.server import PlexServer
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout, Timeout

# --- Configuration & Constants (Updated for Docker) ---
# Define base paths within the container
APP_DIR = '/app' # Standard practice for app code in containers
CONFIG_DIR = os.path.join(APP_DIR, 'config')
LOG_DIR = os.path.join(APP_DIR, 'logs')
DATA_DIR = os.path.join(APP_DIR, 'data')

# Update file paths
CONFIG_FILENAME = 'config.json'
SCRIPT_FILENAME = 'ColleXions.py'
LOG_FILENAME = 'collexions.log'
HISTORY_FILENAME = 'selected_collections.json'
STATUS_FILENAME = 'status.json'

# Use absolute paths within the container structure
CONFIG_PATH = os.path.join(CONFIG_DIR, CONFIG_FILENAME)
SCRIPT_PATH = os.path.join(APP_DIR, SCRIPT_FILENAME) # Assumes script is in /app
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILENAME)
SELECTED_COLLECTIONS_PATH = os.path.join(DATA_DIR, HISTORY_FILENAME)
STATUS_PATH = os.path.join(DATA_DIR, STATUS_FILENAME)

# LOG_DIR_NAME is less relevant now, using absolute LOG_DIR
# BASE_DIR is less relevant if using absolute paths

PYTHON_EXECUTABLE = sys.executable # This remains the same

# --- Flask App Setup ---
app = Flask(__name__)
# IMPORTANT: Set a strong, unique secret key in a real deployment!
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_default_very_secret_key_needs_changing')

# --- Logging ---
# Set level to DEBUG to capture detailed logs if needed, INFO for less noise
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s')

# --- Helper Functions ---

def load_config():
    """Loads configuration data from config.json."""
    if not os.path.exists(CONFIG_PATH):
        logging.warning(f"Config file not found at {CONFIG_PATH}. Returning empty default.")
        return {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            if not isinstance(config_data, dict):
                raise ValueError("Config file is not a valid JSON object.")
            logging.info("Configuration loaded successfully.")
            # --- Ensure categories key exists and is a dict ---
            if 'categories' not in config_data:
                 config_data['categories'] = {}
            elif not isinstance(config_data['categories'], dict):
                 logging.warning("Invalid 'categories' format in config, resetting to empty dict.")
                 config_data['categories'] = {}
            # --- Ensure library names exists ---
            if 'library_names' not in config_data:
                config_data['library_names'] = []
            elif not isinstance(config_data['library_names'], list):
                logging.warning("Invalid 'library_names' format in config, resetting to empty list.")
                config_data['library_names'] = []

            return config_data
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {CONFIG_PATH}: {e}")
        flash(f"Error loading config file: Invalid JSON - {e}", "error")
        return {'library_names': [], 'categories': {}} # Return default structure on error
    except Exception as e:
        logging.error(f"Error loading config file {CONFIG_PATH}: {e}")
        flash(f"Error loading config file: {e}", "error")
        return {'library_names': [], 'categories': {}} # Return default structure on error


def save_config(data):
    """Saves configuration data back to config.json."""
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logging.info("Configuration saved successfully.")
        # Flash message confirms save ONLY, not restart
        flash("Configuration saved successfully!", "success")
        return True
    except Exception as e:
        logging.error(f"Error saving config file {CONFIG_PATH}: {e}")
        flash(f"Error saving configuration: {e}", "error")
        return False

def safe_int(value, default=0):
    """Safely converts a value to int, returning default on failure."""
    try:
        # Attempt conversion to int
        return int(value)
    except (ValueError, TypeError):
        # If conversion fails, log a warning and return default
        # Removing this warning as it can be noisy for empty optional fields
        # logging.warning(f"Could not convert '{value}' to int, using default {default}")
        return default

def get_bool(value):
    """Converts form checkbox value ('on' or None) to boolean."""
    return value == 'on'

# --- Process Management ---

def is_script_running():
    """Check if the target script is running."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
             # Check if cmdline is accessible and is a list/tuple
             cmdline = proc.info.get('cmdline')
             if cmdline and isinstance(cmdline, (list, tuple)):
                 # Check if both the script path and python executable are in the command line
                 if SCRIPT_PATH in cmdline and PYTHON_EXECUTABLE in cmdline:
                     logging.debug(f"Found running script process: PID={proc.pid} CMD={' '.join(cmdline)}")
                     return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass # These are expected errors in some cases, just ignore them
    except Exception as e:
        logging.error(f"Error checking running process: {e}")
    return False


def start_script():
    """Starts the target script if not already running."""
    if is_script_running():
        logging.warning("Attempted to start script, but it is already running.")
        # Avoid flashing here, let the route handle it
        return True # Indicate it's running (or already was)
    try:
        logging.info(f"Starting script: {SCRIPT_PATH} with executable {PYTHON_EXECUTABLE}")
        # Ensure logs directory exists before starting the script
        log_dir_full_path = os.path.join(BASE_DIR, LOG_DIR_NAME)
        if not os.path.exists(log_dir_full_path):
             try:
                 os.makedirs(log_dir_full_path)
                 logging.info(f"Created log directory: {log_dir_full_path}")
             except OSError as e:
                 logging.error(f"Could not create log directory {log_dir_full_path}: {e}")
                 # Optionally, decide if this is critical and prevent startup
                 # flash(f"Error: Could not create log directory '{LOG_DIR_NAME}'. Script cannot start.", "error")
                 # return False
        subprocess.Popen([PYTHON_EXECUTABLE, SCRIPT_PATH], cwd=BASE_DIR) # Run script from base dir
        time.sleep(1) # Give a moment for the process to potentially start/fail
        if is_script_running():
            logging.info("Script started successfully.")
            return True
        else:
            logging.error("Script process did not appear after Popen call.")
            flash("Error: Script process failed to start or exited immediately. Check logs.", "error")
            return False
    except FileNotFoundError:
         logging.error(f"Cannot start script: '{PYTHON_EXECUTABLE}' or '{SCRIPT_PATH}' not found.")
         flash(f"Error: Could not find Python executable or script file '{SCRIPT_FILENAME}'.", "error")
    except Exception as e:
        logging.error(f"Error starting script: {e}", exc_info=True)
        flash(f"Error starting script: {e}", "error")
    return False

def stop_script():
    """Stops running target script process(es)."""
    killed = False
    pids_killed = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
             cmdline = proc.info.get('cmdline')
             if cmdline and isinstance(cmdline, (list, tuple)):
                 if SCRIPT_PATH in cmdline and PYTHON_EXECUTABLE in cmdline:
                    try:
                        pid_to_kill = proc.pid
                        logging.info(f"Attempting to terminate script process: PID={pid_to_kill} CMD={' '.join(cmdline)}")
                        proc.terminate() # Try graceful termination first
                        try:
                            proc.wait(timeout=3) # Wait for graceful exit
                            logging.info(f"Process PID={pid_to_kill} terminated gracefully.")
                            pids_killed.append(pid_to_kill)
                            killed = True
                        except psutil.TimeoutExpired:
                            logging.warning(f"Process PID={pid_to_kill} did not terminate gracefully, attempting kill.")
                            proc.kill()
                            proc.wait(timeout=3) # Wait for kill
                            logging.info(f"Process PID={pid_to_kill} killed forcefully.")
                            pids_killed.append(pid_to_kill)
                            killed = True
                    except psutil.NoSuchProcess:
                        logging.warning(f"Process PID={pid_to_kill} terminated before stop command completed.")
                        # Consider it killed if it's gone, even if we didn't get the kill confirmation
                        if pid_to_kill not in pids_killed:
                           pids_killed.append(f"{pid_to_kill} (already gone)")
                           killed = True
                    except Exception as e:
                        logging.error(f"Error stopping process PID={getattr(proc, 'pid', 'N/A')}: {e}")
                        flash(f"Error stopping process PID={getattr(proc, 'pid', 'N/A')}: {e}", "error")
    except (psutil.AccessDenied, psutil.ZombieProcess): pass
    except Exception as e: logging.error(f"Error iterating processes during stop: {e}")

    if not pids_killed: # Check if any PIDs were actually actioned
        logging.info("No running script process found matching criteria to stop.")
        # Don't report killed=True if nothing was found
        killed = False
    else:
        logging.info(f"Stopped script process(es): {pids_killed}")
        killed = True # Ensure killed is true if we stopped something

    # Final check
    time.sleep(0.5)
    if is_script_running():
        logging.warning("Script process still detected after stop attempt.")
        flash("Warning: Script process may still be running after stop command.", "warning")
        killed = False # Reflect that it might not be truly stopped

    return killed


# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles displaying the config form and saving it (NO restart)."""
    config = load_config() # Load current config for GET display

    if request.method == 'POST':
        logging.info("Processing configuration form submission...")
        # --- Parse Form Data ---
        new_config = {}
        try:
            # Base Config (Example - keep others as they were)
            new_config['plex_url'] = request.form.get('plex_url', '').strip()
            new_config['plex_token'] = request.form.get('plex_token', '').strip()
            new_config['collexions_label'] = request.form.get('collexions_label', 'Collexions').strip()
            new_config['pinning_interval'] = safe_int(request.form.get('pinning_interval'), 180)
            new_config['repeat_block_hours'] = safe_int(request.form.get('repeat_block_hours'), 12)
            new_config['min_items_for_pinning'] = safe_int(request.form.get('min_items_for_pinning'), 10)
            new_config['discord_webhook_url'] = request.form.get('discord_webhook_url', '').strip()


            # Libraries, Exclusions, Regex (Keep as before)
            new_config['library_names'] = sorted(list(set(lib.strip() for lib in request.form.getlist('library_names[]') if lib.strip()))) # Ensure unique and sorted
            new_config['exclusion_list'] = [ex.strip() for ex in request.form.getlist('exclusion_list[]') if ex.strip()]
            new_config['regex_exclusion_patterns'] = [rgx.strip() for rgx in request.form.getlist('regex_exclusion_patterns[]') if rgx.strip()]

            # Number of collections to pin (Keep as before)
            pin_lib_keys = request.form.getlist("pin_library_key[]")
            pin_lib_values = request.form.getlist("pin_library_value[]")
            num_pin_dict = {}
            for key, value_str in zip(pin_lib_keys, pin_lib_values):
                key = key.strip()
                if key: # Ensure key is not empty
                    num_pin_dict[key] = safe_int(value_str, 0)
            new_config['number_of_collections_to_pin'] = num_pin_dict

            # Special Collections (Keep as before)
            special_list = []
            start_dates=request.form.getlist('special_start_date[]')
            end_dates=request.form.getlist('special_end_date[]')
            coll_names_str=request.form.getlist('special_collection_names[]')
            for start, end, names_str in zip(start_dates, end_dates, coll_names_str):
                start = start.strip()
                end = end.strip()
                names = [name.strip() for name in names_str.split(',') if name.strip()]
                if start and end and names:
                    special_list.append({'start_date': start, 'end_date': end, 'collection_names': names})
            new_config['special_collections'] = special_list


            # --- NEW Category Parsing ---
            new_categories = {}
            defined_libraries = new_config.get('library_names', []) # Use the libraries defined in this submission

            for library_name in defined_libraries:
                logging.debug(f"Parsing categories for library: {library_name}")
                category_names = request.form.getlist(f'category_{library_name}_name[]')
                pin_counts = request.form.getlist(f'category_{library_name}_pin_count[]')
                logging.debug(f"  Names found: {category_names}")
                logging.debug(f"  Pin counts found: {pin_counts}")

                library_categories = []
                # Loop through the submitted categories for this library using an index
                for i in range(len(category_names)):
                    cat_name = category_names[i].strip()
                    pin_count = safe_int(pin_counts[i], 1) # Default pin count to 1 if invalid

                    # Get the list of collections for this specific category index
                    # The key format is 'category_<library_name>_<category_index>_collections[]'
                    collection_titles = request.form.getlist(f'category_{library_name}_{i}_collections[]')
                    cleaned_collection_titles = [title.strip() for title in collection_titles if title.strip()]

                    logging.debug(f"  Category Index {i}: Name='{cat_name}', PinCount={pin_count}, Collections={cleaned_collection_titles}")

                    # Only add the category if it has a name and at least one collection title
                    if cat_name and cleaned_collection_titles:
                        library_categories.append({
                            "category_name": cat_name,
                            "pin_count": pin_count,
                            "collections": cleaned_collection_titles
                        })
                    elif cat_name and not cleaned_collection_titles:
                         logging.warning(f"Category '{cat_name}' in library '{library_name}' was submitted but had no collection titles. Skipping.")
                    elif not cat_name and cleaned_collection_titles:
                         logging.warning(f"A category at index {i} in library '{library_name}' had collection titles but no name. Skipping.")


                if library_categories: # Only add the library key if it has categories
                    new_categories[library_name] = library_categories
                else:
                     logging.debug(f"  No valid categories found or added for library: {library_name}")

            new_config['categories'] = new_categories
            logging.debug(f"Final parsed categories structure: {json.dumps(new_categories, indent=2)}")
            # --- END NEW Category Parsing ---


            # --- Save ONLY ---
            if save_config(new_config):
                # Reload config after saving to reflect changes immediately if redirecting to index
                config = load_config()
                # Redirect to GET to prevent form resubmission on refresh
                return redirect(url_for('index'))
            else:
                 # If save failed, reload the original config to display again
                 config = load_config()
                 # Render the template again with the *original* config and the error flash message
                 return render_template('index.html', config=config)

        except Exception as e:
             logging.error(f"Error processing form data: {e}", exc_info=True)
             flash(f"Error processing form: {e}", "error")
             # Load the current config to redisplay the form
             config = load_config()

    # GET request or failed POST render
    # Always ensure config has default keys expected by the template
    config.setdefault('library_names', [])
    config.setdefault('categories', {})
    config.setdefault('number_of_collections_to_pin', {})
    config.setdefault('exclusion_list', [])
    config.setdefault('regex_exclusion_patterns', [])
    config.setdefault('special_collections', [])

    return render_template('index.html', config=config)

# --- Data/Log Routes --- (Unchanged)
@app.route('/get_history', methods=['GET'])
def get_history():
    if not os.path.exists(SELECTED_COLLECTIONS_PATH): return jsonify({"error": "History file not found."}), 404
    try:
        with open(SELECTED_COLLECTIONS_PATH, 'r', encoding='utf-8') as f: history_data = json.load(f)
        return jsonify(history_data)
    except Exception as e: logging.error(f"Error reading history: {e}"); return jsonify({"error": f"Error reading history: {e}"}), 500

@app.route('/get_log', methods=['GET'])
def get_log():
    log_lines_to_fetch = 200 # Increased default
    if not os.path.exists(LOG_FILE_PATH): return jsonify({"error": "Log file not found."}), 404
    try:
        lines = []
        with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f: # Added errors='ignore'
            lines = f.readlines()
        log_content = "".join(lines[-log_lines_to_fetch:])
        return jsonify({"log_content": log_content})
    except Exception as e: logging.error(f"Error reading log: {e}"); return jsonify({"error": f"Error reading log: {e}"}), 500

# --- Action Routes --- (Unchanged)
@app.route('/status', methods=['GET'])
def status():
     script_running = is_script_running(); next_run_ts = None; last_known_script_status = "Unknown"; config = load_config()
     if os.path.exists(STATUS_PATH):
         try:
             with open(STATUS_PATH, 'r', encoding='utf-8') as f: status_data = json.load(f)
             next_run_ts = status_data.get('next_run_timestamp'); last_known_script_status = status_data.get('status', 'Unknown')
             if not isinstance(next_run_ts, (int, float)): next_run_ts = None
         except Exception as e: logging.warning(f"Could not parse status file {STATUS_PATH}: {e}"); last_known_script_status = "Err reading status"
     if not script_running: next_run_ts = None; # Don't show next run if stopped
     # Keep last known status unless it was 'Running'
     if not script_running and last_known_script_status == "Running":
         last_known_script_status = "Stopped"

     return jsonify({"script_running": script_running, "config_interval_minutes": config.get("pinning_interval"), "next_run_timestamp": next_run_ts, "last_known_script_status": last_known_script_status})

@app.route('/start', methods=['POST'])
def start_route():
     if start_script():
         flash("Script start requested.", "success")
         # Give it a sec to update status maybe?
         time.sleep(1)
     else:
         # start_script() should flash specific errors
         # flash("Script failed to start.", "warning") # Avoid double flashing
         pass
     return jsonify({"script_running": is_script_running()})

@app.route('/stop', methods=['POST'])
def stop_route():
     if stop_script():
         flash("Script stop requested.", "success")
         # Give it a sec to update status
         time.sleep(1)
     else:
         flash("Script failed to stop or was not running.", "warning")
     return jsonify({"script_running": is_script_running()})

@app.route('/test_plex', methods=['POST'])
def test_plex():
    config = load_config(); url = config.get('plex_url'); token = config.get('plex_token')
    if not url or not token: return jsonify({"success": False, "message": "Plex URL or Token missing from config."}), 400
    try:
        logging.info(f"Testing Plex connection to {url}...");
        # Use a reasonable timeout
        plex = PlexServer(baseurl=url, token=token, timeout=10)
        # Perform a simple operation that requires authentication, like listing libraries
        plex.library.sections() # Fetches library sections
        server_name = plex.friendlyName
        logging.info(f"Plex connection test successful: Connected to '{server_name}'")
        return jsonify({"success": True, "message": f"Connection Successful: Found server '{server_name}'."})
    except Unauthorized:
        logging.error("Plex connection test FAIL: Unauthorized (Invalid Token).")
        return jsonify({"success": False, "message": "Connection FAILED: Unauthorized. Check your Plex Token."}), 401
    except (RequestsConnectionError, Timeout, ReadTimeout) as e:
        logging.error(f"Plex connection test FAIL: Network/Timeout error connecting to {url}: {e}")
        return jsonify({"success": False, "message": f"Connection FAILED: Could not reach Plex URL '{url}'. Check network and URL. Error: {type(e).__name__}"}), 500
    except PlexNotFound:
         logging.error(f"Plex connection test FAIL: Plex URL '{url}' might be valid, but endpoint not found (e.g., incorrect path)?")
         return jsonify({"success": False, "message": f"Connection FAILED: URL '{url}' reached, but Plex API endpoint not found. Check URL path."}), 404
    except Exception as e:
        logging.error(f"Plex connection test FAIL: Unexpected error: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Connection FAILED: An unexpected error occurred: {e}"}), 500


# --- Main Execution ---
if __name__ == '__main__':
    logging.info("Starting Flask Web UI...")
    # Ensure log directory exists
    log_dir_full_path = os.path.join(BASE_DIR, LOG_DIR_NAME)
    if not os.path.exists(log_dir_full_path):
        try:
            os.makedirs(log_dir_full_path)
            logging.info(f"Created log directory: {log_dir_full_path}")
        except OSError as e:
             logging.error(f"Failed to create log directory {log_dir_full_path}: {e}. Log saving might fail.")

    # Don't pre-create status file - let ColleXions manage it.

    # Use waitress for production instead of Flask dev server
    # app.run(host='0.0.0.0', port=5000, debug=False)
    # For development:
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False) # Disable reloader for stability with subprocess