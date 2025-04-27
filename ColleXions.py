# --- Imports ---
import random
import logging
import time
import json
import os
import sys
import re
import requests
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest, Unauthorized
from datetime import datetime, timedelta

# --- Configuration & Constants (Updated for Docker) ---
# Define base paths within the container
APP_DIR = '/app'
CONFIG_DIR = os.path.join(APP_DIR, 'config')
LOG_DIR = os.path.join(APP_DIR, 'logs')
DATA_DIR = os.path.join(APP_DIR, 'data')

# Update file paths using absolute container paths
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
LOG_FILE = os.path.join(LOG_DIR, 'collexions.log')
SELECTED_COLLECTIONS_FILE = os.path.join(DATA_DIR, 'selected_collections.json')
STATUS_FILE = os.path.join(DATA_DIR, 'status.json')

# --- Setup Logging ---
# Ensure log directory exists
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
    except OSError as e:
        sys.stderr.write(f"CRITICAL: Error creating log directory '{LOG_DIR}': {e}. Exiting.\n")
        sys.exit(1) # Exit if log dir cannot be created

log_handlers = [logging.StreamHandler(sys.stdout)]
# Setup file handler only if LOG_DIR exists
try:
    log_handlers.append(logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')) # Use append mode 'a'
except Exception as e:
    sys.stderr.write(f"Warning: Error setting up file log handler for '{LOG_FILE}': {e}\n")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=log_handlers
)
logging.getLogger("requests").setLevel(logging.WARNING) # Quieten requests library
logging.getLogger("urllib3").setLevel(logging.WARNING) # Quieten urllib3 library

# --- Status Update Function ---
def update_status(status_message="Running", next_run_timestamp=None):
    """Updates the status JSON file."""
    status_data = {"status": status_message, "last_update": datetime.now().isoformat()}
    if next_run_timestamp:
        status_data["next_run_timestamp"] = next_run_timestamp
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error writing status file '{STATUS_FILE}': {e}")


# --- Functions ---

def load_selected_collections():
    """Loads the history of previously pinned collections."""
    if os.path.exists(SELECTED_COLLECTIONS_FILE):
        try:
            with open(SELECTED_COLLECTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict): return data
                else: logging.error(f"Invalid format in {SELECTED_COLLECTIONS_FILE}. Resetting."); return {}
        except json.JSONDecodeError: logging.error(f"Error decoding {SELECTED_COLLECTIONS_FILE}. Resetting."); return {}
        except Exception as e: logging.error(f"Error loading {SELECTED_COLLECTIONS_FILE}: {e}. Resetting."); return {}
    return {}

