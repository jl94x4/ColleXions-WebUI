# --- Imports ---
import random
import logging
import time
import json
import os
import sys
import re
import requests
import copy 
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest, Unauthorized
from datetime import datetime, timedelta
import argparse
from jsonschema import validate, exceptions as jsonschema_exceptions

# --- Configuration & Constants (Updated for Docker) ---
APP_DIR = '/app'
CONFIG_DIR = os.path.join(APP_DIR, 'config')
LOG_DIR = os.path.join(APP_DIR, 'logs')
DATA_DIR = os.path.join(APP_DIR, 'data')

CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
LOG_FILE = os.path.join(LOG_DIR, 'collexions.log')
SELECTED_COLLECTIONS_FILE = os.path.join(DATA_DIR, 'selected_collections.json')
STATUS_FILE = os.path.join(DATA_DIR, 'status.json')
LAST_PINNED_DETAILS_FILE = os.path.join(DATA_DIR, 'last_pinned_details.json')

# --- Script-level global for Dry-Run Mode ---
_DRY_RUN_MODE_ACTIVE = False

# --- Configuration Schema Definition ---
CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "plex_url": {"type": "string", "format": "uri"},
        "plex_token": {"type": "string", "minLength": 1},
        "pinning_interval": {"type": "integer", "minimum": 1, "default": 180},
        "library_names": {"type": "array", "items": {"type": "string"}, "minItems": 0, "default": []},
        "collexions_label": {"type": "string", "default": "Collexions"},
        "number_of_collections_to_pin": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}, "default": {}},
        "categories": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "object", "properties": {"category_name": {"type": "string"}, "collections": {"type": "array", "items": {"type": "string"}}, "pin_count": {"type": "integer", "minimum": 0}}, "required": ["category_name", "collections", "pin_count"]}}, "default": {}},
        "repeat_block_hours": {"type": "integer", "minimum": 0, "default": 12},
        "min_items_for_pinning": {"type": "integer", "minimum": 0, "default": 10},
        "discord_webhook_url": {"type": ["string", "null"], "format": "uri", "default": ""},
        "exclusion_list": {"type": "array", "items": {"type": "string"}, "default": []},
        "regex_exclusion_patterns": {"type": "array", "items": {"type": "string"}, "default": []},
        "special_collections": {"type": "array", "items": {"type": "object", "properties": {"start_date": {"type": "string", "pattern": "^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"}, "end_date": {"type": "string", "pattern": "^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"}, "collection_names": {"type": "array", "items": {"type": "string"}, "minItems": 1}}, "required": ["start_date", "end_date", "collection_names"]}, "default": []},
        "use_random_category_mode": {"type": "boolean", "default": False},
        "random_category_skip_percent": {"type": "integer", "minimum": 0, "maximum": 100, "default": 70}
    },
    "required": ["plex_url", "plex_token"]
}

# --- Setup Logging ---
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
        print(f"INFO: Log directory created at {LOG_DIR}")
    except OSError as e:
        sys.stderr.write(f"CRITICAL: Error creating log directory '{LOG_DIR}': {e}. Exiting.\n")
        sys.exit(1)
