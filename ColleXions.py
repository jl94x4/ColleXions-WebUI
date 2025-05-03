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
APP_DIR = '/app'
CONFIG_DIR = os.path.join(APP_DIR, 'config')
LOG_DIR = os.path.join(APP_DIR, 'logs')
DATA_DIR = os.path.join(APP_DIR, 'data')

CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
LOG_FILE = os.path.join(LOG_DIR, 'collexions.log')
SELECTED_COLLECTIONS_FILE = os.path.join(DATA_DIR, 'selected_collections.json')
STATUS_FILE = os.path.join(DATA_DIR, 'status.json')

# --- Setup Logging ---
# Ensure log directory exists before setting up handlers
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
        # Use print here because logging might not be fully configured yet
        print(f"INFO: Log directory created at {LOG_DIR}")
    except OSError as e:
        sys.stderr.write(f"CRITICAL: Error creating log directory '{LOG_DIR}': {e}. Exiting.\n")
        sys.exit(1) # Exit if log dir cannot be created

log_handlers = [logging.StreamHandler(sys.stdout)]
# Setup file handler only if LOG_DIR exists
try:
    # Use 'a' to append to the log file, more useful for docker logs
    log_handlers.append(logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'))
except Exception as e:
    sys.stderr.write(f"Warning: Error setting up file log handler for '{LOG_FILE}': {e}\n")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=log_handlers
)
# Quieten overly verbose libraries
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# --- Status Update Function ---
def update_status(status_message="Running", next_run_timestamp=None):
    """Updates the status JSON file."""
    # Ensure data directory exists before writing status
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True) # Use exist_ok=True
            logging.info(f"Created data directory: {DATA_DIR}")
        except OSError as e:
            logging.error(f"Could not create data directory {DATA_DIR}: {e}. Status update might fail.")
            # Continue attempt anyway

    status_data = {"status": status_message, "last_update": datetime.now().isoformat()}
    if next_run_timestamp:
        # Ensure timestamp is serializable (float or int)
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