def save_selected_collections(selected_collections):
    """Saves the updated history of pinned collections."""
    try:
        with open(SELECTED_COLLECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(selected_collections, f, ensure_ascii=False, indent=4)
    except Exception as e: logging.error(f"Error saving {SELECTED_COLLECTIONS_FILE}: {e}")

def get_recently_pinned_collections(selected_collections, config):
    """Gets titles of non-special collections pinned within the repeat_block_hours window."""
    repeat_block_hours = config.get('repeat_block_hours', 12)
    if not isinstance(repeat_block_hours, (int, float)) or repeat_block_hours <= 0:
        logging.warning(f"Invalid 'repeat_block_hours' ({repeat_block_hours}), defaulting 12."); repeat_block_hours = 12
    cutoff_time = datetime.now() - timedelta(hours=repeat_block_hours)
    recent_titles = set()
    timestamps_to_keep = {}
    logging.info(f"Checking history since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} for recently pinned non-special items (Repeat block: {repeat_block_hours} hours)")

    # Create a copy to iterate over while potentially modifying the original
    history_items = list(selected_collections.items())

    for timestamp_str, titles in history_items:
        if not isinstance(titles, list):
             logging.warning(f"Cleaning invalid history entry (not a list): {timestamp_str}")
             selected_collections.pop(timestamp_str, None)
             continue
        try:
            # Support both formats for robustness
            try: timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            except ValueError: timestamp = datetime.fromisoformat(timestamp_str) # Try ISO format too

            if timestamp >= cutoff_time:
                valid_titles = {t for t in titles if isinstance(t, str)}
                recent_titles.update(valid_titles)
                timestamps_to_keep[timestamp_str] = titles # Keep this entry
            else:
                 logging.debug(f"History entry {timestamp_str} is older than cutoff {cutoff_time}.")
                 # Don't add to timestamps_to_keep, it will be removed below

        except ValueError:
             logging.warning(f"Cleaning invalid date format in history: '{timestamp_str}'. Entry removed.")
             selected_collections.pop(timestamp_str, None)
        except Exception as e:
             logging.error(f"Cleaning problematic history entry '{timestamp_str}': {e}. Entry removed.")
             selected_collections.pop(timestamp_str, None)

    # Efficiently remove old keys
    keys_to_remove = set(selected_collections.keys()) - set(timestamps_to_keep.keys())
    removed_count = 0
    for key in keys_to_remove:
        selected_collections.pop(key, None)
        removed_count += 1

    if removed_count > 0:
         logging.info(f"Removed {removed_count} old entries from history file during cleanup.")
         save_selected_collections(selected_collections) # Save after cleanup

    if recent_titles:
        logging.info(f"Recently pinned non-special collections (excluded due to {repeat_block_hours}h block): {', '.join(sorted(list(recent_titles)))}")
    else:
        logging.info("No recently pinned non-special collections found within the repeat block window.")

    return recent_titles


def is_regex_excluded(title, patterns):
    """Checks if a title matches any regex pattern."""
    if not patterns or not isinstance(patterns, list): return False
    for pattern_str in patterns:
        if not isinstance(pattern_str, str) or not pattern_str: continue
        try:
            # Compile regex for efficiency if this were called many times with same patterns
            # For now, search directly
            if re.search(pattern_str, title, re.IGNORECASE):
                logging.info(f"Excluding '{title}' based on regex pattern: '{pattern_str}'")
                return True
        except re.error as e:
            logging.error(f"Invalid regex pattern '{pattern_str}' in config: {e}. Skipping this pattern.")
            # Optionally, you might want to remove/flag the invalid pattern in the config or cache
            continue # Skip this pattern and check others
        except Exception as e:
            logging.error(f"Unexpected error during regex check for title '{title}', pattern '{pattern_str}': {e}")
            return False # Fail safe: assume not excluded if error occurs
    return False


def load_config():
    """Loads configuration from config.json, exits on critical errors."""
    if not os.path.exists(CONFIG_PATH):
        logging.critical(f"CRITICAL: Config file not found at {CONFIG_PATH}. Please create it or use the Web UI. Exiting.")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        if not isinstance(config_data, dict):
            raise ValueError("Config file content is not a valid JSON object.")

        # --- Validate essential keys ---
        required_keys = ['plex_url', 'plex_token', 'pinning_interval', 'library_names', 'collexions_label', 'number_of_collections_to_pin', 'categories']
        missing_keys = [key for key in required_keys if key not in config_data]
        if missing_keys:
            logging.warning(f"Config file is missing the following keys: {', '.join(missing_keys)}. Using defaults or empty values where possible, but this may cause issues.")

        # --- Set defaults for non-critical missing keys ---
        config_data.setdefault('collexions_label', 'Collexions')
        config_data.setdefault('pinning_interval', 180)
        config_data.setdefault('repeat_block_hours', 12)
        config_data.setdefault('min_items_for_pinning', 10)
        config_data.setdefault('discord_webhook_url', '')
        config_data.setdefault('exclusion_list', [])
        config_data.setdefault('regex_exclusion_patterns', [])
        config_data.setdefault('special_collections', [])
        config_data.setdefault('library_names', [])
        config_data.setdefault('number_of_collections_to_pin', {})
        config_data.setdefault('categories', {}) # Ensure categories exists

        # --- Validate specific required keys needed before connection ---
        if not config_data.get('plex_url') or not config_data.get('plex_token'):
             raise ValueError("Missing required configuration: 'plex_url' and 'plex_token' must be set.")
        if not isinstance(config_data.get('library_names'), list):
            logging.warning("Config 'library_names' is not a list. Resetting to empty list.")
            config_data['library_names'] = []
        if not isinstance(config_data.get('categories'), dict):
             logging.warning("Config 'categories' is not a dictionary. Resetting to empty dict.")
             config_data['categories'] = {}


        logging.info("Configuration loaded and validated.")
        return config_data

    except json.JSONDecodeError as e:
        logging.critical(f"CRITICAL: Error decoding JSON from config file {CONFIG_PATH}: {e}. Exiting.")
        sys.exit(1)
    except ValueError as e:
         logging.critical(f"CRITICAL: Invalid or missing configuration in {CONFIG_PATH}: {e}. Exiting.")
         sys.exit(1)
    except Exception as e:
        logging.critical(f"CRITICAL: An unexpected error occurred while loading config file {CONFIG_PATH}: {e}. Exiting.", exc_info=True)
        sys.exit(1)


def connect_to_plex(config):
    """Connects to Plex server, returns PlexServer object or None."""
    plex_url = config.get('plex_url')
    plex_token = config.get('plex_token')

    if not plex_url or not plex_token:
        logging.error("Plex URL or Token is missing in the configuration.")
        return None

    try:
        logging.info(f"Attempting to connect to Plex server at {plex_url}...")
        # Increased timeout for potentially slower servers/networks
        plex = PlexServer(plex_url, plex_token, timeout=90)
        # Test connection by fetching server name (requires authentication)
        server_name = plex.friendlyName
        logging.info(f"Successfully connected to Plex server '{server_name}'.")
        return plex
    except Unauthorized:
        logging.error("Plex connection failed: Unauthorized. Check your Plex Token.")
        update_status("Error: Plex Unauthorized")
        return None
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Plex connection failed: Could not connect to {plex_url}. Check URL and network. Error: {e}")
        update_status("Error: Plex Connection Failed")
        return None
    except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout):
         logging.error(f"Plex connection failed: Request timed out connecting to {plex_url}.")
         update_status("Error: Plex Connection Timeout")
         return None
    except Exception as e:
        # Catch other potential exceptions from plexapi or requests
        logging.error(f"Plex connection failed: An unexpected error occurred: {e}", exc_info=True)
        update_status(f"Error: Plex Connection Unexpected ({type(e).__name__})")
        return None

def get_collections_from_library(plex, library_name):
    """Fetches all collection objects from a single specified library name."""
    collections_in_library = []
    if not plex or not library_name or not isinstance(library_name, str):
        logging.error(f"Invalid input for getting collections: plex={plex}, library_name={library_name}")
        return collections_in_library

    try:
        logging.info(f"Accessing library: '{library_name}'")
        library = plex.library.section(library_name)
        logging.info(f"Fetching collections from library '{library_name}'...")
        collections_in_library = library.collections()
        logging.info(f"Found {len(collections_in_library)} collections in '{library_name}'.")
    except NotFound:
        logging.error(f"Library '{library_name}' not found on the Plex server.")
    except Exception as e:
        logging.error(f"Error fetching collections from library '{library_name}': {e}", exc_info=True)

    return collections_in_library


