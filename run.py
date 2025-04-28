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

PYTHON_EXECUTABLE = sys.executable # This remains the same


# --- Flask App Setup ---
app = Flask(__name__)
# IMPORTANT: Set a strong, unique secret key! Use environment variable if possible.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_default_very_secret_key_needs_changing_in_production')

# --- Logging ---
# Basic config for Flask app logging (separate from ColleXions.py logging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [Flask App] %(message)s')

# --- Helper Functions ---

def load_config():
    """Loads configuration data from config.json."""
    # Ensure config directory exists
    if not os.path.exists(CONFIG_DIR):
        logging.warning(f"Config directory {CONFIG_DIR} not found. Creating.")
        try:
             os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError as e:
             logging.error(f"Error creating config dir {CONFIG_DIR}: {e}. Loading default config.")
             return {'library_names': [], 'categories': {}} # Return default structure

    if not os.path.exists(CONFIG_PATH):
        logging.warning(f"Config file not found at {CONFIG_PATH}. Returning empty default.")
        return {'library_names': [], 'categories': {}} # Return default structure
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            if not isinstance(config_data, dict):
                raise ValueError("Config file is not a valid JSON object.")
            logging.info("Configuration loaded successfully.")
            # Ensure required keys have default types
            config_data.setdefault('library_names', [])
            config_data.setdefault('categories', {})
            # Add other setdefaults as needed for template robustness
            config_data.setdefault('number_of_collections_to_pin', {})
            config_data.setdefault('exclusion_list', [])
            config_data.setdefault('regex_exclusion_patterns', [])
            config_data.setdefault('special_collections', [])
            return config_data
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {CONFIG_PATH}: {e}")
        flash(f"Error loading config file: Invalid JSON - {e}", "error")
        return {'library_names': [], 'categories': {}}
    except Exception as e:
        logging.error(f"Error loading config file {CONFIG_PATH}: {e}")
        flash(f"Error loading config file: {e}", "error")
        return {'library_names': [], 'categories': {}}


def save_config(data):
    """Saves configuration data back to config.json."""
     # Ensure config directory exists before saving
    if not os.path.exists(CONFIG_DIR):
        logging.info(f"Config directory {CONFIG_DIR} not found. Creating before save.")
        try:
             os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError as e:
             logging.error(f"Error creating config dir {CONFIG_DIR}: {e}. Cannot save config.")
             flash(f"Error saving configuration: Could not create directory {CONFIG_DIR}", "error")
             return False
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logging.info("Configuration saved successfully.")
        flash("Configuration saved successfully!", "success")
        return True
    except Exception as e:
        logging.error(f"Error saving config file {CONFIG_PATH}: {e}")
        flash(f"Error saving configuration: {e}", "error")
        return False

def safe_int(value, default=0):
    """Safely converts a value to int, returning default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def get_bool(value):
    """Converts form checkbox value ('on' or None) to boolean."""
    return value == 'on'

# --- Process Management ---

def is_script_running():
    """Check if the target script (ColleXions.py) is running."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
             cmdline = proc.info.get('cmdline')
             # Check command line carefully - look for python executable and the *absolute* script path
             if cmdline and isinstance(cmdline, (list, tuple)) and len(cmdline) > 1:
                 # Check if python executable matches and the second argument is the SCRIPT_PATH
                 if (PYTHON_EXECUTABLE in cmdline[0] or 'python' in os.path.basename(cmdline[0]).lower()) and cmdline[1] == SCRIPT_PATH:
                     logging.debug(f"Found running script process: PID={proc.pid} CMD={' '.join(cmdline)}")
                     return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    except Exception as e:
        logging.error(f"Error checking running process: {e}")
    return False