def load_selected_collections():
    """Loads the history of previously pinned collections."""
    # Ensure data directory exists before reading history
    if not os.path.exists(DATA_DIR):
        logging.warning(f"Data directory {DATA_DIR} not found when loading history. Assuming no history.")
        return {}

    if os.path.exists(SELECTED_COLLECTIONS_FILE):
        try:
            # Check if file is empty before trying to load JSON
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
    """Saves the updated history of pinned collections."""
    # Ensure data directory exists before saving history
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            logging.info(f"Created data directory before saving history: {DATA_DIR}")
        except OSError as e:
            logging.error(f"Could not create data directory {DATA_DIR}: {e}. History saving failed.")
            return # Don't try to save if dir creation failed

    try:
        with open(SELECTED_COLLECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(selected_collections, f, ensure_ascii=False, indent=4)
            logging.debug(f"Saved history to {SELECTED_COLLECTIONS_FILE}")
    except Exception as e:
        logging.error(f"Error saving history to {SELECTED_COLLECTIONS_FILE}: {e}")

def get_recently_pinned_collections(selected_collections, config):
    """Gets titles of non-special collections pinned within the repeat_block_hours window."""
    repeat_block_hours = config.get('repeat_block_hours', 12)
    # Validate repeat_block_hours
    if not isinstance(repeat_block_hours, (int, float)) or repeat_block_hours < 0: # Allow 0
        logging.warning(f"Invalid 'repeat_block_hours' ({repeat_block_hours}), defaulting 12.");
        repeat_block_hours = 12

    if repeat_block_hours == 0:
        logging.info("Repeat block hours set to 0. Recency check disabled.")
        return set() # Return empty set if blocking is disabled

    cutoff_time = datetime.now() - timedelta(hours=repeat_block_hours)
    recent_titles = set()
    timestamps_to_keep = {}
    logging.info(f"Checking history since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} for recently pinned non-special items (Repeat block: {repeat_block_hours} hours)")

    history_items = list(selected_collections.items()) # Create a copy to iterate over

    for timestamp_str, titles in history_items:
        # Basic validation of history entry structure
        if not isinstance(titles, list):
             logging.warning(f"Cleaning invalid history entry (value not a list): {timestamp_str}")
             selected_collections.pop(timestamp_str, None) # Remove invalid entry from original dict
             continue
        try:
            # Attempt to parse timestamp (support ISO format primarily now)
            try: timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError: timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S') # Fallback

            # Compare with cutoff time
            if timestamp >= cutoff_time:
                valid_titles = {t for t in titles if isinstance(t, str)} # Ensure titles are strings
                recent_titles.update(valid_titles)
                timestamps_to_keep[timestamp_str] = titles # Keep this entry
            # else: Old entry, will be removed implicitly below

        except ValueError:
             logging.warning(f"Cleaning invalid date format in history: '{timestamp_str}'. Entry removed.")
             selected_collections.pop(timestamp_str, None)
        except Exception as e:
             logging.error(f"Cleaning problematic history entry '{timestamp_str}': {e}. Entry removed.")
             selected_collections.pop(timestamp_str, None)

    # Efficiently remove old keys by checking against kept keys
    keys_to_remove = set(selected_collections.keys()) - set(timestamps_to_keep.keys())
    removed_count = 0
    if keys_to_remove:
        for key in keys_to_remove:
            selected_collections.pop(key, None)
            removed_count += 1
        logging.info(f"Removed {removed_count} old entries from history file.")
        save_selected_collections(selected_collections) # Save immediately after cleanup

    if recent_titles:
        logging.info(f"Recently pinned non-special collections (excluded due to {repeat_block_hours}h block): {sorted(list(recent_titles))}")
    else:
        logging.info("No recently pinned non-special collections found within the repeat block window.")

    return recent_titles


def is_regex_excluded(title, patterns):
    """Checks if a title matches any regex pattern."""
    if not patterns or not isinstance(patterns, list): return False
    for pattern_str in patterns:
        if not isinstance(pattern_str, str) or not pattern_str: continue # Skip empty/invalid patterns
        try:
            if re.search(pattern_str, title, re.IGNORECASE):
                logging.info(f"Excluding '{title}' based on regex pattern: '{pattern_str}'")
                return True
        except re.error as e:
            logging.error(f"Invalid regex pattern '{pattern_str}' in config: {e}. Skipping this pattern.")
            continue # Skip invalid pattern
        except Exception as e:
            logging.error(f"Unexpected error during regex check for title '{title}', pattern '{pattern_str}': {e}")
            return False # Fail safe on unexpected error
    return False


def load_config():
    """Loads configuration from config.json, exits on critical errors."""
    # Ensure config directory exists
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            logging.info(f"Created config directory: {CONFIG_DIR}")
            # If dir was just created, config cannot exist yet
            logging.critical(f"CRITICAL: Config directory created, but config file '{CONFIG_PATH}' not found. Please create it (e.g., using Web UI) and restart. Exiting.")
            sys.exit(1)
        except OSError as e:
             logging.critical(f"CRITICAL: Error creating config directory '{CONFIG_DIR}': {e}. Exiting.")
             sys.exit(1)

    if not os.path.exists(CONFIG_PATH):
        logging.critical(f"CRITICAL: Config file not found at {CONFIG_PATH}. Please create it (e.g., using Web UI) and restart. Exiting.")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            raise ValueError("Config file content is not a valid JSON object.")

        # --- Validate essential keys & set defaults ---
        if not cfg.get('plex_url') or not cfg.get('plex_token'):
             raise ValueError("Missing required configuration: 'plex_url' and 'plex_token' must be set.")

        cfg.setdefault('use_random_category_mode', False)
        cfg.setdefault('random_category_skip_percent', 70)
        cfg.setdefault('collexions_label', 'Collexions')
        cfg.setdefault('pinning_interval', 180)
        cfg.setdefault('repeat_block_hours', 12)
        cfg.setdefault('min_items_for_pinning', 10)
        cfg.setdefault('discord_webhook_url', '')
        cfg.setdefault('exclusion_list', [])
        cfg.setdefault('regex_exclusion_patterns', [])
        cfg.setdefault('special_collections', [])
        cfg.setdefault('library_names', [])
        cfg.setdefault('number_of_collections_to_pin', {})
        cfg.setdefault('categories', {})

        # --- Validate types for potentially problematic keys ---
        if not isinstance(cfg.get('library_names'), list): cfg['library_names'] = []
        if not isinstance(cfg.get('categories'), dict): cfg['categories'] = {}
        if not isinstance(cfg.get('number_of_collections_to_pin'), dict): cfg['number_of_collections_to_pin'] = {}
        if not isinstance(cfg.get('exclusion_list'), list): cfg['exclusion_list'] = []
        if not isinstance(cfg.get('regex_exclusion_patterns'), list): cfg['regex_exclusion_patterns'] = []
        if not isinstance(cfg.get('special_collections'), list): cfg['special_collections'] = []

        # Validate skip percentage range after loading/setting default
        skip_perc = cfg.get('random_category_skip_percent') # Already has default from setdefault
        if not (isinstance(skip_perc, int) and 0 <= skip_perc <= 100):
            logging.warning(f"Invalid 'random_category_skip_percent' ({skip_perc}). Clamping to 0-100.")
            # Attempt conversion if possible, otherwise default
            try: clamped_perc = max(0, min(100, int(skip_perc)))
            except (ValueError, TypeError): clamped_perc = 70
            cfg['random_category_skip_percent'] = clamped_perc

        logging.info("Configuration loaded and validated.")
        return cfg

    except json.JSONDecodeError as e:
        logging.critical(f"CRITICAL: Error decoding JSON from {CONFIG_PATH}: {e}. Exiting.")
        sys.exit(1)
    except ValueError as e:
         logging.critical(f"CRITICAL: Invalid or missing configuration in {CONFIG_PATH}: {e}. Exiting.")
         sys.exit(1)
    except Exception as e:
        logging.critical(f"CRITICAL: An unexpected error occurred while loading config {CONFIG_PATH}: {e}. Exiting.", exc_info=True)
        sys.exit(1)


def connect_to_plex(config):
    """Connects to Plex server, returns PlexServer object or None."""
    plex_url, token = config.get('plex_url'), config.get('plex_token')
    if not plex_url or not token:
        logging.error("Plex URL/Token missing in config."); return None
    try:
        logging.info(f"Connecting to Plex: {plex_url}...");
        plex = PlexServer(plex_url, token, timeout=90)
        server_name = plex.friendlyName # Test connection
        logging.info(f"Connected to Plex server '{server_name}'.");
        return plex
    except Unauthorized: logging.error("Plex connect failed: Unauthorized."); update_status("Error: Plex Unauthorized")
    except requests.exceptions.ConnectionError as e: logging.error(f"Plex connect failed: {e}"); update_status("Error: Plex Connection Failed")
    except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout): logging.error(f"Plex connect timeout: {plex_url}."); update_status("Error: Plex Connection Timeout")
    except Exception as e: logging.error(f"Plex connect failed: {e}", exc_info=True); update_status(f"Error: Plex Unexpected ({type(e).__name__})")
    return None