def pin_collections(collections_to_pin, config, plex): # Added plex parameter
    """Pins the provided list of collections, adds label, and sends individual Discord notifications."""
    if not collections_to_pin:
        logging.info("Pin list is empty. Nothing to pin.")
        return [] # Return empty list if nothing to pin

    webhook_url = config.get('discord_webhook_url')
    label_to_add = config.get('collexions_label')
    successfully_pinned_titles = [] # Keep track of titles actually pinned

    logging.info(f"--- Attempting to Pin {len(collections_to_pin)} Collections ---")

    for collection in collections_to_pin:
        # Basic validation of the collection object
        if not hasattr(collection, 'title') or not hasattr(collection, 'key'):
            logging.warning(f"Skipping invalid collection object: {collection}")
            continue

        coll_title = collection.title
        item_count_str = "Unknown" # Default item count string

        try:
            # Fetch the latest version of the collection to ensure visibility() works
            # This can be network intensive if pinning many items
            # collection.reload() # Consider if this is necessary or too slow

            # Get item count safely
            try:
                # Use childCount for direct count if available and fast
                item_count = collection.childCount
                item_count_str = f"{item_count} Item{'s' if item_count != 1 else ''}"
            except Exception as e:
                 # Fallback or just log warning if count is not critical for pinning itself
                 logging.warning(f"Could not retrieve item count for '{coll_title}': {e}")
                 # item_count_str remains "Unknown"

            logging.info(f"Attempting to pin collection: '{coll_title}' ({item_count_str})")

            # Pinning operation using visibility
            try:
                hub = collection.visibility()
                hub.promoteHome()
                hub.promoteShared()
                log_message = f"Collection '{coll_title}' ({item_count_str}) pinned successfully."
                discord_message = f"📌 Collection '**{coll_title}**' ({item_count_str}) pinned successfully."
                logging.info(log_message)
                successfully_pinned_titles.append(coll_title) # Add to success list

                # Send Discord notification immediately after successful pin
                if webhook_url:
                    send_discord_message(webhook_url, discord_message)

            except Exception as pin_error:
                 logging.error(f"Failed to pin '{coll_title}' using visibility method: {pin_error}")
                 # Continue to label attempt even if pinning failed? Or skip?
                 # Let's skip labeling if pinning failed.
                 continue # Skip to the next collection

            # --- Add Label (only if pinning was successful) ---
            if label_to_add:
                try:
                    logging.info(f"Attempting to add label '{label_to_add}' to '{coll_title}'...")
                    collection.addLabel(label_to_add)
                    logging.info(f"Successfully added label '{label_to_add}' to '{coll_title}'.")
                except Exception as e:
                    # Log error but don't necessarily fail the whole run
                    logging.error(f"Failed to add label '{label_to_add}' to '{coll_title}': {e}")
            # --- End Add Label ---

        except NotFound:
            logging.error(f"Collection '{coll_title}' not found during processing (maybe deleted?). Skipping.")
        except Exception as e:
            logging.error(f"Unexpected error processing collection '{coll_title}' for pinning: {e}", exc_info=True)

    logging.info(f"--- Pinning process complete. Successfully pinned {len(successfully_pinned_titles)} collections. ---")
    return successfully_pinned_titles # Return the list of titles successfully pinned


def send_discord_message(webhook_url, message):
    """Sends a message to the specified Discord webhook URL."""
    if not webhook_url or not isinstance(webhook_url, str):
        logging.debug("Discord webhook URL not configured or invalid.")
        return
    if not message or not isinstance(message, str):
        logging.warning("Attempted to send empty or invalid message to Discord.")
        return

    # Basic formatting check for Discord limits (optional)
    if len(message) > 2000:
        message = message[:1997] + "..."
        logging.warning("Discord message truncated to 2000 characters.")

    data = {"content": message}
    logging.info(f"Sending message to Discord webhook...") #: '{message[:50]}...'") # Log first 50 chars

    try:
        response = requests.post(webhook_url, json=data, timeout=15) # Increased timeout
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        logging.info(f"Discord message sent successfully (Status Code: {response.status_code}).")
    except requests.exceptions.Timeout:
        logging.error(f"Failed to send Discord message: Request timed out.")
    except requests.exceptions.RequestException as e:
        # This catches connection errors, invalid URL errors, etc.
        logging.error(f"Failed to send Discord message: {e}")
    except Exception as e:
        # Catch any other unexpected errors during the request
        logging.error(f"An unexpected error occurred while sending Discord message: {e}")