def start_script():
    """Starts the ColleXions.py script if not already running."""
    if is_script_running():
        logging.warning("Attempted to start script, but it is already running.")
        return True # Indicate it's already running or start was successful previously

    try:
        logging.info(f"Starting script: {SCRIPT_PATH} with executable {PYTHON_EXECUTABLE}")

        # Ensure log and data directories exist using absolute paths (KEEP THIS PART)
        # This check is important before Popen attempts to run the script which might need them.
        for dir_path in [LOG_DIR, DATA_DIR, CONFIG_DIR]: # Check config dir too
            if not os.path.exists(dir_path):
                 try:
                     os.makedirs(dir_path, exist_ok=True) # Use exist_ok=True
                     logging.info(f"Created directory: {dir_path}")
                 except OSError as e:
                     logging.error(f"Could not create required directory {dir_path}: {e}")
                     flash(f"Error: Could not create directory '{dir_path}'. Script may fail.", "error")
                     # Decide whether to proceed or return False based on severity
                     return False # Fail start if essential dirs can't be made

        # Remove the OLD check using BASE_DIR and LOG_DIR_NAME as it caused NameError

        # Use Popen to run in the background. Run from APP_DIR.
        process = subprocess.Popen([PYTHON_EXECUTABLE, SCRIPT_PATH], cwd=APP_DIR)
        logging.info(f"Script process initiated with PID (may change if daemonized): {process.pid}")
        time.sleep(1) # Brief pause to allow process to potentially start/fail early

        if is_script_running():
            logging.info("Script confirmed running after Popen.")
            return True
        else:
            logging.error("Script process did not appear or exited immediately after Popen call.")
            # Try to get output if it failed quickly (Best effort)
            try:
                stdout, stderr = process.communicate(timeout=1)
                if stdout: logging.error(f"Script stdout: {stdout.decode(errors='ignore')}")
                if stderr: logging.error(f"Script stderr: {stderr.decode(errors='ignore')}")
            except subprocess.TimeoutExpired:
                 logging.error("Could not get script output (timed out).")
            except Exception as comm_err:
                 logging.error(f"Error getting script output: {comm_err}")

            flash("Error: Script process failed to start or exited immediately. Check Flask logs.", "error")
            return False # Return False as script failed to start properly

    except FileNotFoundError:
         # This means PYTHON_EXECUTABLE or SCRIPT_PATH was not found by Popen
         logging.error(f"Cannot start script: FileNotFoundError for '{PYTHON_EXECUTABLE}' or '{SCRIPT_PATH}'.")
         flash(f"Error: Could not find Python executable or script file needed to start.", "error")
         return False
    except Exception as e:
        # Catch other potential errors during Popen or directory checks
        logging.error(f"Error starting script: {e}", exc_info=True)
        flash(f"Error starting script: {e}", "error")
        return False


def stop_script():
    """Stops running ColleXions.py script process(es)."""
    killed = False
    pids_killed = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
             cmdline = proc.info.get('cmdline')
             if cmdline and isinstance(cmdline, (list, tuple)) and len(cmdline) > 1:
                 if (PYTHON_EXECUTABLE in cmdline[0] or 'python' in os.path.basename(cmdline[0]).lower()) and cmdline[1] == SCRIPT_PATH:
                    pid_to_kill = proc.pid
                    try:
                        logging.info(f"Attempting to terminate script process: PID={pid_to_kill} CMD={' '.join(cmdline)}")
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                            logging.info(f"Process PID={pid_to_kill} terminated gracefully.")
                            pids_killed.append(str(pid_to_kill))
                            killed = True
                        except psutil.TimeoutExpired:
                            logging.warning(f"Process PID={pid_to_kill} did not terminate gracefully, killing.")
                            proc.kill()
                            proc.wait(timeout=3)
                            logging.info(f"Process PID={pid_to_kill} killed forcefully.")
                            pids_killed.append(f"{pid_to_kill} (killed)")
                            killed = True
                    except psutil.NoSuchProcess:
                        logging.warning(f"Process PID={pid_to_kill} terminated before stop command completed.")
                        if str(pid_to_kill) not in pids_killed and f"{pid_to_kill} (killed)" not in pids_killed:
                            pids_killed.append(f"{pid_to_kill} (already gone)")
                        killed = True # Still count as success if it's gone
                    except Exception as e:
                        logging.error(f"Error stopping process PID={pid_to_kill}: {e}")
                        flash(f"Error stopping process PID={pid_to_kill}: {e}", "error")
    except (psutil.AccessDenied, psutil.ZombieProcess): pass
    except Exception as e: logging.error(f"Error iterating processes during stop: {e}")

    if not pids_killed:
        logging.info("No running script process found matching criteria to stop.")
        killed = False
    else:
        logging.info(f"Stopped script process(es): {', '.join(pids_killed)}")
        killed = True

    # Short delay and final check
    time.sleep(0.5)
    if is_script_running():
        logging.warning("Script process still detected after stop attempt.")
        flash("Warning: Script process may still be running after stop command.", "warning")
        killed = False

    return killed


# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles displaying the config form and saving it."""
    if request.method == 'POST':
        logging.info("Processing configuration form submission...")
        new_config = {}
        try:
            # Base Config
            new_config['plex_url'] = request.form.get('plex_url', '').strip()
            new_config['plex_token'] = request.form.get('plex_token', '').strip()
            new_config['collexions_label'] = request.form.get('collexions_label', 'Collexions').strip()
            new_config['pinning_interval'] = safe_int(request.form.get('pinning_interval'), 180)
            new_config['repeat_block_hours'] = safe_int(request.form.get('repeat_block_hours'), 12)
            new_config['min_items_for_pinning'] = safe_int(request.form.get('min_items_for_pinning'), 10)
            new_config['discord_webhook_url'] = request.form.get('discord_webhook_url', '').strip()

            # Libraries, Exclusions, Regex
            new_config['library_names'] = sorted(list(set(lib.strip() for lib in request.form.getlist('library_names[]') if lib.strip())))
            new_config['exclusion_list'] = [ex.strip() for ex in request.form.getlist('exclusion_list[]') if ex.strip()]
            new_config['regex_exclusion_patterns'] = [rgx.strip() for rgx in request.form.getlist('regex_exclusion_patterns[]') if rgx.strip()]

            # Number of collections to pin
            pin_lib_keys = request.form.getlist("pin_library_key[]")
            pin_lib_values = request.form.getlist("pin_library_value[]")
            num_pin_dict = {}
            for key, value_str in zip(pin_lib_keys, pin_lib_values):
                key = key.strip()
                if key:
                    num_pin_dict[key] = safe_int(value_str, 0)
            new_config['number_of_collections_to_pin'] = num_pin_dict

            # Special Collections Parsing (Revised)
            special_list = []
            start_dates = request.form.getlist('special_start_date[]')
            end_dates = request.form.getlist('special_end_date[]')
            coll_names_str_list = request.form.getlist('special_collection_names[]')
            logging.debug(f"--- Parsing Special Collections ---")
            logging.debug(f"Received special_start_date[] ({len(start_dates)} items): {start_dates}")
            logging.debug(f"Received special_end_date[] ({len(end_dates)} items): {end_dates}")
            logging.debug(f"Received special_collection_names[] ({len(coll_names_str_list)} items): {coll_names_str_list}")
            num_special_entries = len(start_dates)
            logging.debug(f"Attempting to process {num_special_entries} special entries.")
            for i in range(num_special_entries):
                start = start_dates[i].strip() if i < len(start_dates) else ''
                end = end_dates[i].strip() if i < len(end_dates) else ''
                names_str = coll_names_str_list[i] if i < len(coll_names_str_list) else ''
                names = [name.strip() for name in names_str.split(',') if name.strip()]
                logging.debug(f"  Processing Special Entry Index {i}: Start='{start}', End='{end}', Names={names} (Raw='{names_str}')")
                if start and end and names:
                    entry_data = {'start_date': start, 'end_date': end, 'collection_names': names}
                    special_list.append(entry_data)
                    logging.debug(f"    -> Added Valid Special Entry: {entry_data}")
                else:
                    logging.warning(f"    -> Skipped Special Entry Index {i} due to missing data.")
            new_config['special_collections'] = special_list
            logging.debug(f"--- Finished Parsing Special Collections ---")
            logging.debug(f"Final constructed special_collections list ({len(special_list)} items): {json.dumps(special_list, indent=2)}")


            # Category Parsing
            new_categories = {}
            defined_libraries = new_config.get('library_names', [])
            logging.debug(f"--- Parsing Categories for Libraries: {defined_libraries} ---")
            for library_name in defined_libraries:
                logging.debug(f"Parsing categories for library: {library_name}")
                category_names = request.form.getlist(f'category_{library_name}_name[]')
                pin_counts = request.form.getlist(f'category_{library_name}_pin_count[]')
                logging.debug(f"  Names found ({len(category_names)}): {category_names}")
                logging.debug(f"  Pin counts found ({len(pin_counts)}): {pin_counts}")
                library_categories = []
                for i in range(len(category_names)): # Iterate based on names found
                    cat_name = category_names[i].strip()
                    # Ensure pin_counts list is long enough before accessing index i
                    pin_count = safe_int(pin_counts[i], 1) if i < len(pin_counts) else 1
                    collection_titles = request.form.getlist(f'category_{library_name}_{i}_collections[]')
                    cleaned_collection_titles = [title.strip() for title in collection_titles if title.strip()]
                    logging.debug(f"  Category Index {i}: Name='{cat_name}', PinCount={pin_count}, Collections={cleaned_collection_titles}")
                    if cat_name and cleaned_collection_titles:
                        library_categories.append({
                            "category_name": cat_name,
                            "pin_count": pin_count,
                            "collections": cleaned_collection_titles
                        })
                    elif cat_name and not cleaned_collection_titles:
                         logging.warning(f"Category '{cat_name}' in library '{library_name}' submitted with no collections. Skipping.")
                    elif not cat_name and cleaned_collection_titles:
                         logging.warning(f"Category index {i} in library '{library_name}' submitted with collections but no name. Skipping.")
                if library_categories:
                    new_categories[library_name] = library_categories
                else:
                     logging.debug(f"  No valid categories added for library: {library_name}")
            new_config['categories'] = new_categories
            logging.debug(f"--- Finished Parsing Categories ---")
            logging.debug(f"Final parsed categories structure: {json.dumps(new_categories, indent=2)}")

            # --- Save Config ---
            if save_config(new_config):
                return redirect(url_for('index')) # Redirect on success
            else:
                 # If save failed, re-render with current data and error flash
                 config = new_config # Display the data user tried to save
                 # Ensure default keys exist for template rendering
                 config.setdefault('library_names', [])
                 config.setdefault('categories', {})
                 config.setdefault('number_of_collections_to_pin', {})
                 config.setdefault('exclusion_list', [])
                 config.setdefault('regex_exclusion_patterns', [])
                 config.setdefault('special_collections', [])
                 return render_template('index.html', config=config) # Render again

        except Exception as e:
             logging.error(f"Error processing form data: {e}", exc_info=True)
             flash(f"Error processing form: {e}", "error")
             config = load_config() # Load existing config on general error

    # GET request or failed POST render
    config = load_config() # Load fresh config for GET request
    return render_template('index.html', config=config)


