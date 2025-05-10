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
    if not os.path.exists(CONFIG_DIR):
        logging.warning(f"Config directory {CONFIG_DIR} not found. Creating.")
        try:
             os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError as e:
             logging.error(f"Error creating config dir {CONFIG_DIR}: {e}. Loading default config.")
             return {'library_names': [], 'categories': {}, 'use_random_category_mode': False, 'random_category_skip_percent': 70}

    if not os.path.exists(CONFIG_PATH):
        logging.warning(f"Config file not found at {CONFIG_PATH}. Returning empty default.")
        return {'library_names': [], 'categories': {}, 'use_random_category_mode': False, 'random_category_skip_percent': 70}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            if not isinstance(config_data, dict):
                raise ValueError("Config file is not a valid JSON object.")
            logging.info("Configuration loaded successfully.")
            config_data.setdefault('use_random_category_mode', False)
            config_data.setdefault('random_category_skip_percent', 70)
            config_data.setdefault('library_names', [])
            config_data.setdefault('categories', {})
            config_data.setdefault('number_of_collections_to_pin', {})
            config_data.setdefault('exclusion_list', [])
            config_data.setdefault('regex_exclusion_patterns', [])
            config_data.setdefault('special_collections', [])
            skip_perc = config_data.get('random_category_skip_percent', 70)
            if not (isinstance(skip_perc, int) and 0 <= skip_perc <= 100):
                logging.warning(f"Configured 'random_category_skip_percent' ({skip_perc}) out of range (0-100). Resetting to default 70.")
                config_data['random_category_skip_percent'] = 70
            return config_data
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {CONFIG_PATH}: {e}")
        flash(f"Error loading config file: Invalid JSON - {e}", "error")
        return {'library_names': [], 'categories': {}, 'use_random_category_mode': False, 'random_category_skip_percent': 70}
    except Exception as e:
        logging.error(f"Error loading config file {CONFIG_PATH}: {e}")
        flash(f"Error loading config file: {e}", "error")
        return {'library_names': [], 'categories': {}, 'use_random_category_mode': False, 'random_category_skip_percent': 70}


def save_config(data):
    """Saves configuration data back to config.json."""
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
        return int(float(str(value)))
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
             if cmdline and isinstance(cmdline, (list, tuple)) and len(cmdline) > 1:
                 if (sys.executable in cmdline[0] or os.path.basename(sys.executable) in os.path.basename(cmdline[0])) and \
                    cmdline[1] == SCRIPT_PATH:
                     logging.debug(f"Found running script process: PID={proc.pid} CMD={' '.join(cmdline)}")
                     return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    except Exception as e:
        logging.error(f"Error checking running process: {e}", exc_info=True)
    return False

# --- MODIFIED: start_script function ---
def start_script(start_in_dry_run_mode=False):
    """Starts the ColleXions.py script, optionally in dry-run mode."""
    if is_script_running():
        logging.warning("Attempted start script, but already running.")
        # flash("Script is already running.", "info") # Already handled by button state
        return True

    try:
        command = [PYTHON_EXECUTABLE, SCRIPT_PATH]
        if start_in_dry_run_mode:
            command.append('--dry-run') # Add the dry-run argument to ColleXions.py
            logging.info(f"Attempting to start script IN DRY-RUN MODE: {' '.join(command)}")
        else:
            logging.info(f"Attempting to start script: {' '.join(command)}")

        for dir_path in [LOG_DIR, DATA_DIR, CONFIG_DIR]:
            if not os.path.exists(dir_path):
                 try:
                     os.makedirs(dir_path, exist_ok=True)
                     logging.info(f"Created directory: {dir_path}")
                 except OSError as e:
                     logging.error(f"Could not create required directory {dir_path}: {e}")
                     flash(f"Error: Could not create directory '{os.path.basename(dir_path)}'. Script may fail.", "error")
                     return False

        process = subprocess.Popen(command, cwd=APP_DIR) # Pass the modified command
        logging.info(f"Script process initiated (PID: {process.pid}) with command: {' '.join(command)}")
        time.sleep(1.5)

        if is_script_running():
            logging.info("Script confirmed running after Popen.")
            return True
        else:
            logging.error("Script process did not appear or exited immediately after Popen call.")
            try:
                exit_code = process.poll()
                if exit_code is not None:
                    logging.error(f"Script process terminated with exit code: {exit_code}")
            except Exception as comm_err:
                 logging.error(f"Error checking script process status after start: {comm_err}")
            flash("Error: Script process failed to start or exited immediately. Check Flask and script logs.", "error")
            return False
    except FileNotFoundError:
         logging.error(f"Cannot start script: FileNotFoundError for '{PYTHON_EXECUTABLE}' or '{SCRIPT_PATH}'.")
         flash(f"Error: Could not find Python executable or script file needed to start.", "error")
         return False
    except Exception as e:
        logging.error(f"Error starting script: {e}", exc_info=True)
        flash(f"Error starting script: {e}", "error")
        return False