def get_collections_from_library(plex, lib_name):
    """Fetches all collection objects from a single specified library name."""
    if not plex or not lib_name or not isinstance(lib_name, str): return []
    try:
        logging.info(f"Accessing lib: '{lib_name}'"); lib = plex.library.section(lib_name)
        logging.info(f"Fetching collections from '{lib_name}'..."); colls = lib.collections()
        logging.info(f"Found {len(colls)} collections in '{lib_name}'."); return colls
    except NotFound: logging.error(f"Library '{lib_name}' not found.")
    except Exception as e: logging.error(f"Error fetching collections from '{lib_name}': {e}", exc_info=True)
    return []


def pin_collections(colls_to_pin, config, plex):
    """Pins the provided list of collections, adds label, and sends Discord notifications."""
    if not colls_to_pin: return []
    webhook, label = config.get('discord_webhook_url'), config.get('collexions_label')
    pinned_titles = []
    logging.info(f"--- Attempting to Pin {len(colls_to_pin)} Collections ---")
    for c in colls_to_pin:
        if not hasattr(c, 'title') or not hasattr(c, 'key'): logging.warning(f"Skipping invalid collection: {c}"); continue
        title = c.title; items = "?"
        try:
            # Get item count safely
            try: items = f"{c.childCount} Item{'s' if c.childCount != 1 else ''}"
            except Exception: pass # Ignore count error if needed

            logging.info(f"Pinning: '{title}' ({items})")
            # Perform pin action
            try:
                 hub = c.visibility(); hub.promoteHome(); hub.promoteShared()
                 pinned_titles.append(title); logging.info(f" Pinned '{title}' successfully.")
                 if webhook: send_discord_message(webhook, f"📌 Collection '**{title}**' with **{items}** pinned.")
            except Exception as pe: logging.error(f" Pin failed '{title}': {pe}"); continue # Skip label if pin fails

            # Add label if configured and pin succeeded
            if label:
                try: c.addLabel(label); logging.info(f" Added label '{label}' to '{title}'.")
                except Exception as le: logging.error(f" Label add failed '{title}': {le}")

        except NotFound: logging.error(f"Collection '{title}' not found during pin process.")
        except Exception as e: logging.error(f"Error processing '{title}' for pinning: {e}", exc_info=True)

    logging.info(f"--- Pinning done. Successfully pinned {len(pinned_titles)}. ---"); return pinned_titles


def send_discord_message(webhook_url, message):
    """Sends a message to the specified Discord webhook URL."""
    if not webhook_url or not message: return
    if len(message) > 2000: message = message[:1997]+"..."
    data = {"content": message}; logging.info("Sending Discord message...")
    try:
        resp = requests.post(webhook_url, json=data, timeout=15); resp.raise_for_status()
        logging.info("Discord msg sent.")
    except Exception as e: logging.error(f"Discord send failed: {e}")