# --- Data/Log Routes ---
@app.route('/get_history', methods=['GET'])
def get_history():
     # Check data dir first
    if not os.path.exists(DATA_DIR):
        logging.error(f"Data directory not found at {DATA_DIR} for get_history.")
        return jsonify({"error": f"Data directory not found."}), 404 # Return 404
    if not os.path.exists(SELECTED_COLLECTIONS_PATH):
        logging.info(f"History file not found at {SELECTED_COLLECTIONS_PATH}. Returning empty history.")
        return jsonify({}) # Return empty JSON object if file doesn't exist
    try:
        with open(SELECTED_COLLECTIONS_PATH, 'r', encoding='utf-8') as f: history_data = json.load(f)
        return jsonify(history_data)
    except Exception as e:
        logging.error(f"Error reading history file {SELECTED_COLLECTIONS_PATH}: {e}", exc_info=True)
        return jsonify({"error": f"Error reading history file: {e}"}), 500

@app.route('/get_log', methods=['GET'])
def get_log():
    log_lines_to_fetch = 250
    # Check log dir first
    if not os.path.exists(LOG_DIR):
         logging.error(f"Log directory not found at {LOG_DIR} for get_log.")
         return jsonify({"log_content": f"(Log directory not found)"}) # Info, not error
    if not os.path.exists(LOG_FILE_PATH):
        logging.info(f"Log file not found at {LOG_FILE_PATH}. Returning message.")
        return jsonify({"log_content": "(Log file not found)"})
    try:
        lines = []
        # Ensure file can be opened
        if os.path.isfile(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            log_content = "".join(lines[-log_lines_to_fetch:])
            return jsonify({"log_content": log_content})
        else:
             logging.error(f"Log path exists but is not a file: {LOG_FILE_PATH}")
             return jsonify({"error": "Log path is not a file"}), 500
    except Exception as e:
        logging.error(f"Error reading log file {LOG_FILE_PATH}: {e}", exc_info=True)
        return jsonify({"error": f"Error reading log file: {e}"}), 500

# --- Action Routes ---
@app.route('/status', methods=['GET'])
def status():
     script_running = is_script_running()
     next_run_ts = None
     last_known_script_status = "Not Found"
     config = load_config() # Load current config to get interval

     if os.path.exists(STATUS_PATH):
         try:
             with open(STATUS_PATH, 'r', encoding='utf-8') as f: status_data = json.load(f)
             next_run_ts = status_data.get('next_run_timestamp')
             last_known_script_status = status_data.get('status', 'Unknown from file')
             if not isinstance(next_run_ts, (int, float)): next_run_ts = None
         except Exception as e:
             logging.warning(f"Could not read or parse status file {STATUS_PATH}: {e}")
             last_known_script_status = "Error reading status file"
     elif not script_running:
          last_known_script_status = "Stopped (No status file)"


     if not script_running:
         next_run_ts = None
         # Only override status if it wasn't already an error/crash state
         if last_known_script_status not in ["Error reading status file"] and \
            "crashed" not in last_known_script_status.lower() and \
            "error" not in last_known_script_status.lower():
              last_known_script_status = "Stopped"
         elif last_known_script_status in ["Running", "Sleeping", "Initializing", "Starting"]:
             last_known_script_status = "Stopped (Unexpectedly?)"

     return jsonify({
         "script_running": script_running,
         "config_interval_minutes": config.get("pinning_interval"),
         "next_run_timestamp": next_run_ts,
         "last_known_script_status": last_known_script_status
     })

@app.route('/start', methods=['POST'])
def start_route():
     if start_script():
         flash("Script start requested.", "success")
         time.sleep(1)
     # else: # start_script() flashes specific errors
     #    pass
     return jsonify({"script_running": is_script_running()})

@app.route('/stop', methods=['POST'])
def stop_route():
     if stop_script():
         flash("Script stop requested.", "success")
         time.sleep(1)
     else:
         flash("Script failed to stop or was not running.", "warning")
     return jsonify({"script_running": is_script_running()})

@app.route('/test_plex', methods=['POST'])
def test_plex():
    config = load_config()
    url = config.get('plex_url')
    token = config.get('plex_token')
    if not url or not token:
        return jsonify({"success": False, "message": "Plex URL or Token missing from config."}), 400
    try:
        logging.info(f"Testing Plex connection to {url}...")
        plex = PlexServer(baseurl=url, token=token, timeout=15)
        plex.library.sections()
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
         logging.error(f"Plex connection test FAIL: Plex URL '{url}' endpoint not found.")
         return jsonify({"success": False, "message": f"Connection FAILED: URL '{url}' reached, but Plex API endpoint not found. Check URL path."}), 404
    except Exception as e:
        logging.error(f"Plex connection test FAIL: Unexpected error: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Connection FAILED: An unexpected error occurred: {e}"}), 500


# --- Main Execution ---
# This block is primarily for direct development execution (`python run.py`)
# For production using Waitress, this block won't be executed directly by Waitress.
if __name__ == '__main__':
    logging.info("Starting Flask Web UI in DEVELOPMENT mode...")

    # Ensure essential directories exist on startup for development mode
    for dir_path in [CONFIG_DIR, LOG_DIR, DATA_DIR]:
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                logging.info(f"Created directory: {dir_path}")
            except OSError as e:
                 logging.error(f"Failed to create directory {dir_path}: {e}. App may encounter issues.")

    # Run Flask development server (use waitress-serve for production)
    # Set debug=False generally, unless actively debugging Flask itself.
    # use_reloader=False is important if running background processes like ColleXions.py
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)