def unpin_collections(plex, library_names, config):
    """Unpins currently promoted collections managed by this script (matching label) in specified libraries."""
    if not plex:
        logging.error("Plex connection not available. Skipping unpin process.")
        return

    label_to_check = config.get('collexions_label')
    # If no label is defined, we cannot safely identify which collections to unpin.
    if not label_to_check:
        logging.warning("'collexions_label' is not defined in config. Skipping unpin process to avoid unpinning unintended collections.")
        return

    exclusion_list = config.get('exclusion_list', []) # Titles to *never* unpin, even if labeled
    exclusion_set = set(exclusion_list) if isinstance(exclusion_list, list) else set()

    logging.info(f"--- Starting Unpin Check for Libraries: {library_names} ---")
    logging.info(f"Looking for collections with label: '{label_to_check}'")
    logging.info(f"Will skip unpinning if title is in exclusion list: {exclusion_set or 'None'}")

    unpinned_count = 0
    label_removed_count = 0
    skipped_due_to_exclusion = 0

    for library_name in library_names:
        if not isinstance(library_name, str):
            logging.warning(f"Skipping invalid library name during unpin: {library_name}")
            continue

        try:
            logging.info(f"Checking library '{library_name}' for collections to unpin...")
            library = plex.library.section(library_name)
            # Fetch all collections once per library
            collections_in_library = library.collections()
            logging.info(f"Found {len(collections_in_library)} total collections in '{library_name}'. Checking promotion status and label...")

            collections_processed = 0
            for collection in collections_in_library:
                 # Basic check
                 if not hasattr(collection, 'title') or not hasattr(collection, 'key'):
                    logging.warning(f"Skipping potentially invalid collection object in '{library_name}': {collection}")
                    continue

                 coll_title = collection.title
                 collections_processed += 1

                 try:
                     # 1. Check if collection is currently promoted
                     hub = collection.visibility()
                     if hub and hub.promoteHome: # Check specific attribute for home promotion
                         logging.debug(f"Collection '{coll_title}' is currently promoted. Checking label and exclusion...")

                         # 2. Check if it has the target label
                         current_labels = [l.tag.lower() for l in collection.labels] if hasattr(collection, 'labels') else [] # Case-insensitive check
                         if label_to_check.lower() in current_labels:
                             logging.debug(f"Collection '{coll_title}' has the label '{label_to_check}'.")

                             # 3. Check if it's in the explicit exclusion list
                             if coll_title in exclusion_set:
                                 logging.info(f"Skipping unpin for '{coll_title}' because it is in the explicit exclusion list, even though it has the label.")
                                 skipped_due_to_exclusion += 1
                                 continue # Do not unpin or remove label if explicitly excluded

                             # 4. If promoted, labeled, and not excluded -> Proceed to unpin and remove label
                             try:
                                 logging.info(f"Attempting to unpin and remove label from '{coll_title}'...")
                                 # Remove Label First
                                 try:
                                     collection.removeLabel(label_to_check)
                                     logging.info(f"Removed label '{label_to_check}' from '{coll_title}'.")
                                     label_removed_count += 1
                                 except Exception as e:
                                     logging.error(f"Failed to remove label '{label_to_check}' from '{coll_title}': {e}")
                                     # Decide if we should still try to unpin? Let's try.

                                 # Then Demote
                                 try:
                                     hub.demoteHome()
                                     hub.demoteShared()
                                     logging.info(f"Unpinned '{coll_title}' successfully.")
                                     unpinned_count += 1
                                 except Exception as demote_error:
                                     logging.error(f"Failed to demote/unpin '{coll_title}': {demote_error}")
                                     # If demotion fails after label removal, log it. Re-adding label might be complex.

                             except Exception as unpin_label_err:
                                 logging.error(f"Error during unpin/label removal process for '{coll_title}': {unpin_label_err}", exc_info=True)

                         else:
                              logging.debug(f"Collection '{coll_title}' is promoted but does not have the label '{label_to_check}'. Skipping unpin/unlabel.")
                     # else: # Optional: Log collections checked but not promoted
                     #    logging.debug(f"Collection '{coll_title}' is not promoted. Skipping.")

                 except NotFound:
                      logging.warning(f"Collection '{coll_title}' seems to have been deleted during processing. Skipping.")
                 except Exception as vis_error:
                      logging.error(f"Error checking visibility or processing '{coll_title}' for unpin: {vis_error}", exc_info=True)

            logging.info(f"Finished checking {collections_processed} collections in '{library_name}'.")

        except NotFound:
            logging.error(f"Library '{library_name}' not found during unpin check.")
        except Exception as e:
            logging.error(f"General error during unpin process for library '{library_name}': {e}", exc_info=True)

    logging.info(f"--- Unpinning Check Complete ---")
    logging.info(f"Unpinned: {unpinned_count} collections.")
    logging.info(f"Removed label from: {label_removed_count} collections.")
    if skipped_due_to_exclusion > 0:
        logging.info(f"Skipped unpinning for {skipped_due_to_exclusion} collections due to exclusion list.")


def get_active_special_collections(config):
    """Determines which 'special' collections are active based on current date."""
    current_date = datetime.now().date()
    active_titles = []
    special_configs = config.get('special_collections', [])

    if not isinstance(special_configs, list):
        logging.warning("Config 'special_collections' is not a list. No special collections will be processed.")
        return []

    logging.info(f"--- Checking {len(special_configs)} Special Collection Periods for today ({current_date.strftime('%Y-%m-%d')}) ---")
    processed_count = 0
    for i, special in enumerate(special_configs):
        # Validate structure
        if not isinstance(special, dict) or not all(k in special for k in ['start_date', 'end_date', 'collection_names']):
             logging.warning(f"Skipping invalid special collection entry #{i+1}: Missing keys. Requires 'start_date', 'end_date', 'collection_names'. Entry: {special}")
             continue

        s_date_str = special.get('start_date')
        e_date_str = special.get('end_date')
        names = special.get('collection_names')

        # Validate types
        if not isinstance(s_date_str, str) or not isinstance(e_date_str, str) or not isinstance(names, list):
             logging.warning(f"Skipping invalid special collection entry #{i+1}: Incorrect data types. Requires strings for dates, list for names. Entry: {special}")
             continue
        if not all(isinstance(n, str) for n in names):
             logging.warning(f"Skipping invalid special collection entry #{i+1}: 'collection_names' contains non-string elements. Entry: {special}")
             continue

        processed_count += 1
        logging.debug(f"Processing special period: Start={s_date_str}, End={e_date_str}, Names={names}")

        try:
            # Parse dates (MM-DD format) and adjust year to current year
            start_month_day = datetime.strptime(s_date_str, '%m-%d')
            end_month_day = datetime.strptime(e_date_str, '%m-%d')

            start_date = start_month_day.replace(year=current_date.year).date()
            end_date = end_month_day.replace(year=current_date.year).date()

            # Handle date ranges that wrap around the new year (e.g., Dec 15 - Jan 10)
            if start_date > end_date:
                # Check if current date is within the range (start_date to end of year OR start of year to end_date)
                if current_date >= start_date or current_date <= end_date:
                    is_active = True
                    logging.debug(f"  -> Active (Year Wrap): Current date {current_date} is within {start_date} to {end_date}")
                else:
                    is_active = False
                    logging.debug(f"  -> Inactive (Year Wrap): Current date {current_date} is outside {start_date} to {end_date}")
            else:
                # Standard range check (inclusive)
                if start_date <= current_date <= end_date:
                    is_active = True
                    logging.debug(f"  -> Active (Standard): Current date {current_date} is within {start_date} to {end_date}")
                else:
                    is_active = False
                    logging.debug(f"  -> Inactive (Standard): Current date {current_date} is outside {start_date} to {end_date}")

            if is_active:
                active_titles.extend(n for n in names if n) # Add non-empty names
                logging.info(f"Special period '{names}' is ACTIVE today ({start_date} to {end_date}). Adding to active list.")

        except ValueError:
            logging.error(f"Invalid date format in special collection entry #{i+1}. Dates must be MM-DD. Entry: {special}")
        except Exception as e:
            logging.error(f"Error processing special collection entry #{i+1} ('{names}'): {e}", exc_info=True)

    unique_active = sorted(list(set(active_titles)))
    logging.info(f"--- Special Collection Check Complete ---")
    if unique_active:
        logging.info(f"Total unique ACTIVE special collection titles for today: {unique_active}")
    else:
        logging.info("No special collection periods are active today.")
    return unique_active