def unpin_collections(plex, lib_names, config):
    """Unpins currently promoted collections managed by this script (matching label)."""
    if not plex: logging.error("Unpin skipped: No Plex connection."); return
    label = config.get('collexions_label');
    if not label: logging.warning("Unpin skipped: 'collexions_label' missing."); return
    excludes = set(config.get('exclusion_list', []))
    logging.info(f"--- Starting Unpin Check (Label: '{label}', Exclusions: {excludes or 'None'}) ---")
    unpinned=0; labels_rem=0; skipped=0

    for lib_name in lib_names:
        if not isinstance(lib_name, str): logging.warning(f"Skipping invalid library name: {lib_name}"); continue
        try:
            logging.info(f"Checking lib '{lib_name}' for unpin...");
            lib = plex.library.section(lib_name); colls = lib.collections()
            logging.info(f" Found {len(colls)} collections. Checking promotion status & label...")
            processed = 0
            for c in colls:
                processed += 1
                if not hasattr(c, 'title') or not hasattr(c, 'key'): logging.warning(f" Skipping invalid collection object #{processed}"); continue
                title = c.title
                try:
                    hub = c.visibility()
                    # Check internal attribute - this seems necessary for now
                    if hub and hub._promoted:
                        logging.debug(f" '{title}' is promoted. Checking label...")
                        labels = [l.tag.lower() for l in c.labels] if hasattr(c, 'labels') else []
                        if label.lower() in labels:
                            logging.debug(f" '{title}' has label '{label}'. Checking exclusion...")
                            if title in excludes:
                                logging.info(f" Skipping unpin for explicitly excluded '{title}'.")
                                skipped+=1; continue # Do not unpin or remove label

                            # --- Proceed to unpin and remove label ---
                            try:
                                logging.info(f" Unpinning/Unlabeling '{title}'...")
                                # Remove Label First
                                try:
                                    c.removeLabel(label); logging.info(f"  Label '{label}' removed.")
                                    labels_rem+=1
                                except Exception as e: logging.error(f"  Label remove failed: {e}")
                                # Then Demote
                                try:
                                    hub.demoteHome(); hub.demoteShared(); logging.info(f"  Unpinned.")
                                    unpinned+=1
                                except Exception as de: logging.error(f"  Demote failed: {de}")
                            except Exception as ue: logging.error(f" Error during unpin/unlabel for '{title}': {ue}", exc_info=True)
                        else: logging.debug(f" '{title}' is promoted but lacks label '{label}'.")
                    # else: logging.debug(f" '{title}' is not promoted.") # Can be noisy
                except NotFound: logging.warning(f"Collection '{title}' not found during visibility check (deleted?).")
                except AttributeError as ae:
                     # Check if the error is specifically about _promoted missing
                     if '_promoted' in str(ae): logging.error(f" Error checking '{title}': `_promoted` attribute not found. Cannot determine status reliably.")
                     else: logging.error(f" Attribute Error checking '{title}': {ae}")
                except Exception as ve: logging.error(f" Visibility/Processing error for '{title}': {ve}", exc_info=True)
            logging.info(f" Finished checking {processed} collections in '{lib_name}'.")
        except NotFound: logging.error(f"Library '{lib_name}' not found during unpin.")
        except Exception as le: logging.error(f"Error processing library '{lib_name}' for unpin: {le}", exc_info=True)
    logging.info(f"--- Unpin Complete --- Unpinned:{unpinned}, Labels Removed:{labels_rem}, Skipped(Excluded):{skipped}.")


def get_active_special_collections(config):
    """Determines active 'special' collections based on current date."""
    today = datetime.now().date(); active = []; specials = config.get('special_collections', [])
    if not isinstance(specials, list): logging.warning("'special_collections' not a list."); return []
    logging.info(f"--- Checking {len(specials)} Special Periods for {today:%Y-%m-%d} ---")
    for i, sp in enumerate(specials):
        # Validate structure and types carefully
        if not isinstance(sp, dict) or not all(k in sp for k in ['start_date', 'end_date', 'collection_names']):
             logging.warning(f"Skipping invalid special entry #{i+1} (missing keys): {sp}"); continue
        s, e, names = sp.get('start_date'), sp.get('end_date'), sp.get('collection_names')
        if not isinstance(s,str) or not isinstance(e,str) or not isinstance(names,list) or not all(isinstance(n,str) for n in names):
            logging.warning(f"Skipping special entry #{i+1} due to invalid types: {sp}"); continue
        try:
            sd = datetime.strptime(s, '%m-%d').replace(year=today.year).date()
            ed = datetime.strptime(e, '%m-%d').replace(year=today.year).date()
            is_active = (today >= sd or today <= ed) if sd > ed else (sd <= today <= ed) # Handles year wrap
            if is_active:
                valid_names = [n for n in names if n] # Filter out empty strings
                if valid_names:
                    active.extend(valid_names); logging.info(f"Special period '{valid_names}' ACTIVE.")
        except ValueError: logging.error(f"Invalid date format in special entry #{i+1} ('{s}'/'{e}'). Use MM-DD.")
        except Exception as ex: logging.error(f"Error processing special entry #{i+1}: {ex}")
    unique_active = sorted(list(set(active)))
    logging.info(f"--- Special Check Complete --- Active: {unique_active or 'None'} ---")
    return unique_active


def get_all_special_collection_names(config):
    """Gets all unique, non-empty names defined in any special collections entry."""
    titles = set(); specials = config.get('special_collections', [])
    if not isinstance(specials, list): return titles
    for sp in specials:
        if isinstance(sp, dict) and isinstance(sp.get('collection_names'), list):
            titles.update(n.strip() for n in sp['collection_names'] if isinstance(n, str) and n.strip())
    return titles