# --- END MODIFIED: start_script function ---

def stop_script():
    """Stops running ColleXions.py script process(es)."""
    killed_successfully = False # More descriptive variable name
    pids_killed_info = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
             cmdline = proc.info.get('cmdline')
             if cmdline and isinstance(cmdline, (list, tuple)) and len(cmdline) > 1:
                  if (sys.executable in cmdline[0] or os.path.basename(sys.executable) in os.path.basename(cmdline[0])) and \
                     cmdline[1] == SCRIPT_PATH:
                    pid_to_kill = proc.pid
                    try:
                        logging.info(f"Attempting to terminate script process: PID={pid_to_kill} CMD={' '.join(cmdline)}")
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                            logging.info(f"Process PID={pid_to_kill} terminated gracefully.")
                            pids_killed_info.append(str(pid_to_kill))
                            killed_successfully = True
                        except psutil.TimeoutExpired:
                            logging.warning(f"Process PID={pid_to_kill} did not terminate gracefully, killing.")
                            proc.kill()
                            proc.wait(timeout=3) # Give it time to die
                            logging.info(f"Process PID={pid_to_kill} killed forcefully.")
                            pids_killed_info.append(f"{pid_to_kill} (killed)")
                            killed_successfully = True # Still counts as success
                    except psutil.NoSuchProcess:
                        logging.warning(f"Process PID={pid_to_kill} no longer exists (already terminated).")
                        if str(pid_to_kill) not in pids_killed_info and f"{pid_to_kill} (killed)" not in pids_killed_info:
                             pids_killed_info.append(f"{pid_to_kill} (already gone)")
                        killed_successfully = True # If it's gone, it's a success
                    except Exception as e:
                        logging.error(f"Error stopping process PID={pid_to_kill}: {e}")
                        flash(f"Error stopping process PID={pid_to_kill}: {e}", "error")
                        # killed_successfully remains false if an error occurred for a specific proc
    except (psutil.AccessDenied, psutil.ZombieProcess): pass
    except Exception as e: logging.error(f"Error iterating processes during stop: {e}")

    if not pids_killed_info:
        logging.info("No running script process found matching criteria to stop.")
        # killed_successfully remains false
    else:
        logging.info(f"Script stop actions completed for PIDs: {', '.join(pids_killed_info)}")
        # If we got here and pids_killed_info is not empty, assume general success
        # unless a specific error was flashed for a PID.
        killed_successfully = True


    time.sleep(0.5) # Allow OS to update process states
    if is_script_running():
        logging.warning("Script process still detected after stop attempt.")
        flash("Warning: Script process may still be running after stop command.", "warning")
        return False # Explicitly return False if still running
    elif killed_successfully: # Only return true if we attempted kills AND it's not running
        return True
    else: # Not running, and no kill attempts were made (or they all failed silently and it stopped some other way)
        return not is_script_running() # Final check


# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles displaying the config form and saving it."""
    if request.method == 'POST':
        logging.info("Processing config form POST request...")
        new_config = {}
        try:
            new_config['plex_url'] = request.form.get('plex_url', '').strip()
            new_config['plex_token'] = request.form.get('plex_token', '').strip()
            new_config['collexions_label'] = request.form.get('collexions_label', 'Collexions').strip()
            new_config['pinning_interval'] = safe_int(request.form.get('pinning_interval'), 180)
            new_config['repeat_block_hours'] = safe_int(request.form.get('repeat_block_hours'), 12)
            new_config['min_items_for_pinning'] = safe_int(request.form.get('min_items_for_pinning'), 10)
            new_config['discord_webhook_url'] = request.form.get('discord_webhook_url', '').strip()
            new_config['use_random_category_mode'] = get_bool(request.form.get('use_random_category_mode'))
            skip_perc_raw = request.form.get('random_category_skip_percent')
            skip_perc = safe_int(skip_perc_raw, 70)
            new_config['random_category_skip_percent'] = max(0, min(100, skip_perc))
            if str(skip_perc_raw).strip() and skip_perc != safe_int(skip_perc_raw, -1):
                 logging.warning(f"Invalid value '{skip_perc_raw}' for random_category_skip_percent. Using {new_config['random_category_skip_percent']}%.")

            new_config['library_names'] = sorted(list(set(lib.strip() for lib in request.form.getlist('library_names[]') if lib.strip())))
            new_config['exclusion_list'] = [ex.strip() for ex in request.form.getlist('exclusion_list[]') if ex.strip()]
            new_config['regex_exclusion_patterns'] = [rgx.strip() for rgx in request.form.getlist('regex_exclusion_patterns[]') if rgx.strip()]

            pin_lib_keys = request.form.getlist("pin_library_key[]"); pin_lib_values = request.form.getlist("pin_library_value[]")
            num_pin_dict = {k.strip(): safe_int(v, 0) for k, v in zip(pin_lib_keys, pin_lib_values) if k.strip()}
            new_config['number_of_collections_to_pin'] = num_pin_dict

            special_list = []; start_dates = request.form.getlist('special_start_date[]'); end_dates = request.form.getlist('special_end_date[]'); names_list = request.form.getlist('special_collection_names[]')
            num_special_entries = len(start_dates)
            logging.debug(f"Parsing {num_special_entries} special entries...")
            for i in range(num_special_entries):
                s = start_dates[i].strip() if i < len(start_dates) else ''; e = end_dates[i].strip() if i < len(end_dates) else ''; ns = names_list[i] if i < len(names_list) else ''
                names = [n.strip() for n in ns.split(',') if n.strip()]
                if s and e and names: special_list.append({'start_date': s, 'end_date': e, 'collection_names': names})
                else: logging.warning(f"Skipped invalid Special Entry Index {i} (Start:'{s}', End:'{e}', Names:'{ns}').")
            new_config['special_collections'] = special_list
            logging.debug(f"Parsed {len(special_list)} valid special entries.")

            new_categories = {}; defined_libraries = new_config.get('library_names', [])
            logging.debug(f"Parsing categories for libraries: {defined_libraries}")
            for lib_name in defined_libraries:
                cat_names = request.form.getlist(f'category_{lib_name}_name[]'); counts = request.form.getlist(f'category_{lib_name}_pin_count[]')
                logging.debug(f" Found {len(cat_names)} category names for '{lib_name}'.")
                lib_cats = []
                for i in range(len(cat_names)):
                    name = cat_names[i].strip(); count = safe_int(counts[i], 1) if i < len(counts) else 1
                    colls = request.form.getlist(f'category_{lib_name}_{i}_collections[]') # Corrected to use index i
                    colls_clean = [c.strip() for c in colls if c.strip()]
                    if name and colls_clean: lib_cats.append({"category_name": name, "pin_count": count, "collections": colls_clean})
                    else: logging.warning(f"Skipped invalid Category Index {i} for library '{lib_name}' (Name:'{name}', Collections:{colls_clean}).")
                if lib_cats: new_categories[lib_name] = lib_cats
            new_config['categories'] = new_categories
            logging.debug(f"Parsed categories structure: {json.dumps(new_categories, indent=2)}")

            if save_config(new_config):
                return redirect(url_for('index'))
            else:
                 config = new_config
                 config.setdefault('library_names', [])
                 config.setdefault('categories', {})
                 config.setdefault('number_of_collections_to_pin', {})
                 config.setdefault('exclusion_list', [])
                 config.setdefault('regex_exclusion_patterns', [])
                 config.setdefault('special_collections', [])
                 config.setdefault('use_random_category_mode', False)
                 config.setdefault('random_category_skip_percent', 70)
                 return render_template('index.html', config=config)
        except Exception as e:
             logging.error(f"Unhandled error during POST processing: {e}", exc_info=True)
             flash(f"Unexpected error processing form: {e}", "error")
             config = load_config()
    else: # GET request
        config = load_config()

    config.setdefault('library_names', [])
    config.setdefault('categories', {})
    config.setdefault('number_of_collections_to_pin', {})
    config.setdefault('exclusion_list', [])
    config.setdefault('regex_exclusion_patterns', [])
    config.setdefault('special_collections', [])
    config.setdefault('use_random_category_mode', False)
    config.setdefault('random_category_skip_percent', 70)
    return render_template('index.html', config=config)