def get_fully_excluded_collections(config, active_special_collections):
    """Combines explicit exclusions and inactive special collections for full exclusion set."""
    # 1. Explicit exclusions from config
    exclusion_raw = config.get('exclusion_list', [])
    if not isinstance(exclusion_raw, list):
        logging.warning("Config 'exclusion_list' is not a list. Treating as empty.")
        exclusion_raw = []
    explicit_exclusion_set = {name.strip() for name in exclusion_raw if isinstance(name, str) and name.strip()}
    logging.info(f"Explicit title exclusions from config: {explicit_exclusion_set or 'None'}")

    # 2. Get all titles defined in *any* special period (active or inactive)
    all_special_titles = get_all_special_collection_names(config)

    # 3. Find inactive special titles (all special titles MINUS the currently active ones)
    active_special_set = set(active_special_collections)
    inactive_special_set = all_special_titles - active_special_set
    if inactive_special_set:
        logging.info(f"Inactive special collections (excluded from random/category selection): {inactive_special_set}")
    else:
         logging.info("No inactive special collections identified.")


    # 4. Combine explicit and inactive special exclusions
    # Collections explicitly excluded are always excluded.
    # Collections defined in *any* special period are excluded from random/category pinning *unless* they are currently active.
    combined_exclusion_set = explicit_exclusion_set.union(inactive_special_set)

    logging.info(f"Total combined title exclusions (explicit + inactive special): {combined_exclusion_set or 'None'}")
    return combined_exclusion_set

def get_all_special_collection_names(config):
    """Returns a set of all unique collection names defined across all special_collections entries in config."""
    all_special_titles = set()
    special_configs = config.get('special_collections', [])

    if not isinstance(special_configs, list):
        logging.warning("Config 'special_collections' is not a list. Cannot identify all special titles.")
        return all_special_titles

    for i, special in enumerate(special_configs):
        if isinstance(special, dict) and 'collection_names' in special and isinstance(special['collection_names'], list):
             # Add valid string names to the set
             valid_names = {name.strip() for name in special['collection_names'] if isinstance(name, str) and name.strip()}
             if len(valid_names) < len(special['collection_names']):
                 logging.debug(f"Cleaned/filtered names from special entry #{i+1}: Original={special['collection_names']}, Valid={valid_names}")
             all_special_titles.update(valid_names)
        else:
             # Log only if the entry itself seems intended but malformed
             if isinstance(special, dict) and special: # Avoid logging for empty list entries etc.
                logging.warning(f"Skipping invalid entry when getting all special names (entry #{i+1}): {special}")

    # No need to log here, get_fully_excluded_collections does it
    # if all_special_titles:
    #     logging.debug(f"Identified {len(all_special_titles)} unique titles defined across all special_collections entries.")
    return all_special_titles


# REMOVED old select_from_categories function as logic is now in filter_collections

def fill_with_random_collections(random_collections_pool, remaining_slots):
    """Fills remaining slots with random choices from the provided pool."""
    collections_to_pin = []
    if remaining_slots <= 0:
        logging.debug("No remaining slots for random selection.")
        return collections_to_pin
    if not random_collections_pool:
        logging.info("No eligible collections left in the pool for random selection.")
        return collections_to_pin

    # Ensure pool is a list for shuffling
    available = list(random_collections_pool)
    random.shuffle(available)

    num_to_select = min(remaining_slots, len(available))
    logging.info(f"Selecting up to {num_to_select} random collection(s) from the remaining {len(available)} eligible items.")

    selected_random = available[:num_to_select]
    collections_to_pin.extend(selected_random)

    # Log the selected random collections
    if selected_random:
        selected_titles = [getattr(c, 'title', 'Untitled') for c in selected_random]
        logging.info(f"Added {len(selected_titles)} random collection(s): {selected_titles}")
    else:
         logging.info("No random collections were selected (either no slots or no available items).")

    return collections_to_pin