def get_fully_excluded_collections(config, active_specials):
    """Combines explicit exclusions and inactive special collections."""
    explicit_set = {n.strip() for n in config.get('exclusion_list', []) if isinstance(n,str) and n.strip()}
    logging.info(f"Explicit title exclusions: {explicit_set or 'None'}")
    all_special = get_all_special_collection_names(config); active_special = set(active_specials)
    inactive_special = all_special - active_special
    if inactive_special: logging.info(f"Inactive special collections (also excluded from random/category): {inactive_special}")
    combined = explicit_set.union(inactive_special)
    logging.info(f"Total combined title exclusions (explicit + inactive special): {combined or 'None'}")
    return combined


def fill_with_random_collections(pool, slots):
    """Fills remaining slots with random choices from the provided pool."""
    if slots <= 0 or not pool: return []
    avail = list(pool); random.shuffle(avail); num = min(slots, len(avail))
    logging.info(f"Selecting {num} random item(s) from {len(avail)} remaining eligible collections.")
    selected = avail[:num]
    if selected: logging.info(f"Added random: {[getattr(c, 'title', '?') for c in selected]}")
    return selected

# ========================================================================
# ==                 MODIFIED filter_collections Function               ==
# ========================================================================
def filter_collections(config, all_collections_in_library, active_special_titles, library_pin_limit, library_name, selected_collections_history):
    logging.info(">>>>>> RUNNING filter_collections - MODIFIED VERSION CHECK <<<<<<")
    """Filters and selects pins based on priorities (Special > Category(Modes) > Random), excluding random picks from served categories.""" # Docstring updated
    logging.info(f"--- Filtering/Selection for '{library_name}' (Limit: {library_pin_limit}) ---")

    # --- Config Retrieval & Validation ---
    min_items = config.get('min_items_for_pinning', 10); min_items = 10 if not isinstance(min_items, int) or min_items < 0 else min_items
    titles_excluded = get_fully_excluded_collections(config, active_special_titles)
    recent_pins = get_recently_pinned_collections(selected_collections_history, config)
    regex_patterns = config.get('regex_exclusion_patterns', [])
    use_random_category_mode = config.get('use_random_category_mode', False)
    skip_perc = config.get('random_category_skip_percent', 70); skip_perc = max(0, min(100, skip_perc)) # Clamp 0-100
    library_categories_config = config.get('categories', {}).get(library_name, [])

    logging.info(f"Filtering: Min Items={min_items}, Random Cat Mode={use_random_category_mode}, Cat Skip Chance={skip_perc}%")

    # --- Initial Filtering Pass ---
    eligible_pool = []
    logging.info(f"Processing {len(all_collections_in_library)} collections through initial filters...")
    for c in all_collections_in_library:
        if not hasattr(c, 'title') or not c.title: continue
        title = c.title; is_special = title in active_special_titles
        # Check exclusions first
        if title in titles_excluded: logging.debug(f" Excluding '{title}' (Explicit/Inactive Special)."); continue
        if is_regex_excluded(title, regex_patterns): continue # Logged in function
        # Check recency (only if not special)
        if not is_special and title in recent_pins: logging.debug(f" Excluding '{title}' (Recent Pin)."); continue
        # Check item count (only if not special)
        if not is_special:
            try:
                item_count = c.childCount
                if item_count < min_items:
                    logging.debug(f" Excluding '{title}' (Low Item Count: {item_count} < {min_items})."); continue
            except Exception as e:
                logging.warning(f" Could not get item count for '{title}': {e}. Including collection anyway.") # Be lenient if count fails

        eligible_pool.append(c) # Passed all checks

    logging.info(f"Found {len(eligible_pool)} eligible collections after initial filtering.")
    if not eligible_pool: return [] # Exit early if nothing is eligible

    # --- Priority Selection ---
    collections_to_pin = []; pinned_titles = set(); remaining_slots = library_pin_limit
    random.shuffle(eligible_pool) # Shuffle once for randomness within priorities

    # --- Priority 1: Specials ---
    logging.info(f"Selection Step 1: Processing Active Special Collections")
    specials_found = []; pool_after_specials = [] # Pool for next steps
    for c in eligible_pool:
        # Check if it's special, slots remain, and not already pinned
        if c.title in active_special_titles and remaining_slots > 0 and c.title not in pinned_titles:
            logging.info(f"  Selecting ACTIVE special: '{c.title}'")
            specials_found.append(c); pinned_titles.add(c.title); remaining_slots -= 1
        else:
            pool_after_specials.append(c) # Keep non-specials or already pinned/over limit specials
    collections_to_pin.extend(specials_found)
    logging.info(f"Selected {len(specials_found)} special(s). Slots left: {remaining_slots}")

    # --- Priority 2: Categories (Conditional Logic) ---
    logging.info(f"Selection Step 2: Processing Categories (Random Mode: {use_random_category_mode})")
    category_collections_found = [] # Store collections selected in this step
    pool_after_categories = list(pool_after_specials) # Default pool for random fill if categories are skipped/empty
    served_category_names = set() # <<< Tracks categories from which items were picked

    if remaining_slots > 0:
        valid_cats = [cat for cat in library_categories_config if isinstance(cat,dict) and cat.get('pin_count',0)>0 and cat.get('collections')]

        if not valid_cats:
            logging.info(f"  No valid categories defined or found for '{library_name}'. Skipping category selection.")
        else:
            # --- Branch based on mode ---
            if use_random_category_mode:
                logging.info(f"  Random Mode: Checking skip chance ({skip_perc}%).")
                if random.random() < (skip_perc / 100.0):
                    logging.info("  Category selection SKIPPED this cycle (random chance occurred).")
                else:
                    logging.info(f"  Proceeding to select ONE random category from {len(valid_cats)} valid options.")
                    chosen_cat = random.choice(valid_cats)
                    cat_name=chosen_cat.get('category_name','Unnamed Category'); cat_count=chosen_cat.get('pin_count',0); cat_titles=chosen_cat.get('collections',[])
                    logging.info(f"  Randomly chose category: '{cat_name}' (Pin Count: {cat_count}, Titles Defined: {len(cat_titles)})")

                    eligible_chosen = []; temp_pool = []; processed_in_chosen = set()
                    for c in pool_after_specials:
                        if c.title in cat_titles and c.title not in pinned_titles:
                            eligible_chosen.append(c)
                        else:
                            temp_pool.append(c)

                    num_pick = min(cat_count, len(eligible_chosen), remaining_slots)
                    logging.info(f"  Attempting to select {num_pick} item(s) from '{cat_name}' (Eligible Found: {len(eligible_chosen)}, Slots Left: {remaining_slots}).")
                    if num_pick > 0:
                        random.shuffle(eligible_chosen)
                        selected_cat = eligible_chosen[:num_pick]
                        category_collections_found.extend(selected_cat)
                        new_pins = {c.title for c in selected_cat}
                        pinned_titles.update(new_pins); remaining_slots -= len(selected_cat); processed_in_chosen.update(new_pins)
                        served_category_names.add(cat_name) # <<< Record served category
                        logging.info(f"  Selected from '{cat_name}': {list(new_pins)}")

                    pool_after_categories = temp_pool + [c for c in eligible_chosen if c.title not in processed_in_chosen]
            else:
                # --- Mode OFF: Process ALL enabled categories (Default Logic) ---
                logging.info(f"  Default Mode: Processing {len(valid_cats)} valid categories.")
                cat_map = {}; slots_rem = {}
                for cat in valid_cats:
                    name = cat.get('category_name','Unnamed Category'); slots_rem[name] = cat.get('pin_count', 0) # Use .get() for safety
                    for title in cat.get('collections', []): cat_map.setdefault(title, []).append(cat)

                temp_pool_after_all_categories = []
                for c in pool_after_specials:
                    title = c.title; picked = False
                    if remaining_slots <= 0: temp_pool_after_all_categories.append(c); continue

                    if title in cat_map:
                        for cat_def in cat_map.get(title, []): # Use .get() for safety
                            cat_name = cat_def.get('category_name', 'Unnamed Category') # Use .get() for safety
                            if slots_rem.get(cat_name, 0) > 0 and remaining_slots > 0:
                                logging.info(f"  Selecting '{title}' for category '{cat_name}'.")
                                category_collections_found.append(c); pinned_titles.add(title)
                                remaining_slots -= 1; slots_rem[cat_name] -= 1;
                                served_category_names.add(cat_name) # <<< Record served category
                                picked = True; break
                    if not picked: temp_pool_after_all_categories.append(c)
                pool_after_categories = temp_pool_after_all_categories

            collections_to_pin.extend(category_collections_found)
            logging.info(f"Selected {len(category_collections_found)} collection(s) during category step. Slots left: {remaining_slots}")
    else:
         logging.info("Skipping category selection (no slots remaining).")
         pool_after_categories = list(pool_after_specials)

    # --- Priority 3: Random Fill (Exclude Served Category Items) --- <<< MODIFIED SECTION START
    # This entire block calculates exclusions before random fill

    titles_in_served_categories = set()
    if served_category_names:
        # Log which categories contributed items and will now have their members excluded from random
        logging.info(f"Categories served this cycle (items belonging to these will be excluded from random fill): {served_category_names}")
        # Find all titles defined in the config for the served categories
        for cat_config in library_categories_config:
             # Check if the category config is valid and if its name was served
             if isinstance(cat_config, dict) and cat_config.get('category_name') in served_category_names:
                # Add all collections defined for this served category to the exclusion set
                category_titles = cat_config.get('collections', [])
                if isinstance(category_titles, list): # Ensure it's a list before updating
                     titles_in_served_categories.update(t for t in category_titles if isinstance(t, str)) # Ensure titles are strings

        if titles_in_served_categories:
            logging.info(f"Excluding {len(titles_in_served_categories)} titles belonging to served categories from random pool.")
            # Optional: Log the actual titles being excluded (can be verbose)
            # logging.debug(f"Titles excluded from random pool: {sorted(list(titles_in_served_categories))}")
        else:
             logging.info("No specific titles found listed under the served categories to exclude.")
    # Else: No categories were served, so no exclusion needed based on categories.

    # Filter the pool available for random fill
    original_pool_size = len(pool_after_categories)
    final_random_pool = [
        c for c in pool_after_categories
        if getattr(c, 'title', None) not in titles_in_served_categories
    ]
    # Log the result of the filtering
    logging.info(f"Pool size for random fill after category exclusion: {len(final_random_pool)} (Original pool size before exclusion: {original_pool_size})")

    # Proceed with random fill using the filtered pool
    if remaining_slots > 0:
        logging.info(f"Selection Step 3: Filling remaining {remaining_slots} slot(s) randomly.")
        # Use the potentially smaller, filtered pool
        random_found = fill_with_random_collections(final_random_pool, remaining_slots)
        collections_to_pin.extend(random_found)
    else:
        logging.info("Skipping random fill (no remaining slots).")

    # --- <<< MODIFIED SECTION END ---

    # --- Final Result ---
    final_titles = [getattr(c, 'title', 'Untitled') for c in collections_to_pin]
    logging.info(f"--- Filtering/Selection Complete for '{library_name}' ---")
    logging.info(f"Final list ({len(final_titles)} items): {final_titles}")
    return collections_to_pin