log_handlers = [logging.StreamHandler(sys.stdout)]
try:
    log_handlers.append(logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'))
except Exception as e:
    sys.stderr.write(f"Warning: Error setting up file log handler for '{LOG_FILE}': {e}\n")
logging.basicConfig(
    level=logging.INFO, # Ensure level is INFO or DEBUG to see all logs
    format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=log_handlers
)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# --- Status Update Function ---
def update_status(status_message="Running", next_run_timestamp=None):
    global _DRY_RUN_MODE_ACTIVE
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            logging.info(f"Created data directory: {DATA_DIR}")
        except OSError as e:
            logging.error(f"Could not create data directory {DATA_DIR}: {e}. Status update might fail.")
            return
    effective_status_message = status_message
    if _DRY_RUN_MODE_ACTIVE:
        effective_status_message = f"[DRY-RUN] {status_message}"
    status_data = {"status": effective_status_message, "last_update": datetime.now().isoformat()}
    if next_run_timestamp:
        if isinstance(next_run_timestamp, (int, float)):
             status_data["next_run_timestamp"] = next_run_timestamp
        else:
             logging.warning(f"Invalid next_run_timestamp type ({type(next_run_timestamp)}), skipping.")
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error writing status file '{STATUS_FILE}': {e}")

# --- Functions ---
# ... (load_selected_collections, save_selected_collections, get_recently_pinned_collections, is_regex_excluded, load_config, connect_to_plex, get_collections_from_library are assumed correct from previous versions) ...
def load_selected_collections():
    if not os.path.exists(DATA_DIR):
        logging.warning(f"Data directory {DATA_DIR} not found when loading history. Assuming no history.")
        return {}
    if os.path.exists(SELECTED_COLLECTIONS_FILE):
        try:
            if os.path.getsize(SELECTED_COLLECTIONS_FILE) == 0:
                 logging.warning(f"History file {SELECTED_COLLECTIONS_FILE} is empty. Resetting history.")
                 return {}
            with open(SELECTED_COLLECTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    logging.debug(f"Loaded {len(data)} entries from history file {SELECTED_COLLECTIONS_FILE}")
                    return data
                else:
                    logging.error(f"Invalid format in {SELECTED_COLLECTIONS_FILE} (not a dict). Resetting history.");
                    return {}
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {SELECTED_COLLECTIONS_FILE}: {e}. Resetting history.");
            return {}
        except Exception as e:
            logging.error(f"Error loading {SELECTED_COLLECTIONS_FILE}: {e}. Resetting history.");
            return {}
    else:
        logging.info(f"History file {SELECTED_COLLECTIONS_FILE} not found. Starting fresh.")
        return {}

def save_selected_collections(selected_collections):
    global _DRY_RUN_MODE_ACTIVE
    if _DRY_RUN_MODE_ACTIVE:
        logging.info(f"DRY-RUN: Would save {len(selected_collections)} entries to history file {SELECTED_COLLECTIONS_FILE}.")
        return
    if not os.path.exists(DATA_DIR):
        try:
            logging.info(f"Data directory {DATA_DIR} does not exist. Attempting to create for saving history.")
            os.makedirs(DATA_DIR, exist_ok=True)
            logging.info(f"Created data directory before saving history: {DATA_DIR}")
        except OSError as e:
            logging.error(f"Could not create data directory {DATA_DIR}: {e}. History saving failed.")
            return
    try:
        with open(SELECTED_COLLECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(selected_collections, f, ensure_ascii=False, indent=4)
            logging.debug(f"Saved history to {SELECTED_COLLECTIONS_FILE}")
    except Exception as e:
        logging.error(f"Error saving history to {SELECTED_COLLECTIONS_FILE}: {e}")

def get_recently_pinned_collections(selected_collections_history, config):
    repeat_block_hours = config.get('repeat_block_hours', 12)
    if not isinstance(repeat_block_hours, (int, float)) or repeat_block_hours < 0:
        logging.warning(f"Invalid 'repeat_block_hours' ({repeat_block_hours}), defaulting 12.");
        repeat_block_hours = 12
    if repeat_block_hours == 0:
        logging.info("Repeat block hours set to 0. Recency check disabled for non-special collections.")
        return set()
    cutoff_time = datetime.now() - timedelta(hours=repeat_block_hours)
    recent_titles = set()
    timestamps_to_keep = {}
    logging.info(f"Checking history since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} for recently pinned non-special items (Repeat block: {repeat_block_hours} hours)")
    history_items_copy = list(selected_collections_history.items())
    for timestamp_str, titles in history_items_copy:
        if not isinstance(titles, list):
             logging.warning(f"Cleaning invalid history entry (value not a list): {timestamp_str}")
             selected_collections_history.pop(timestamp_str, None)
             continue
        try:
            try: timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError: timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            if timestamp >= cutoff_time:
                valid_titles = {t for t in titles if isinstance(t, str)}
                recent_titles.update(valid_titles)
                timestamps_to_keep[timestamp_str] = titles
        except ValueError:
             logging.warning(f"Cleaning invalid date format in history: '{timestamp_str}'. Entry removed.")
             selected_collections_history.pop(timestamp_str, None)
        except Exception as e:
             logging.error(f"Cleaning problematic history entry '{timestamp_str}': {e}. Entry removed.")
             selected_collections_history.pop(timestamp_str, None)
    keys_in_history = set(selected_collections_history.keys())
    keys_to_remove = keys_in_history - set(timestamps_to_keep.keys())
    removed_count = 0
    if keys_to_remove:
        for key in keys_to_remove:
            selected_collections_history.pop(key, None)
            removed_count += 1
        logging.info(f"Removed {removed_count} old entries from history file (in memory).")
    if recent_titles:
        logging.info(f"Recently pinned non-special collections (excluded due to {repeat_block_hours}h block): {sorted(list(recent_titles))}")
    else:
        logging.info("No recently pinned non-special collections found within the repeat block window.")
    return recent_titles

def is_regex_excluded(title, patterns):
    if not patterns or not isinstance(patterns, list): return False
    for pattern_str in patterns:
        if not isinstance(pattern_str, str) or not pattern_str: continue
        try:
            if re.search(pattern_str, title, re.IGNORECASE):
                logging.info(f"Excluding '{title}' based on regex pattern: '{pattern_str}'")
                return True
        except re.error as e:
            logging.error(f"Invalid regex pattern '{pattern_str}' in config: {e}. Skipping this pattern.")
            continue
        except Exception as e:
            logging.error(f"Unexpected error during regex check for title '{title}', pattern '{pattern_str}': {e}")
            return False
    return False

def load_config():
    global _DRY_RUN_MODE_ACTIVE
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            logging.info(f"Config directory created: {CONFIG_DIR}")
            logging.critical(f"CRITICAL{' (DRY RUN)' if _DRY_RUN_MODE_ACTIVE else ''}: Config directory was missing and created. Config file '{CONFIG_PATH}' not found. Please create it and restart. Exiting.")
            sys.exit(1)
        except OSError as e:
             logging.critical(f"CRITICAL{' (DRY RUN)' if _DRY_RUN_MODE_ACTIVE else ''}: Error creating config directory '{CONFIG_DIR}': {e}. Exiting.")
             sys.exit(1)
    if not os.path.exists(CONFIG_PATH):
        logging.critical(f"CRITICAL{' (DRY RUN)' if _DRY_RUN_MODE_ACTIVE else ''}: Config file not found at {CONFIG_PATH}. Please create it and restart. Exiting.")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        validate(instance=config_data, schema=CONFIG_SCHEMA)
        logging.info("Configuration successfully validated against schema.")
        for prop, definition in CONFIG_SCHEMA.get("properties", {}).items():
            if "default" in definition and prop not in config_data:
                config_data[prop] = definition["default"]
                logging.debug(f"Applied schema default for '{prop}': {definition['default']}")
        config_data.setdefault('library_names', [])
        config_data.setdefault('number_of_collections_to_pin', {})
        config_data.setdefault('categories', {})
        config_data.setdefault('exclusion_list', [])
        config_data.setdefault('regex_exclusion_patterns', [])
        config_data.setdefault('special_collections', [])
        if not isinstance(config_data.get('library_names'), list):
            logging.warning("Config 'library_names' is not a list after load/defaults. Resetting to empty list.")
            config_data['library_names'] = []
        if not isinstance(config_data.get('categories'), dict):
            logging.warning("Config 'categories' is not a dict after load/defaults. Resetting to empty dict.")
            config_data['categories'] = {}
        skip_perc = config_data.get('random_category_skip_percent')
        if not (isinstance(skip_perc, int) and 0 <= skip_perc <= 100):
            logging.warning(f"Invalid 'random_category_skip_percent' ({skip_perc}) post-load. Clamping.")
            clamped_perc = 70
            try: clamped_perc = max(0, min(100, int(skip_perc)))
            except (ValueError, TypeError): pass
            config_data['random_category_skip_percent'] = clamped_perc
        logging.info("Configuration loaded, validated, and defaults applied.")
        return config_data
    except json.JSONDecodeError as e:
        logging.critical(f"CRITICAL{' (DRY RUN)' if _DRY_RUN_MODE_ACTIVE else ''}: Error decoding JSON from {CONFIG_PATH}: {e}. Exiting.")
        sys.exit(1)
    except jsonschema_exceptions.ValidationError as e:
        error_path = "->".join(map(str, e.path)) if e.path else "root"
        logging.critical(f"CRITICAL{' (DRY RUN)' if _DRY_RUN_MODE_ACTIVE else ''}: Configuration validation error in {CONFIG_PATH}: {e.message} (at {error_path}). Exiting.")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"CRITICAL{' (DRY RUN)' if _DRY_RUN_MODE_ACTIVE else ''}: An unexpected error occurred while loading config {CONFIG_PATH}: {e}. Exiting.", exc_info=True)
        sys.exit(1)

def connect_to_plex(config):
    plex_url, token = config.get('plex_url'), config.get('plex_token')
    if not plex_url or not token:
        logging.error("Plex URL/Token missing in config."); return None
    try:
        logging.info(f"Connecting to Plex: {plex_url}...");
        plex = PlexServer(plex_url, token, timeout=90)
        server_name = plex.friendlyName
        logging.info(f"Connected to Plex server '{server_name}'.");
        return plex
    except Unauthorized: logging.error("Plex connect failed: Unauthorized (Invalid Token)."); update_status("Error: Plex Unauthorized")
    except requests.exceptions.ConnectionError as e: logging.error(f"Plex connect failed: Could not connect to {plex_url}. Error: {e}"); update_status("Error: Plex Connection Failed")
    except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout): logging.error(f"Plex connect timeout to {plex_url}."); update_status("Error: Plex Connection Timeout")
    except Exception as e: logging.error(f"Plex connect failed: An unexpected error occurred: {e}", exc_info=True); update_status(f"Error: Plex Unexpected ({type(e).__name__})")
    return None

def get_collections_from_library(plex, lib_name):
    if not plex or not lib_name or not isinstance(lib_name, str): return []
    try:
        logging.info(f"Accessing lib: '{lib_name}'"); lib = plex.library.section(lib_name)
        logging.info(f"Fetching collections from '{lib_name}'..."); colls = lib.collections()
        logging.info(f"Found {len(colls)} collections in '{lib_name}'."); return colls
    except NotFound: logging.error(f"Library '{lib_name}' not found.")
    except Exception as e: logging.error(f"Error fetching collections from library '{lib_name}': {e}", exc_info=True)
    return []

def pin_collections(colls_to_pin, config, plex, library_name):
    # ... (This function remains the same as your latest working version that returns detailed list) ...
    global _DRY_RUN_MODE_ACTIVE
    if not colls_to_pin: return []
    webhook_url = config.get('discord_webhook_url')
    label_to_add = config.get('collexions_label')
    pinned_item_details = []
    dry_run_prefix = "[DRY-RUN] " if _DRY_RUN_MODE_ACTIVE else ""
    logging.info(f"{dry_run_prefix}--- Attempting to Pin {len(colls_to_pin)} Collections (for library '{library_name}') ---")
    for c in colls_to_pin:
        if not hasattr(c, 'title') or not hasattr(c, 'key'):
            logging.warning(f"{dry_run_prefix}Skipping invalid collection object: {c}"); continue
        coll_title = c.title
        item_count_str = "?"
        try:
            item_count = c.childCount
            item_count_str = f"{item_count} Item{'s' if item_count != 1 else ''}"
        except Exception:
            logging.debug(f"{dry_run_prefix}Could not retrieve item count for '{coll_title}'.")
        current_item_details = {"title": coll_title, "items": item_count_str, "library": library_name}
        try:
            if _DRY_RUN_MODE_ACTIVE:
                logging.info(f"DRY-RUN: Would pin collection '{coll_title}'.")
                discord_message = f"DRY-RUN: 📍 Collection '**{coll_title}**' ({item_count_str}) from **{library_name}** would be pinned."
            else:
                hub = c.visibility()
                hub.promoteHome()
                hub.promoteShared()
                logging.info(f"Pinned '{coll_title}' successfully.")
                discord_message = f"📍 Collection '**{coll_title}**' ({item_count_str}) from **{library_name}** pinned successfully."
            pinned_item_details.append(current_item_details)
            if webhook_url:
                send_discord_message(webhook_url, discord_message)
            if label_to_add:
                if _DRY_RUN_MODE_ACTIVE:
                    logging.info(f"DRY-RUN: Would add label '{label_to_add}' to '{coll_title}'.")
                else:
                    try:
                        logging.info(f"Attempting to add label '{label_to_add}' to '{coll_title}'...")
                        c.addLabel(label_to_add)
                        logging.info(f"Successfully added label '{label_to_add}' to '{coll_title}'.")
                    except Exception as label_error:
                        logging.error(f"Failed to add label '{label_to_add}' to '{coll_title}': {label_error}")
        except NotFound:
            logging.error(f"{dry_run_prefix}Collection '{coll_title}' not found during pin processing. Skipping.")
        except Exception as e:
            logging.error(f"{dry_run_prefix}Unexpected error processing collection '{coll_title}' for pinning: {e}", exc_info=True)
    logging.info(f"{dry_run_prefix}--- Pinning process complete. {'Would have processed' if _DRY_RUN_MODE_ACTIVE else 'Successfully processed'} {len(pinned_item_details)} collections for potential pinning. ---")
    return pinned_item_details

def send_discord_message(webhook_url, message):
    # ... (This function remains the same) ...
    global _DRY_RUN_MODE_ACTIVE
    if _DRY_RUN_MODE_ACTIVE:
        logging.info(f"DRY-RUN: Would send Discord message: '{message[:150]}...'")
        return
    if not webhook_url or not isinstance(webhook_url, str) or not message:
        logging.debug("Discord webhook URL/message empty or invalid. Skipping.")
        return
    if len(message) > 2000:
        message = message[:1997] + "..."
        logging.warning("Discord message truncated to 2000 characters.")
    data = {"content": message}
    logging.info("Sending message to Discord webhook...")
    try:
        response = requests.post(webhook_url, json=data, timeout=15)
        response.raise_for_status()
        logging.info(f"Discord message sent successfully (Status: {response.status_code}).")
    except requests.exceptions.Timeout:
        logging.error("Failed to send Discord message: Request timed out.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Discord message: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending Discord message: {e}")

def unpin_collections(plex, lib_names, config):
    # ... (This function remains the same) ...
    global _DRY_RUN_MODE_ACTIVE
    dry_run_prefix = "[DRY-RUN] " if _DRY_RUN_MODE_ACTIVE else ""
    if not plex:
        logging.error(f"{dry_run_prefix}Unpin skipped: No Plex connection."); return
    label_to_check = config.get('collexions_label')
    if not label_to_check:
        logging.warning(f"{dry_run_prefix}Unpin skipped: 'collexions_label' not defined in config."); return
    exclusion_set = set(config.get('exclusion_list', []))
    logging.info(f"{dry_run_prefix}--- Starting Unpin Check for Libraries: {lib_names} ---")
    logging.info(f"{dry_run_prefix}Looking for collections with label: '{label_to_check}'")
    logging.info(f"{dry_run_prefix}Will skip unpinning if title is in exclusion list: {exclusion_set or 'None'}")
    unpinned_count = 0
    label_removed_count = 0
    skipped_due_to_exclusion = 0
    for library_name in lib_names:
        if not isinstance(library_name, str) or not library_name.strip():
            logging.warning(f"{dry_run_prefix}Skipping invalid or empty library name during unpin: '{library_name}'"); continue
        try:
            logging.info(f"{dry_run_prefix}Checking library '{library_name}' for collections to unpin...")
            library = plex.library.section(library_name)
            collections_in_library = library.collections()
            logging.info(f"{dry_run_prefix}Found {len(collections_in_library)} total collections in '{library_name}'. Checking promotion status and label...")
            processed_this_lib = 0
            for collection in collections_in_library:
                processed_this_lib +=1
                if not hasattr(collection, 'title') or not hasattr(collection, 'key'):
                    logging.warning(f"{dry_run_prefix}Skipping potentially invalid collection object #{processed_this_lib} in '{library_name}'"); continue
                coll_title = collection.title
                try:
                    hub = collection.visibility()
                    if hub and hasattr(hub, '_promoted') and hub._promoted:
                        logging.debug(f"{dry_run_prefix}Collection '{coll_title}' is currently promoted. Checking label and exclusion...")
                        current_labels = [l.tag.lower() for l in collection.labels] if hasattr(collection, 'labels') else []
                        if label_to_check.lower() in current_labels:
                            logging.debug(f"{dry_run_prefix}Collection '{coll_title}' has the label '{label_to_check}'.")
                            if coll_title in exclusion_set:
                                logging.info(f"{dry_run_prefix}Skipping unpin for '{coll_title}' (explicitly excluded).")
                                skipped_due_to_exclusion += 1
                                continue
                            logging.info(f"{dry_run_prefix}Attempting to unpin and remove label from '{coll_title}'...")
                            if _DRY_RUN_MODE_ACTIVE:
                                logging.info(f"DRY-RUN: Would remove label '{label_to_check}' from '{coll_title}'.")
                            else:
                                try: collection.removeLabel(label_to_check); logging.info(f"Removed label '{label_to_check}' from '{coll_title}'.")
                                except Exception as e_label: logging.error(f"Failed to remove label '{label_to_check}' from '{coll_title}': {e_label}")
                            label_removed_count += 1
                            if _DRY_RUN_MODE_ACTIVE:
                                logging.info(f"DRY-RUN: Would unpin '{coll_title}'.")
                            else:
                                try: hub.demoteHome(); hub.demoteShared(); logging.info(f"Unpinned '{coll_title}' successfully.")
                                except Exception as e_demote: logging.error(f"Failed to demote/unpin '{coll_title}': {e_demote}")
                            unpinned_count += 1
                        else:
                            logging.debug(f"{dry_run_prefix}Collection '{coll_title}' is promoted but does not have label. Skipping.")
                except NotFound: logging.warning(f"{dry_run_prefix}Collection '{coll_title}' not found during visibility check (deleted?). Skipping.")
                except AttributeError as ae:
                    if '_promoted' in str(ae).lower(): logging.error(f"{dry_run_prefix}Error checking promotion for '{coll_title}': `_promoted` attribute not found on hub. Hub: {hub}")
                    else: logging.error(f"{dry_run_prefix}AttributeError checking visibility/processing '{coll_title}' for unpin: {ae}", exc_info=True)
                except Exception as vis_error: logging.error(f"{dry_run_prefix}Error checking visibility/processing '{coll_title}' for unpin: {vis_error}", exc_info=True)
            logging.info(f"{dry_run_prefix}Finished checking {processed_this_lib} collections in '{library_name}'.")
        except NotFound: logging.error(f"{dry_run_prefix}Library '{library_name}' not found during unpin check.")
        except Exception as e: logging.error(f"{dry_run_prefix}General error during unpin process for library '{library_name}': {e}", exc_info=True)
    logging.info(f"{dry_run_prefix}--- Unpinning Check Complete ---")
    logging.info(f"{dry_run_prefix}{'Would have unpinned' if _DRY_RUN_MODE_ACTIVE else 'Unpinned'}: {unpinned_count} collections.")
    logging.info(f"{dry_run_prefix}{'Would have removed label from' if _DRY_RUN_MODE_ACTIVE else 'Removed label from'}: {label_removed_count} collections.")
    if skipped_due_to_exclusion > 0: logging.info(f"{dry_run_prefix}Skipped unpinning for {skipped_due_to_exclusion} collections due to exclusion list.")

def get_active_special_collections(config):
    # ... (This function remains the same) ...
    current_date = datetime.now().date()
    active_titles = []
    special_configs = config.get('special_collections', [])
    if not isinstance(special_configs, list):
        logging.warning("Config 'special_collections' is not a list. No special collections will be processed.")
        return []
    logging.info(f"--- Checking {len(special_configs)} Special Collection Periods for today ({current_date.strftime('%Y-%m-%d')}) ---")
    for i, special in enumerate(special_configs):
        if not isinstance(special, dict) or not all(k in special for k in ['start_date', 'end_date', 'collection_names']):
             logging.warning(f"Skipping invalid special collection entry #{i+1} (missing keys/not dict): {special}")
             continue
        s_date_str = special.get('start_date')
        e_date_str = special.get('end_date')
        names = special.get('collection_names')
        if not (isinstance(s_date_str, str) and isinstance(e_date_str, str) and isinstance(names, list) and all(isinstance(n, str) and n.strip() for n in names)):
             logging.warning(f"Skipping invalid special collection entry #{i+1} (incorrect data types or empty names): {special}")
             continue
        try:
            start_month_day = datetime.strptime(s_date_str, '%m-%d')
            end_month_day = datetime.strptime(e_date_str, '%m-%d')
            start_date = start_month_day.replace(year=current_date.year).date()
            end_date = end_month_day.replace(year=current_date.year).date()
            is_active_period = (start_date <= current_date <= end_date) if start_date <= end_date else (current_date >= start_date or current_date <= end_date)
            if is_active_period:
                active_titles.extend(n for n in names if n)
                logging.info(f"Special period for collections '{names}' is ACTIVE today ({start_date.strftime('%m-%d')} to {end_date.strftime('%m-%d')}).")
        except ValueError:
            logging.error(f"Invalid date format in special collection entry #{i+1}. Dates must be MM-DD. Entry: {special}")
        except Exception as e:
            logging.error(f"Error processing special collection entry #{i+1} ('{names}'): {e}", exc_info=True)
    unique_active = sorted(list(set(active_titles)))
    logging.info(f"--- Special Collection Check Complete ---")
    logging.info(f"Total unique ACTIVE special collection titles for today: {unique_active if unique_active else 'None'}")
    return unique_active

def get_all_special_collection_names(config):
    # ... (This function remains the same) ...
    all_special_titles = set()
    special_configs = config.get('special_collections', [])
    for special in special_configs:
         if isinstance(special, dict) and 'collection_names' in special and isinstance(special['collection_names'], list):
             valid_names = {name.strip() for name in special['collection_names'] if isinstance(name, str) and name.strip()}
             all_special_titles.update(valid_names)
    return all_special_titles

def get_fully_excluded_collections(config, active_special_collections):
    # ... (This function remains the same) ...
    exclusion_raw = config.get('exclusion_list', [])
    explicit_exclusion_set = {name.strip() for name in exclusion_raw if isinstance(name, str) and name.strip()}
    logging.info(f"Explicit title exclusions from config: {explicit_exclusion_set or 'None'}")
    all_special_titles = get_all_special_collection_names(config)
    active_special_set = set(active_special_collections)
    inactive_special_set = all_special_titles - active_special_set
    if inactive_special_set:
        logging.info(f"Inactive special collections (also excluded from random/category selection): {inactive_special_set}")
    else:
         logging.info("No inactive special collections identified for additional exclusion.")
    combined_exclusion_set = explicit_exclusion_set.union(inactive_special_set)
    logging.info(f"Total combined title exclusions (explicit + inactive special): {combined_exclusion_set or 'None'}")
    return combined_exclusion_set

# --- MODIFIED fill_with_random_collections with more logging ---
def fill_with_random_collections(random_collections_pool, remaining_slots):
    logging.debug(f"Entering fill_with_random_collections. Slots: {remaining_slots}, Pool size: {len(random_collections_pool) if random_collections_pool else 0}")
    collections_to_pin = []
    if remaining_slots <= 0:
        logging.debug("No remaining slots for random selection. Exiting fill_with_random_collections.")
        return collections_to_pin
    if not random_collections_pool:
        logging.info("No eligible collections left in the pool for random selection. Exiting fill_with_random_collections.")
        return collections_to_pin

    try:
        logging.debug(f"Type of random_collections_pool: {type(random_collections_pool)}")
        # Ensure it's a list of actual Plex collection objects, not just titles
        if random_collections_pool and not hasattr(random_collections_pool[0], 'title'):
            logging.error("random_collections_pool does not appear to contain Plex objects. Cannot select.")
            return []

        available = list(random_collections_pool) # Make a copy to shuffle
        logging.debug(f"Created 'available' list from pool. Size: {len(available)}")
        
        random.shuffle(available)
        logging.debug("'available' list shuffled.")
        
        num_to_select = min(remaining_slots, len(available))
        logging.info(f"Attempting to select {num_to_select} random collection(s) from {len(available)} available items.")
        
        if num_to_select > 0:
            selected_random = available[:num_to_select]
            collections_to_pin.extend(selected_random)
            selected_titles = [getattr(c, 'title', 'Untitled') for c in selected_random]
            logging.info(f"Added {len(selected_titles)} random collection(s): {selected_titles}")
        else:
            logging.info("No random collections were selected (num_to_select was 0).")
            
    except Exception as e:
        logging.error(f"Error during fill_with_random_collections: {e}", exc_info=True)
        return [] # Return empty list on error to prevent further issues

    logging.debug(f"Exiting fill_with_random_collections. Returning {len(collections_to_pin)} items.")
    return collections_to_pin
# --- END MODIFIED fill_with_random_collections ---

def filter_collections(config, all_collections_in_library, active_special_titles, library_pin_limit, library_name, selected_collections_history):
    # ... (This function remains the same as your latest working version) ...
    logging.info(f">>> Current filter_collections for LIBRARY: '{library_name}' <<<")
    min_items = config.get('min_items_for_pinning', 10)
    titles_excluded = get_fully_excluded_collections(config, active_special_titles)
    recent_pins = get_recently_pinned_collections(selected_collections_history, config)
    regex_patterns = config.get('regex_exclusion_patterns', [])
    use_random_category_mode = config.get('use_random_category_mode', False)
    skip_perc = config.get('random_category_skip_percent', 70)
    try:
        raw_categories_for_library = config.get('categories', {}).get(library_name, [])
        library_categories_config = copy.deepcopy(raw_categories_for_library)
    except Exception as e:
        logging.error(f"Error deepcopying categories for '{library_name}': {e}. Proceeding with empty categories.")
        library_categories_config = []
    logging.info(f"Filtering for '{library_name}': Min Items={min_items}, Random Cat Mode={use_random_category_mode}, Cat Skip Chance={skip_perc}%")
    eligible_pool = []
    logging.info(f"Processing {len(all_collections_in_library)} collections found in '{library_name}' through initial filters...")
    for c in all_collections_in_library:
        if not hasattr(c, 'title') or not c.title:
            logging.debug(f"Skipping collection with missing title: {c}")
            continue
        title = c.title
        is_special = title in active_special_titles
        if title in titles_excluded:
            logging.debug(f" Excluding '{title}' (Reason: Explicit or Inactive Special Title Exclusion).")
            continue
        if is_regex_excluded(title, regex_patterns):
            continue
        if not is_special and title in recent_pins:
            logging.debug(f" Excluding '{title}' (Reason: Recently pinned non-special item within repeat block).")
            continue
        if not is_special:
            try:
                item_count = c.childCount
                if item_count < min_items:
                    logging.debug(f" Excluding '{title}' (Reason: Low item count: {item_count} < {min_items}).")
                    continue
            except AttributeError:
                logging.warning(f" Excluding '{title}' due to AttributeError when getting item count (childCount).")
                continue
            except Exception as e:
                logging.warning(f" Excluding '{title}' due to error getting item count: {e}")
                continue
        eligible_pool.append(c)
    logging.info(f"Found {len(eligible_pool)} eligible collections in '{library_name}' after initial filtering.")
    if not eligible_pool:
        logging.info(f"No collections eligible for pinning in '{library_name}'. Skipping priority selection.")
        return []
    collections_to_pin = []
    pinned_titles_this_run = set()
    remaining_slots = library_pin_limit
    random.shuffle(eligible_pool)
    logging.info(f"Selection Step 1: Prioritizing Active Special Collection(s) for '{library_name}'.")
    specials_selected_now = []
    pool_after_specials_processing = []
    for c_item in eligible_pool:
        coll_title = c_item.title
        if coll_title in active_special_titles and remaining_slots > 0 and coll_title not in pinned_titles_this_run:
            logging.info(f"  Selecting ACTIVE special collection: '{coll_title}'")
            specials_selected_now.append(c_item)
            pinned_titles_this_run.add(coll_title)
            remaining_slots -= 1
        else:
            pool_after_specials_processing.append(c_item)
    collections_to_pin.extend(specials_selected_now)
    logging.info(f"Selected {len(specials_selected_now)} special collection(s). Remaining slots: {remaining_slots}")
    category_collections_selected_now = []
    pool_for_random_fill = list(pool_after_specials_processing)
    titles_from_served_categories_for_random_exclusion = set()
    if remaining_slots > 0 and library_categories_config:
        logging.info(f"Selection Step 2: Processing Categories for '{library_name}' (Random Mode: {use_random_category_mode}).")
        valid_categories_for_lib = [cat_dict for cat_dict in library_categories_config if isinstance(cat_dict, dict) and cat_dict.get('pin_count', 0) > 0 and cat_dict.get('collections')]
        if not valid_categories_for_lib:
            logging.info(f"  No valid (enabled and with collections) categories found for '{library_name}'.")
        else:
            if use_random_category_mode:
                for cat_conf in valid_categories_for_lib:
                    titles_from_served_categories_for_random_exclusion.update(cat_conf.get('collections', []))
                logging.info(f"  Random Category Mode: {len(titles_from_served_categories_for_random_exclusion)} titles from all defined valid categories in '{library_name}' will be excluded from random fill.")
                if random.random() < (skip_perc / 100.0):
                    logging.info(f"  Category selection SKIPPED for '{library_name}' due to {skip_perc}% chance.")
                else:
                    chosen_category_config = random.choice(valid_categories_for_lib)
                    cat_name = chosen_category_config.get('category_name', 'Unnamed Random Category')
                    cat_pin_count = chosen_category_config.get('pin_count', 0)
                    cat_titles_defined = set(chosen_category_config.get('collections', []))
                    logging.info(f"  Randomly selected category: '{cat_name}' (Target Pins: {cat_pin_count}, Defined Titles: {len(cat_titles_defined)})")
                    eligible_for_this_cat = [item for item in pool_after_specials_processing if item.title in cat_titles_defined and item.title not in pinned_titles_this_run]
                    num_to_pick_from_cat = min(cat_pin_count, len(eligible_for_this_cat), remaining_slots)
                    if num_to_pick_from_cat > 0:
                        random.shuffle(eligible_for_this_cat)
                        picked_for_this_cat = eligible_for_this_cat[:num_to_pick_from_cat]
                        category_collections_selected_now.extend(picked_for_this_cat)
                        for p_item in picked_for_this_cat: 
                            pinned_titles_this_run.add(p_item.title)
                        remaining_slots -= len(picked_for_this_cat)
                        logging.info(f"  Selected {len(picked_for_this_cat)} item(s) from '{cat_name}': {[item.title for item in picked_for_this_cat]}")
            else: 
                category_slots_remaining = {cat.get('category_name'): cat.get('pin_count',0) for cat in valid_categories_for_lib}
                collection_to_category_map = {}
                for cat_conf in valid_categories_for_lib: 
                    cat_name_map = cat_conf.get('category_name')
                    for title_in_cat in cat_conf.get('collections', []): 
                        collection_to_category_map.setdefault(title_in_cat, []).append(cat_name_map)
                temp_pool_after_default_categories = []
                for c_item in pool_after_specials_processing: 
                    item_title = c_item.title
                    picked_this_item_by_cat = False
                    if remaining_slots <= 0: 
                        temp_pool_after_default_categories.append(c_item); continue
                    if item_title in collection_to_category_map and item_title not in pinned_titles_this_run: 
                        for cat_name_item_belongs_to in collection_to_category_map[item_title]: 
                            if category_slots_remaining.get(cat_name_item_belongs_to, 0) > 0: 
                                logging.info(f"  Selecting '{item_title}' for category '{cat_name_item_belongs_to}'.")
                                category_collections_selected_now.append(c_item)
                                pinned_titles_this_run.add(item_title)
                                remaining_slots -= 1
                                category_slots_remaining[cat_name_item_belongs_to] -= 1
                                for cat_conf_detail in valid_categories_for_lib: 
                                    if cat_conf_detail.get('category_name') == cat_name_item_belongs_to: 
                                        titles_from_served_categories_for_random_exclusion.update(cat_conf_detail.get('collections',[]))
                                        break 
                                picked_this_item_by_cat = True 
                                break 
                    if not picked_this_item_by_cat: 
                        temp_pool_after_default_categories.append(c_item)
                pool_for_random_fill = temp_pool_after_default_categories 
            collections_to_pin.extend(category_collections_selected_now) 
            logging.info(f"Selected {len(category_collections_selected_now)} collection(s) from categories. Remaining slots: {remaining_slots}")
    else: 
        logging.info(f"Skipping category selection for '{library_name}' (Slots left: {remaining_slots}, Categories defined: {bool(library_categories_config)}).")
        pool_for_random_fill = list(pool_after_specials_processing)
    final_random_candidates = []
    for item in pool_for_random_fill: 
        if item.title not in pinned_titles_this_run and item.title not in titles_from_served_categories_for_random_exclusion: 
            final_random_candidates.append(item)
    logging.info(f"Pool for random fill (after category exclusions & already pinned items): {len(final_random_candidates)} items. Titles excluded due to category service: {len(titles_from_served_categories_for_random_exclusion)}")
    
    if remaining_slots > 0:
        logging.info(f"Selection Step 3: Filling remaining {remaining_slots} slot(s) randomly for '{library_name}'.")
        random_selected_now = fill_with_random_collections(final_random_candidates, remaining_slots)
        logging.debug(f"Result from fill_with_random_collections: {len(random_selected_now)} items.") # <--- ADDED DEBUG
        collections_to_pin.extend(random_selected_now)
    else:
        logging.info(f"Skipping random selection for '{library_name}' (no remaining slots).")
    
    final_selected_titles = [getattr(c, 'title', 'Untitled') for c in collections_to_pin]
    logging.info(f"--- Filtering and Selection Complete for '{library_name}' ---")
    logging.info(f"Final list of {len(final_selected_titles)} collections selected for pinning: {final_selected_titles if final_selected_titles else 'None'}")
    return collections_to_pin

# --- Main Function ---
# ... (main function remains the same as your latest working version, including saving LAST_PINNED_DETAILS_FILE) ...
def main():
    global _DRY_RUN_MODE_ACTIVE
    run_start_time = datetime.now()
    logging.info(f"====== Starting Collexions Script Run at {run_start_time.strftime('%Y-%m-%d %H:%M:%S')}{' (DRY RUN)' if _DRY_RUN_MODE_ACTIVE else ''} ======")
    try:
        config = load_config()
    except SystemExit:
        update_status("CRITICAL: Config Error")
        return
    pin_interval_minutes = config.get('pinning_interval', 180)
    next_run_calc_time = run_start_time + timedelta(minutes=pin_interval_minutes)
    logging.info(f"Pinning interval set to {pin_interval_minutes} minutes. Next run approximately: {next_run_calc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    update_status("Running", next_run_calc_time.timestamp())
    plex = connect_to_plex(config)
    if not plex:
        logging.critical(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Failed to connect to Plex. Aborting this run.")
        return
    selected_collections_history = load_selected_collections()
    library_names = config.get('library_names', [])
    all_pinned_details_this_run = []
    if not library_names:
        logging.warning(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}No 'library_names' defined in config. Nothing to process for pinning/unpinning.")
    else:
        unpin_collections(plex, library_names, config)
    collections_per_library_config = config.get('number_of_collections_to_pin', {})
    for library_name in library_names:
        if not isinstance(library_name, str) or not library_name.strip():
            logging.warning(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Skipping invalid or empty library name in list."); continue
        pin_limit = collections_per_library_config.get(library_name, 0)
        if not isinstance(pin_limit, int) or pin_limit < 0:
            logging.warning(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Invalid pin limit for '{library_name}' ({pin_limit}). Defaulting to 0.")
            pin_limit = 0
        if pin_limit == 0:
            logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Skipping library '{library_name}' as its pin limit is set to 0.")
            continue
        logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}===== Processing Library: '{library_name}' (Pin Limit: {pin_limit}) =====")
        update_status(f"Processing: {library_name}", next_run_calc_time.timestamp())
        library_process_start_time = time.time()
        all_colls_in_lib = get_collections_from_library(plex, library_name)
        if not all_colls_in_lib:
            logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}No collections found or retrieved from library '{library_name}'. Skipping pinning for this library.")
            continue
        active_specials = get_active_special_collections(config)
        colls_to_pin_for_library_objects = filter_collections(
            config, all_colls_in_lib, active_specials, pin_limit, library_name, selected_collections_history
        )
        if colls_to_pin_for_library_objects:
            pinned_item_details_for_library = pin_collections(colls_to_pin_for_library_objects, config, plex, library_name)
            all_pinned_details_this_run.extend(pinned_item_details_for_library)
        else:
            logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}No collections were selected for pinning in '{library_name}' after filtering.")
        logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Finished processing library '{library_name}' in {time.time() - library_process_start_time:.2f} seconds.")
        logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}===== Completed Library: '{library_name}' =====")
    last_pinned_output = {
        "run_mode": "DRY-RUN" if _DRY_RUN_MODE_ACTIVE else "NORMAL",
        "timestamp": datetime.now().isoformat(),
        "pinned_items": all_pinned_details_this_run
    }
    try:
        logging.debug(f"Attempting to save last pinned details. DATA_DIR: {DATA_DIR}, File: {LAST_PINNED_DETAILS_FILE}")
        if not os.path.exists(DATA_DIR):
            logging.info(f"Data directory {DATA_DIR} does not exist. Attempting to create for last_pinned_details.")
            os.makedirs(DATA_DIR, exist_ok=True)
            logging.info(f"Data directory {DATA_DIR} created (or already existed).")
        with open(LAST_PINNED_DETAILS_FILE, 'w', encoding='utf-8') as f:
            json.dump(last_pinned_output, f, ensure_ascii=False, indent=4)
        logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Saved last pinned details to {LAST_PINNED_DETAILS_FILE} ({len(all_pinned_details_this_run)} items).")
    except Exception as e:
        logging.error(f"Error saving last pinned details to {LAST_PINNED_DETAILS_FILE}: {e}", exc_info=True)
    if all_pinned_details_this_run:
        current_timestamp_iso = datetime.now().isoformat()
        titles_processed_for_pinning = {item['title'] for item in all_pinned_details_this_run}
        all_special_titles_ever = get_all_special_collection_names(config)
        non_special_pins_for_history = sorted(list(titles_processed_for_pinning - all_special_titles_ever))
        if non_special_pins_for_history:
            if not isinstance(selected_collections_history, dict): selected_collections_history = {}
            selected_collections_history[current_timestamp_iso] = non_special_pins_for_history
            save_selected_collections(selected_collections_history)
            logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Updated history file for timestamp {current_timestamp_iso} with {len(non_special_pins_for_history)} non-special pinned items.")
            num_specials_pinned = len(titles_processed_for_pinning) - len(non_special_pins_for_history)
            if num_specials_pinned > 0:
                 logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Note: {num_specials_pinned} special collection(s) were {'processed for pinning' if _DRY_RUN_MODE_ACTIVE else 'pinned'} but not added to recency history tracking.")
        else:
             logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Only special collections (or none) were {'processed' if _DRY_RUN_MODE_ACTIVE else 'successfully pinned'} this cycle. History file not updated for recency blocking.")
    else:
         logging.info(f"{'[DRY-RUN] ' if _DRY_RUN_MODE_ACTIVE else ''}Nothing was {'processed for pinning' if _DRY_RUN_MODE_ACTIVE else 'successfully pinned'} this cycle. History file not updated.")
    run_end_time = datetime.now()
    logging.info(f"====== Collexions Script Run Finished at {run_end_time.strftime('%Y-%m-%d %H:%M:%S')}{' (DRY RUN)' if _DRY_RUN_MODE_ACTIVE else ''} ======")
    logging.info(f"Total run duration: {run_end_time - run_start_time}")

# --- Continuous Loop ---
# ... (run_continuously function remains the same) ...
def run_continuously():
    global _DRY_RUN_MODE_ACTIVE
    while True:
        run_cycle_start_time = datetime.now()
        next_run_ts_planned_for_status = None
        pin_interval_from_config_for_sleep = 180
        try:
            temp_config_for_interval = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, 'r', encoding='utf-8') as f_temp:
                        temp_config_for_interval = json.load(f_temp)
                except Exception as e_cfg_read:
                    logging.warning(f"Could not read config for interval pre-main(): {e_cfg_read}. Using default interval.")
            current_pin_interval = temp_config_for_interval.get('pinning_interval', 180)
            if not isinstance(current_pin_interval, (int, float)) or current_pin_interval <= 0:
                current_pin_interval = 180
            pin_interval_from_config_for_sleep = current_pin_interval
            sleep_seconds_calc = pin_interval_from_config_for_sleep * 60
            next_run_ts_planned_for_status = (run_cycle_start_time + timedelta(seconds=sleep_seconds_calc)).timestamp()
            main()
        except KeyboardInterrupt:
            logging.info(f"Keyboard interrupt received. Exiting Collexions script.{' (DRY RUN was active)' if _DRY_RUN_MODE_ACTIVE else ''}")
            update_status("Stopped (Interrupt)")
            break
        except SystemExit as e:
             logging.critical(f"SystemExit called during run cycle (code: {e.code}). Exiting Collexions script.{' (DRY RUN was active)' if _DRY_RUN_MODE_ACTIVE else ''}")
             break
        except Exception as e:
            logging.critical(f"CRITICAL UNHANDLED EXCEPTION in run_continuously loop: {e}", exc_info=True)
            update_status(f"CRASHED ({type(e).__name__})")
            pin_interval_from_config_for_sleep = 1
            logging.error(f"Sleeping for {pin_interval_from_config_for_sleep*60} seconds before next attempt after crash.")
            next_run_ts_planned_for_status = (datetime.now() + timedelta(seconds=pin_interval_from_config_for_sleep*60)).timestamp()
        seconds_to_next_ideal_start = 0
        if next_run_ts_planned_for_status:
            seconds_to_next_ideal_start = next_run_ts_planned_for_status - datetime.now().timestamp()
        else:
            seconds_to_next_ideal_start = pin_interval_from_config_for_sleep * 60
        actual_sleep_duration = max(1, seconds_to_next_ideal_start)
        update_status(f"Sleeping ({pin_interval_from_config_for_sleep:.0f} min)", next_run_ts_planned_for_status)
        if next_run_ts_planned_for_status:
             logging.info(f"Next run scheduled around: {datetime.fromtimestamp(next_run_ts_planned_for_status).strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"Sleeping for approximately {actual_sleep_duration:.0f} seconds...")
        try:
            time.sleep(actual_sleep_duration)
        except KeyboardInterrupt:
             logging.info(f"Keyboard interrupt received during sleep. Exiting Collexions script.{' (DRY RUN was active)' if _DRY_RUN_MODE_ACTIVE else ''}")
             update_status("Stopped (Interrupt during sleep)")
             break

# --- Script Entry Point ---
# ... (__main__ entry point remains the same) ...
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ColleXions Background Script")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Run the script in dry-run mode: no changes will be made."
    )
    args = parser.parse_args()
    _DRY_RUN_MODE_ACTIVE = args.dry_run
    update_status("Initializing")
    if _DRY_RUN_MODE_ACTIVE:
        logging.info(">>>>>>>>>> COLLECTIONS SCRIPT IS STARTING IN DRY-RUN MODE <<<<<<<<<<")
    else:
        logging.info("Collexions script starting up in LIVE mode...")
    try:
        run_continuously()
    except SystemExit:
         logging.info(f"Exiting due to SystemExit during script execution.{' (DRY RUN was active)' if _DRY_RUN_MODE_ACTIVE else ''}")
    except KeyboardInterrupt:
         logging.info(f"Exiting due to KeyboardInterrupt during script execution.{' (DRY RUN was active)' if _DRY_RUN_MODE_ACTIVE else ''}")
    except Exception as e:
        logging.critical(f"FATAL UNHANDLED ERROR AT SCRIPT LEVEL: {e}", exc_info=True)
        update_status("FATAL ERROR")
        sys.exit(1)