@app.route('/get_history', methods=['GET'])
def get_history():
    # ... (Your existing get_history route - no changes needed)
    if not os.path.exists(DATA_DIR):
        logging.error(f"Data directory not found at {DATA_DIR} for get_history.")
        return jsonify({"error": f"Data directory not found."}), 404
    if not os.path.exists(SELECTED_COLLECTIONS_PATH):
        logging.info(f"History file not found at {SELECTED_COLLECTIONS_PATH}. Returning empty.")
        return jsonify({})
    try:
        with open(SELECTED_COLLECTIONS_PATH, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
            if not isinstance(history_data, dict):
                 logging.warning(f"History file {SELECTED_COLLECTIONS_PATH} is not a valid JSON object. Returning empty.")
                 return jsonify({})
            return jsonify(history_data)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding history file {SELECTED_COLLECTIONS_PATH}: {e}")
        return jsonify({"error": f"Error decoding history file: {e}"}), 500
    except Exception as e:
        logging.error(f"Error reading history file {SELECTED_COLLECTIONS_PATH}: {e}", exc_info=True)
        return jsonify({"error": f"Error reading history file: {e}"}), 500

@app.route('/get_log', methods=['GET'])
def get_log():
    # ... (Your existing get_log route - no changes needed)
    log_lines_to_fetch = 250
    if not os.path.exists(LOG_DIR):
         logging.error(f"Log directory not found at {LOG_DIR} for get_log.")
         return jsonify({"log_content": f"(Log directory {LOG_DIR} not found)"})
    if not os.path.exists(LOG_FILE_PATH):
        logging.info(f"Log file not found at {LOG_FILE_PATH}. Returning message.")
        return jsonify({"log_content": "(Log file not found)"})
    try:
        if os.path.isfile(LOG_FILE_PATH):
            lines = []
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

@app.route('/status', methods=['GET'])
def status():
    # ... (Your existing status route - ColleXions.py will now include [DRY-RUN] in its status message)
     script_running = is_script_running()
     next_run_ts = None
     last_known_script_status = "Not Found"
     config = load_config()

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
         if last_known_script_status not in ["Error reading status file"] and \
            "crashed" not in last_known_script_status.lower() and \
            "error" not in last_known_script_status.lower() and \
            "fatal" not in last_known_script_status.lower():
              last_known_script_status = "Stopped"
         elif last_known_script_status in ["Running", "Sleeping", "Initializing", "Starting"] or "[DRY-RUN] Running" in last_known_script_status or "[DRY-RUN] Sleeping" in last_known_script_status or "[DRY-RUN] Initializing" in last_known_script_status or "[DRY-RUN] Starting" in last_known_script_status or "Processing" in last_known_script_status :
             last_known_script_status = "Stopped (Unexpectedly?)"

     return jsonify({
         "script_running": script_running,
         "config_interval_minutes": config.get("pinning_interval"),
         "next_run_timestamp": next_run_ts,
         "last_known_script_status": last_known_script_status
     })

# --- MODIFIED: /start route ---
@app.route('/start', methods=['POST'])
def start_route():
    dry_run_str = request.args.get('dry_run', 'false').lower() # Get from query parameter
    is_dry_run_active = dry_run_str == 'true'

    if is_dry_run_active:
        flash("Script start requested IN DRY-RUN MODE.", "warning")
    else:
        flash("Script start requested.", "success")

    if start_script(start_in_dry_run_mode=is_dry_run_active): # Pass the flag
        time.sleep(1.5) # Give script time to update its status
    # else: start_script() already handles flashing error messages
    return jsonify({"script_running": is_script_running()})
# --- END MODIFIED: /start route ---

@app.route('/stop', methods=['POST'])
def stop_route():
    if stop_script():
        flash("Script stop requested successfully.", "success")
        time.sleep(1)
    else:
        if not is_script_running():
            flash("Script was already stopped.", "info")
        else:
            flash("Script failed to stop (it might still be running or was not running initially).", "warning")
    return jsonify({"script_running": is_script_running()})


@app.route('/test_plex', methods=['POST'])
def test_plex():
    # ... (Your existing test_plex route - no changes needed)
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
if __name__ == '__main__':
    logging.info("Starting Flask Web UI in DEVELOPMENT mode...")
    for dir_path in [CONFIG_DIR, LOG_DIR, DATA_DIR]:
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                logging.info(f"Created directory: {dir_path}")
            except OSError as e:
                 logging.error(f"Failed to create directory {dir_path}: {e}. App may encounter issues.")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)