def filter_collections(config, all_collections_in_library, active_special_titles, library_pin_limit, library_name, selected_collections_history):
    """Filters collections and selects pins based on configured priorities (Special > Category > Random) for a specific library."""

    logging.info(f"--- Starting Filtering and Selection for Library: '{library_name}' (Pin Limit: {library_pin_limit}) ---")

    # --- Initial Filtering ---
    min_items_threshold = config.get('min_items_for_pinning', 10)
    if not isinstance(min_items_threshold, int) or min_items_threshold < 0:
        logging.warning(f"Invalid 'min_items_for_pinning' ({min_items_threshold}), defaulting to 10.")
        min_items_threshold = 10
    logging.info(f"Filtering Step 1: Applying minimum item count threshold = {min_items_threshold}")

    # Get titles fully excluded (explicit list + inactive specials)
    # Note: Active specials are NOT excluded here, they are handled by priority.
    titles_fully_excluded = get_fully_excluded_collections(config, active_special_titles)

    # Get titles recently pinned (non-special only)
    recently_pinned_non_special_titles = get_recently_pinned_collections(selected_collections_history, config)

    # Get regex exclusion patterns
    regex_patterns = config.get('regex_exclusion_patterns', [])
    if not isinstance(regex_patterns, list):
        logging.warning("Config 'regex_exclusion_patterns' is not a list. No regex exclusions will be applied.")
        regex_patterns = []

    eligible_collections_pool = [] # Collections passing initial filters
    logging.info(f"Processing {len(all_collections_in_library)} collections found in '{library_name}' through initial filters...")

    for collection in all_collections_in_library:
        # Basic validation
        if not hasattr(collection, 'title') or not collection.title:
            logging.debug(f"Skipping collection with missing title: {collection}")
            continue
        coll_title = collection.title

        # Filter 1: Explicit title exclusion (includes inactive specials)
        if coll_title in titles_fully_excluded:
            logging.debug(f"Excluding '{coll_title}' (Explicit or Inactive Special Title Exclusion).")
            continue

        # Filter 2: Regex exclusion
        if is_regex_excluded(coll_title, regex_patterns):
            # Logging done within is_regex_excluded
            continue

        # Filter 3: Minimum item count (Skip check if it's an *active* special collection)
        is_active_special = coll_title in active_special_titles
        if not is_active_special: # Only check count if not an active special
            try:
                item_count = collection.childCount
                if item_count < min_items_threshold:
                    logging.debug(f"Excluding '{coll_title}' (Low item count: {item_count} < {min_items_threshold}).")
                    continue
            except AttributeError:
                logging.warning(f"Excluding '{coll_title}' due to AttributeError when getting item count (childCount).")
                continue
            except Exception as e:
                logging.warning(f"Excluding '{coll_title}' due to error getting item count: {e}")
                continue
        else:
             logging.debug(f"Skipping item count check for ACTIVE special collection '{coll_title}'.")


        # Filter 4: Recently pinned (non-special) exclusion
        # Only apply this if the collection is NOT an active special
        if not is_active_special and coll_title in recently_pinned_non_special_titles:
            logging.debug(f"Excluding '{coll_title}' (Recently pinned non-special item within repeat block).")
            continue

        # If all filters passed, add to the eligible pool for priority selection
        logging.debug(f"Collection '{coll_title}' passed initial filters. Adding to eligible pool.")
        eligible_collections_pool.append(collection)

    logging.info(f"Found {len(eligible_collections_pool)} eligible collections in '{library_name}' after initial filtering.")
    if not eligible_collections_pool:
        logging.info(f"No collections eligible for pinning in '{library_name}'. Skipping priority selection.")
        return [] # Return empty list

    # --- Priority Selection ---
    collections_to_pin = []
    pinned_titles = set() # Keep track of titles already selected in this run
    remaining_slots = library_pin_limit

    # Make a copy of the pool to avoid modifying it directly during iteration? No, selection is fine.
    # Shuffle the pool *once* upfront to ensure randomness within priorities
    random.shuffle(eligible_collections_pool)
    logging.debug(f"Shuffled eligible pool: {[c.title for c in eligible_collections_pool]}")

    # --- Priority 1: Active Special Collections ---
    logging.info(f"Selection Step 1: Prioritizing {len(active_special_titles)} Active Special Collection(s).")
    special_collections_found = []
    temp_eligible_pool = [] # Build a new pool excluding specials we pick
    for collection in eligible_collections_pool:
        coll_title = collection.title
        if coll_title in active_special_titles and remaining_slots > 0 and coll_title not in pinned_titles:
            logging.info(f"  Selecting ACTIVE special collection: '{coll_title}'")
            special_collections_found.append(collection)
            pinned_titles.add(coll_title)
            remaining_slots -= 1
        else:
            # Add non-specials or specials not picked to the next stage pool
            temp_eligible_pool.append(collection)

    collections_to_pin.extend(special_collections_found)
    eligible_collections_pool = temp_eligible_pool # Update pool for next stages
    logging.info(f"Selected {len(special_collections_found)} special collections. Remaining slots: {remaining_slots}")

    # --- Priority 2: Category Collections ---
    if remaining_slots > 0:
        logging.info(f"Selection Step 2: Processing Categories for '{library_name}'.")
        # Get category definitions specific to this library
        library_categories_config = config.get('categories', {}).get(library_name, [])

        if not library_categories_config:
            logging.info(f"  No categories defined for library '{library_name}'. Skipping category selection.")
        else:
            logging.info(f"  Found {len(library_categories_config)} category definitions for '{library_name}'.")
            temp_eligible_pool = [] # Pool for collections not picked by categories
            processed_in_categories = set() # Track titles picked in this step

            # Iterate through eligible pool *once* and check against *all* categories
            category_collections_found = []

            # Create a lookup for faster category checking: {title: [category_configs]}
            category_title_map = {}
            for cat_idx, category_def in enumerate(library_categories_config):
                 pin_count = category_def.get('pin_count', 0)
                 cat_name = category_def.get('category_name', f'Unnamed Cat {cat_idx}')
                 if pin_count > 0:
                     for title in category_def.get('collections', []):
                         if title not in category_title_map: category_title_map[title] = []
                         # Store the config dict itself for easy access to pin_count etc.
                         category_title_map[title].append(category_def)
                 else:
                     logging.debug(f"  Skipping category '{cat_name}' as pin count is 0.")

            # Keep track of how many we still want from each category
            category_slots_remaining = {cat_def['category_name']: cat_def['pin_count']
                                        for cat_def in library_categories_config if cat_def.get('pin_count', 0) > 0}


            # Iterate through the shuffled eligible pool
            pool_after_categories = [] # Items not picked by categories go here
            for collection in eligible_collections_pool:
                 coll_title = collection.title
                 picked_by_category = False

                 if remaining_slots <= 0: # Stop if global limit reached
                      pool_after_categories.append(collection)
                      continue

                 # Check if this collection belongs to any *active* category
                 if coll_title in category_title_map:
                      # Belongs to one or more categories, try to pick it
                      # Iterate through categories it belongs to (shuffled order implicitly via pool)
                      for category_def in category_title_map[coll_title]:
                           cat_name = category_def['category_name']
                           # Check if this category still needs items AND global slots remain
                           if category_slots_remaining.get(cat_name, 0) > 0 and remaining_slots > 0:
                                logging.info(f"  Selecting collection '{coll_title}' for category '{cat_name}'.")
                                category_collections_found.append(collection)
                                pinned_titles.add(coll_title)
                                remaining_slots -= 1
                                category_slots_remaining[cat_name] -= 1 # Decrement category specific slot
                                picked_by_category = True
                                break # Picked for one category, move to next collection

                 if not picked_by_category:
                      # Add to the pool for random selection if not picked by category
                      pool_after_categories.append(collection)


            collections_to_pin.extend(category_collections_found)
            eligible_collections_pool = pool_after_categories # Update pool for random stage
            logging.info(f"Selected {len(category_collections_found)} collections from categories. Remaining slots: {remaining_slots}")

    else:
         logging.info("Skipping category selection (no remaining slots).")


    # --- Priority 3: Random Fill ---
    if remaining_slots > 0:
        logging.info(f"Selection Step 3: Filling remaining {remaining_slots} slot(s) randomly.")
        # The pool already contains items not picked by special or category, and is shuffled
        random_collections_found = fill_with_random_collections(eligible_collections_pool, remaining_slots)
        collections_to_pin.extend(random_collections_found)
        # Update remaining_slots for final log, though not used further
        remaining_slots -= len(random_collections_found)
    else:
        logging.info("Skipping random selection (no remaining slots).")


    # --- Final Result ---
    final_selected_titles = [getattr(c, 'title', 'Untitled') for c in collections_to_pin]
    logging.info(f"--- Filtering and Selection Complete for '{library_name}' ---")
    logging.info(f"Final list of {len(final_selected_titles)} collections selected for pinning: {final_selected_titles}")

    return collections_to_pin