# ========================================================================
# ==              End of MODIFIED filter_collections Function           ==
# ========================================================================


# --- Main Function ---
def main():
    """Main execution logic for one cycle."""
    run_start = datetime.now()
    logging.info(f"====== Starting Run: {run_start:%Y-%m-%d %H:%M:%S} ======")
    update_status("Starting")
    try: config = load_config()
    except SystemExit: update_status("CRITICAL: Config Error"); return # Exit cycle if config fails

    interval = config.get('pinning_interval', 180); interval = 180 if not isinstance(interval,(int,float)) or interval<=0 else interval
    next_run_ts = (run_start + timedelta(minutes=interval)).timestamp()
    logging.info(f"Interval: {interval} min. Next run approx: {datetime.fromtimestamp(next_run_ts):%Y-%m-%d %H:%M:%S}")
    update_status("Running", next_run_ts)

    plex = connect_to_plex(config)
    if not plex: logging.critical("Plex connection failed. Aborting run."); return # Exit cycle if no connection

    history = load_selected_collections(); libs = config.get('library_names', [])
    if not libs: logging.warning("No libraries defined in config. Nothing to process."); return # Exit cycle if no libs

    # --- Unpin First ---
    unpin_collections(plex, libs, config)

    pin_limits = config.get('number_of_collections_to_pin', {});
    if not isinstance(pin_limits, dict): pin_limits = {}
    all_pinned_this_run = [] # Track titles successfully pinned across all libraries

    # --- Process Libraries ---
    for lib_name in libs:
        if not isinstance(lib_name, str): logging.warning(f"Skipping invalid library name: {lib_name}"); continue
        limit = pin_limits.get(lib_name, 0); limit = 0 if not isinstance(limit, int) or limit < 0 else limit
        if limit == 0: logging.info(f"Skipping library '{lib_name}' (pin limit 0)."); continue

        logging.info(f"===== Processing Library: '{lib_name}' (Pin Limit: {limit}) =====")
        update_status(f"Processing: {lib_name}", next_run_ts) # Update status for current lib
        lib_start_time = time.time()

        collections = get_collections_from_library(plex, lib_name)
        if not collections: logging.info(f"No collections found or retrieved from '{lib_name}'."); continue

        active_specials = get_active_special_collections(config)
        # Call the modified filter_collections function
        to_pin = filter_collections(config, collections, active_specials, limit, lib_name, history)

        if to_pin:
            # Pin collections and get list of titles actually pinned
            pinned_now = pin_collections(to_pin, config, plex)
            all_pinned_this_run.extend(pinned_now)
        else:
            logging.info(f"No collections selected for pinning in '{lib_name}' after filtering.")

        logging.info(f"===== Completed Library: '{lib_name}' in {time.time() - lib_start_time:.2f}s =====")

    # --- Update History File ---
    if all_pinned_this_run:
        timestamp = datetime.now().isoformat() # Use ISO format for keys
        unique_pins = set(all_pinned_this_run)
        all_specials_list = get_all_special_collection_names(config) # Get all titles ever defined as special
        # Only add non-special items to history for recency check
        non_specials_pinned_this_run = sorted(list(unique_pins - all_specials_list))

        if non_specials_pinned_this_run:
             # Make sure history is loaded (should be, but safety check)
             if not isinstance(history, dict): history = {}
             history[timestamp] = non_specials_pinned_this_run
             save_selected_collections(history)
             logging.info(f"Updated history ({len(non_specials_pinned_this_run)} non-special items) for {timestamp}.")
             specials_pinned_count = len(unique_pins) - len(non_specials_pinned_this_run)
             if specials_pinned_count > 0: logging.info(f"Note: {specials_pinned_count} special item(s) pinned but not added to recency history.")
        else:
             logging.info("Only special items (or none) were successfully pinned this cycle. History not updated for recency blocking.")
    else:
         logging.info("Nothing successfully pinned this cycle. History not updated.")

    run_duration = datetime.now() - run_start
    logging.info(f"====== Run Finished: {datetime.now():%Y-%m-%d %H:%M:%S} (Duration: {run_duration}) ======")