# --- Main Function ---
def main():
    """Main execution loop."""
    run_start_time = datetime.now()
    logging.info(f"====== Starting Collexions Script Run at {run_start_time.strftime('%Y-%m-%d %H:%M:%S')} ======")
    update_status("Starting") # Initial status

    # --- Load Config ---
    try:
        config = load_config()
    except SystemExit:
        update_status("CRITICAL: Config Error")
        # load_config already logged the critical error
        return # Exit main if config fails critically

    # --- Calculate Sleep Interval ---
    pin_interval_minutes = config.get('pinning_interval', 180)
    if not isinstance(pin_interval_minutes, (int, float)) or pin_interval_minutes <= 0:
        logging.warning(f"Invalid 'pinning_interval' ({pin_interval_minutes}), defaulting to 180 minutes.")
        pin_interval_minutes = 180
    sleep_seconds = pin_interval_minutes * 60
    next_run_calc_time = run_start_time + timedelta(minutes=pin_interval_minutes)
    logging.info(f"Pinning interval set to {pin_interval_minutes} minutes. Next run approximately: {next_run_calc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    update_status("Running", next_run_calc_time.timestamp()) # Update status with planned next run

    # --- Connect to Plex ---
    plex = connect_to_plex(config)
    if not plex:
        # Error logged in connect_to_plex, status updated there too.
        logging.critical("Failed to connect to Plex. Aborting this run.")
        # Don't sys.exit, allow script to sleep and retry later
        return

    # --- Load History ---
    selected_collections_history = load_selected_collections()

    # --- Unpin First ---
    library_names = config.get('library_names', [])
    if not library_names:
        logging.warning("No 'library_names' defined in config. Nothing to process.")
    else:
        unpin_collections(plex, library_names, config)

    # --- Process Each Library for Pinning ---
    collections_per_library_config = config.get('number_of_collections_to_pin', {})
    if not isinstance(collections_per_library_config, dict):
        logging.warning("Config 'number_of_collections_to_pin' is not a dictionary. Using defaults (0 pins).")
        collections_per_library_config = {}

    all_newly_pinned_titles_this_run = [] # Track all titles successfully pinned across all libraries

    for library_name in library_names:
        library_process_start = time.time()
        if not isinstance(library_name, str):
            logging.warning(f"Skipping invalid library name in list: {library_name}")
            continue

        pin_limit = collections_per_library_config.get(library_name, 0)
        if not isinstance(pin_limit, int) or pin_limit < 0:
            logging.warning(f"Invalid pin limit for '{library_name}' ({pin_limit}). Defaulting to 0.")
            pin_limit = 0

        if pin_limit == 0:
            logging.info(f"Skipping library '{library_name}' as its pin limit is set to 0.")
            continue

        logging.info(f"===== Processing Library: '{library_name}' (Pin Limit: {pin_limit}) =====")
        update_status(f"Processing: {library_name}", next_run_calc_time.timestamp())

        # --- Get Collections for this Library ---
        all_colls_in_lib = get_collections_from_library(plex, library_name)
        if not all_colls_in_lib:
            logging.info(f"No collections found or retrieved from library '{library_name}'. Skipping pinning for this library.")
            continue

        # --- Filter and Select Collections ---
        active_specials = get_active_special_collections(config) # Get currently active specials
        colls_to_pin_for_library = filter_collections(
            config,
            all_colls_in_lib,
            active_specials,
            pin_limit,
            library_name,
            selected_collections_history # Pass history for recency check
        )

        # --- Pin Selected Collections for this Library ---
        if colls_to_pin_for_library:
            logging.info(f"Attempting to pin {len(colls_to_pin_for_library)} selected collections for '{library_name}'...")
            # Pass plex object to pin_collections
            successfully_pinned_titles = pin_collections(colls_to_pin_for_library, config, plex)
            all_newly_pinned_titles_this_run.extend(successfully_pinned_titles) # Add successfully pinned titles to the run list
        else:
            logging.info(f"No collections were selected for pinning in '{library_name}' after filtering.")

        logging.info(f"Finished processing library '{library_name}' in {time.time() - library_process_start:.2f} seconds.")
        logging.info(f"===== Completed Library: '{library_name}' =====")


    # --- Update History File (only non-special items from the successfully pinned list) ---
    if all_newly_pinned_titles_this_run:
        current_timestamp_iso = datetime.now().isoformat() # Use ISO format for consistency
        unique_new_pins_all = set(all_newly_pinned_titles_this_run)
        all_special_titles_ever = get_all_special_collection_names(config) # Get all titles ever defined as special

        non_special_pins_for_history = {
            title for title in unique_new_pins_all
            if title not in all_special_titles_ever # Exclude if title ever appeared in *any* special config
        }

        if non_special_pins_for_history:
             history_entry = sorted(list(non_special_pins_for_history))
             # Prune history before adding new entry (optional, depends on desired history size)
             # prune_history(selected_collections_history, max_entries=100)
             selected_collections_history[current_timestamp_iso] = history_entry
             save_selected_collections(selected_collections_history)
             logging.info(f"Updated history file ({SELECTED_COLLECTIONS_FILE}) for timestamp {current_timestamp_iso} with {len(history_entry)} non-special pinned items.")

             # Log difference if any specials were pinned
             num_specials_pinned = len(unique_new_pins_all) - len(non_special_pins_for_history)
             if num_specials_pinned > 0:
                 logging.info(f"Note: {num_specials_pinned} special collection(s) were pinned but not added to recency history tracking.")
        else:
             logging.info("Only special collections (or none) were successfully pinned this cycle. History file not updated for recency blocking.")
    else:
         logging.info("Nothing was successfully pinned this cycle. History file not updated.")
    # --- End History Update ---

    run_end_time = datetime.now()
    logging.info(f"====== Collexions Script Run Finished at {run_end_time.strftime('%Y-%m-%d %H:%M:%S')} ======")
    logging.info(f"Total run duration: {run_end_time - run_start_time}")


# --- Continuous Loop ---
def run_continuously():
    """Runs the main logic in a loop with sleep."""
    while True:
        run_start = time.time()
        next_run_timestamp_planned = None # Reset planned time
        try:
            # --- Load config fresh each cycle ---
            # Moved loading inside main() to handle errors per cycle
            # config = load_config() # Now loaded inside main()

            # Calculate sleep time based on potentially updated config *before* main()
            temp_config = {}
            try:
                if os.path.exists(CONFIG_PATH):
                    with open(CONFIG_PATH, 'r', encoding='utf-8') as f: temp_config = json.load(f)
            except Exception: pass # Ignore errors here, load_config inside main will handle them properly
            pin_interval = temp_config.get('pinning_interval', 180)
            if not isinstance(pin_interval, (int, float)) or pin_interval <= 0: pin_interval = 180
            sleep_sec = pin_interval * 60
            next_run_timestamp_planned = (datetime.now() + timedelta(seconds=sleep_sec)).timestamp()

            # --- Run the main processing logic ---
            main() # Contains its own error handling for config/plex connection

        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Exiting Collexions script.")
            update_status("Stopped (Keyboard Interrupt)")
            break # Exit the while loop
        except SystemExit as e:
             logging.critical(f"SystemExit called, exiting Collexions script. Exit code: {e.code}")
             update_status("Stopped (SystemExit)")
             break # Exit loop if sys.exit was called (e.g., critical config error)
        except Exception as e:
            # Catch any unexpected errors *outside* the main() function's try/except
            logging.critical(f"CRITICAL UNHANDLED EXCEPTION in main loop: {e}", exc_info=True)
            update_status(f"CRASHED ({type(e).__name__})")
            # Decide whether to break or try to continue after a delay
            sleep_sec = 60 # Sleep for a short period before potentially retrying
            logging.error(f"Sleeping for {sleep_sec} seconds before next attempt after crash.")


        # --- Sleep ---
        if next_run_timestamp_planned:
            update_status("Sleeping", next_run_timestamp_planned)
            logging.info(f"Next run scheduled around: {datetime.fromtimestamp(next_run_timestamp_planned).strftime('%Y-%m-%d %H:%M:%S')}")
        else:
             # Fallback if planned time wasn't calculated
             update_status("Sleeping")
             next_run_fallback = datetime.now() + timedelta(seconds=sleep_sec)
             logging.info(f"Next run approximately: {next_run_fallback.strftime('%Y-%m-%d %H:%M:%S')}")


        logging.info(f"Sleeping for {pin_interval:.1f} minutes ({sleep_sec:.0f} seconds)...")
        try:
            # Use a loop for sleep to make it interruptible sooner
            sleep_end_time = time.time() + sleep_sec
            while time.time() < sleep_end_time:
                 time.sleep(1) # Check every second for KeyboardInterrupt

        except KeyboardInterrupt:
             logging.info("Keyboard interrupt received during sleep. Exiting Collexions script.")
             update_status("Stopped (Keyboard Interrupt)")
             break # Exit the while loop

# --- Script Entry Point ---
if __name__ == "__main__":
    # Initial status update when script starts
    update_status("Initializing")
    try:
        run_continuously()
    except Exception as e:
        # Final catch-all for any error during startup or loop setup
        logging.critical(f"FATAL ERROR: Collexions script encountered an unrecoverable error: {e}", exc_info=True)
        update_status("FATAL ERROR")
        sys.exit(1) # Exit with error code