# --- Continuous Loop ---
def run_continuously():
    """Runs main logic in loop with sleep."""
    while True:
        next_run_ts_planned = None; sleep_s = 180 * 60 # Default sleep

        try:
            interval = 180 # Default interval
            try: # Load config just for interval check, suppress most errors
                if os.path.exists(CONFIG_PATH):
                    with open(CONFIG_PATH,'r',encoding='utf-8') as f: cfg = json.load(f)
                    temp_interval = cfg.get('pinning_interval', 180)
                    if isinstance(temp_interval,(int,float)) and temp_interval > 0: interval = temp_interval
            except Exception as e: logging.debug(f"Minor error reading config for interval: {e}")

            sleep_s = interval * 60
            next_run_ts_planned = (datetime.now() + timedelta(seconds=sleep_s)).timestamp()

            # --- Run the main processing logic ---
            main()

        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Exiting Collexions script.")
            update_status("Stopped (Interrupt)")
            break # Exit the while loop
        except SystemExit as e:
             # This happens if load_config or other critical part calls sys.exit()
             logging.critical(f"SystemExit called during run cycle. Exiting Collexions script. Exit code: {e.code}")
             # Status might have already been updated by load_config, but set final state here too
             update_status("Stopped (SystemExit)")
             break # Exit the while loop
        except Exception as e:
            # Catch any other unexpected errors *outside* the main() function's try/except
            logging.critical(f"CRITICAL UNHANDLED EXCEPTION in run_continuously loop: {e}", exc_info=True)
            update_status(f"CRASHED ({type(e).__name__})")
            # Decide whether to break or try to continue after a delay
            sleep_s = 60 # Sleep for a short period before potentially retrying
            logging.error(f"Sleeping for {sleep_s} seconds before next attempt after crash.")


        # --- Sleep Calculation & Execution ---
        actual_sleep = sleep_s
        current_ts = datetime.now().timestamp()

        # Calculate sleep duration based on planned next run, ensuring it's not negative
        if next_run_ts_planned and next_run_ts_planned > current_ts:
            actual_sleep = max(1, next_run_ts_planned - current_ts) # Sleep at least 1 sec
            sleep_until = datetime.fromtimestamp(next_run_ts_planned)
            update_status("Sleeping", next_run_ts_planned)
            logging.info(f"Next run scheduled around: {sleep_until:%Y-%m-%d %H:%M:%S}")
        else:
            # If planned time is past or wasn't calculated (e.g., after crash), schedule based on interval from now
            next_run_est_ts = current_ts + sleep_s
            sleep_until = datetime.fromtimestamp(next_run_est_ts)
            update_status("Sleeping", next_run_est_ts)
            logging.info(f"Next run approximately: {sleep_until:%Y-%m-%d %H:%M:%S}")

        logging.info(f"Sleeping for {actual_sleep:.0f} seconds...")
        try:
            # Interruptible sleep loop
            sleep_end_time = time.time() + actual_sleep
            while time.time() < sleep_end_time:
                 # Sleep in small chunks to remain responsive to KeyboardInterrupt
                 check_interval = min(sleep_end_time - time.time(), 1.0)
                 if check_interval <= 0: break
                 time.sleep(check_interval)
        except KeyboardInterrupt:
             logging.info("Keyboard interrupt received during sleep. Exiting Collexions script.")
             update_status("Stopped (Interrupt during sleep)")
             break # Exit the while loop

# --- Script Entry Point ---
if __name__ == "__main__":
    # This block executes when the script is run directly (python ColleXions.py)
    update_status("Initializing")
    try:
        # Perform initial setup checks if needed before starting loop
        logging.info("Collexions script starting up...")
        # Test config load once at start? load_config() handles exit on critical failure.
        # config = load_config() # Ensures config is valid before first run

        # Start the continuous loop
        run_continuously()

    except SystemExit:
         # This handles sys.exit called during initial checks if any were added above
         logging.info("Exiting due to SystemExit during initialization.")
         # Status should have been set before exit
    except Exception as e:
        # Final safety net for any error during startup before loop begins
        logging.critical(f"FATAL STARTUP/UNHANDLED ERROR: {e}", exc_info=True)
        update_status("FATAL ERROR")
        sys.exit(1) # Exit with error code