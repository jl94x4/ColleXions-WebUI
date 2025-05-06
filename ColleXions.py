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
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=log_handlers
)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# --- Status Update Function ---
def update_status(status_message="Running", next_run_timestamp=None):
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            logging.info(f"Created data directory: {DATA_DIR}")
        except OSError as e:
            logging.error(f"Could not create data directory {DATA_DIR}: {e}. Status update might fail.")

    status_data = {"status": status_message, "last_update": datetime.now().isoformat()}
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
    if not os.path.exists(DATA_DIR):
        try:
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
        logging.info("Repeat block hours set to 0. Recency check disabled.")
        return set()
    cutoff_time = datetime.now() - timedelta(hours=repeat_block_hours)
    recent_titles = set()
    timestamps_to_keep = {}
    logging.info(f"Checking history since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} for recently pinned non-special items (Repeat block: {repeat_block_hours} hours)")
    history_items = list(selected_collections_history.items())
    for timestamp_str, titles in history_items:
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
    keys_to_remove = set(selected_collections_history.keys()) - set(timestamps_to_keep.keys())
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
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            logging.info(f"Created config directory: {CONFIG_DIR}")
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
        if not isinstance(cfg.get('library_names'), list): cfg['library_names'] = []
        if not isinstance(cfg.get('categories'), dict): cfg['categories'] = {}
        if not isinstance(cfg.get('number_of_collections_to_pin'), dict): cfg['number_of_collections_to_pin'] = {}
        if not isinstance(cfg.get('exclusion_list'), list): cfg['exclusion_list'] = []
        if not isinstance(cfg.get('regex_exclusion_patterns'), list): cfg['regex_exclusion_patterns'] = []
        if not isinstance(cfg.get('special_collections'), list): cfg['special_collections'] = []
        skip_perc = cfg.get('random_category_skip_percent')
        if not (isinstance(skip_perc, int) and 0 <= skip_perc <= 100):
            logging.warning(f"Invalid 'random_category_skip_percent' ({skip_perc}). Clamping to 0-100.")
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
    plex_url, token = config.get('plex_url'), config.get('plex_token')
    if not plex_url or not token:
        logging.error("Plex URL/Token missing in config."); return None
    try:
        logging.info(f"Connecting to Plex: {plex_url}...");
        plex = PlexServer(plex_url, token, timeout=90)
        server_name = plex.friendlyName
        logging.info(f"Connected to Plex server '{server_name}'.");
        return plex
    except Unauthorized: logging.error("Plex connect failed: Unauthorized."); update_status("Error: Plex Unauthorized")
    except requests.exceptions.ConnectionError as e: logging.error(f"Plex connect failed: {e}"); update_status("Error: Plex Connection Failed")
    except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout): logging.error(f"Plex connect timeout: {plex_url}."); update_status("Error: Plex Connection Timeout")
    except Exception as e: logging.error(f"Plex connect failed: {e}", exc_info=True); update_status(f"Error: Plex Unexpected ({type(e).__name__})")
    return None

def get_collections_from_library(plex, lib_name):
    if not plex or not lib_name or not isinstance(lib_name, str): return []
    try:
        logging.info(f"Accessing lib: '{lib_name}'"); lib = plex.library.section(lib_name)
        logging.info(f"Fetching collections from '{lib_name}'..."); colls = lib.collections()
        logging.info(f"Found {len(colls)} collections in '{lib_name}'."); return colls
    except NotFound: logging.error(f"Library '{lib_name}' not found.")
    except Exception as e: logging.error(f"Error fetching collections from '{lib_name}': {e}", exc_info=True)
    return []

# --- MODIFIED pin_collections FUNCTION TO INCLUDE library_name ---
def pin_collections(colls_to_pin, config, plex, library_name): # MODIFIED: Added library_name
    """Pins the provided list of collections, adds label, and sends Discord notifications."""
    if not colls_to_pin: return []
    webhook, label = config.get('discord_webhook_url'), config.get('collexions_label')
    pinned_titles = []
    logging.info(f"--- Attempting to Pin {len(colls_to_pin)} Collections (for library '{library_name}') ---") # Added library_name to log
    for c in colls_to_pin:
        if not hasattr(c, 'title') or not hasattr(c, 'key'): logging.warning(f"Skipping invalid collection: {c}"); continue
        title = c.title; items = "?"
        try:
            try: items = f"{c.childCount} Item{'s' if c.childCount != 1 else ''}"
            except Exception: pass

            logging.info(f"Pinning: '{title}' ({items}) from library '{library_name}'") # Added library_name to log
            try:
                 hub = c.visibility(); hub.promoteHome(); hub.promoteShared()
                 pinned_titles.append(title); logging.info(f" Pinned '{title}' successfully.")
                 # MODIFIED: Added library_name to Discord message
                 if webhook: send_discord_message(webhook, f"📌 Collection '**{title}**' with **{items}** from **{library_name}** pinned.")
            except Exception as pe: logging.error(f" Pin failed '{title}': {pe}"); continue

            if label:
                try: c.addLabel(label); logging.info(f" Added label '{label}' to '{title}'.")
                except Exception as le: logging.error(f" Label add failed '{title}': {le}")

        except NotFound: logging.error(f"Collection '{title}' not found during pin process.")
        except Exception as e: logging.error(f"Error processing '{title}' for pinning: {e}", exc_info=True)

    logging.info(f"--- Pinning done. Successfully pinned {len(pinned_titles)}. ---"); return pinned_titles

def send_discord_message(webhook_url, message):
    if not webhook_url or not message: return
    if len(message) > 2000: message = message[:1997]+"..."
    data = {"content": message}; logging.info("Sending Discord message...")
    try:
        resp = requests.post(webhook_url, json=data, timeout=15); resp.raise_for_status()
        logging.info("Discord msg sent.")
    except Exception as e: logging.error(f"Discord send failed: {e}")

def unpin_collections(plex, lib_names, config):
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
                    if hub and hub._promoted:
                        logging.debug(f" '{title}' is promoted. Checking label...")
                        labels = [l.tag.lower() for l in c.labels] if hasattr(c, 'labels') else []
                        if label.lower() in labels:
                            logging.debug(f" '{title}' has label '{label}'. Checking exclusion...")
                            if title in excludes:
                                logging.info(f" Skipping unpin for explicitly excluded '{title}'.")
                                skipped+=1; continue
                            try:
                                logging.info(f" Unpinning/Unlabeling '{title}'...")
                                try:
                                    c.removeLabel(label); logging.info(f"  Label '{label}' removed.")
                                    labels_rem+=1
                                except Exception as e: logging.error(f"  Label remove failed: {e}")
                                try:
                                    hub.demoteHome(); hub.demoteShared(); logging.info(f"  Unpinned.")
                                    unpinned+=1
                                except Exception as de: logging.error(f"  Demote failed: {de}")
                            except Exception as ue: logging.error(f" Error during unpin/unlabel for '{title}': {ue}", exc_info=True)
                        else: logging.debug(f" '{title}' is promoted but lacks label '{label}'.")
                except NotFound: logging.warning(f"Collection '{title}' not found during visibility check (deleted?).")
                except AttributeError as ae:
                     if '_promoted' in str(ae): logging.error(f" Error checking '{title}': `_promoted` attribute not found. Cannot determine status reliably.")
                     else: logging.error(f" Attribute Error checking '{title}': {ae}")
                except Exception as ve: logging.error(f" Visibility/Processing error for '{title}': {ve}", exc_info=True)
            logging.info(f" Finished checking {processed} collections in '{lib_name}'.")
        except NotFound: logging.error(f"Library '{lib_name}' not found during unpin.")
        except Exception as le: logging.error(f"Error processing library '{lib_name}' for unpin: {le}", exc_info=True)
    logging.info(f"--- Unpin Complete --- Unpinned:{unpinned}, Labels Removed:{labels_rem}, Skipped(Excluded):{skipped}.")

def get_active_special_collections(config):
    today = datetime.now().date(); active = []; specials = config.get('special_collections', [])
    if not isinstance(specials, list): logging.warning("'special_collections' not a list."); return []
    logging.info(f"--- Checking {len(specials)} Special Periods for {today:%Y-%m-%d} ---")
    for i, sp in enumerate(specials):
        if not isinstance(sp, dict) or not all(k in sp for k in ['start_date', 'end_date', 'collection_names']):
             logging.warning(f"Skipping invalid special entry #{i+1} (missing keys): {sp}"); continue
        s, e, names = sp.get('start_date'), sp.get('end_date'), sp.get('collection_names')
        if not isinstance(s,str) or not isinstance(e,str) or not isinstance(names,list) or not all(isinstance(n,str) for n in names):
            logging.warning(f"Skipping special entry #{i+1} due to invalid types: {sp}"); continue
        try:
            sd = datetime.strptime(s, '%m-%d').replace(year=today.year).date()
            ed = datetime.strptime(e, '%m-%d').replace(year=today.year).date()
            is_active = (today >= sd or today <= ed) if sd > ed else (sd <= today <= ed)
            if is_active:
                valid_names = [n for n in names if n]
                if valid_names:
                    active.extend(valid_names); logging.info(f"Special period '{valid_names}' ACTIVE.")
        except ValueError: logging.error(f"Invalid date format in special entry #{i+1} ('{s}'/'{e}'). Use MM-DD.")
        except Exception as ex: logging.error(f"Error processing special entry #{i+1}: {ex}")
    unique_active = sorted(list(set(active)))
    logging.info(f"--- Special Check Complete --- Active: {unique_active or 'None'} ---")
    return unique_active

def get_all_special_collection_names(config):
    titles = set(); specials = config.get('special_collections', [])
    if not isinstance(specials, list): return titles
    for sp in specials:
        if isinstance(sp, dict) and isinstance(sp.get('collection_names'), list):
            titles.update(n.strip() for n in sp['collection_names'] if isinstance(n, str) and n.strip())
    return titles

def get_fully_excluded_collections(config, active_specials):
    explicit_set = {n.strip() for n in config.get('exclusion_list', []) if isinstance(n,str) and n.strip()}
    logging.info(f"Explicit title exclusions: {explicit_set or 'None'}")
    all_special = get_all_special_collection_names(config); active_special = set(active_specials)
    inactive_special = all_special - active_special
    if inactive_special: logging.info(f"Inactive special collections (also excluded from random/category): {inactive_special}")
    combined = explicit_set.union(inactive_special)
    logging.info(f"Total combined title exclusions (explicit + inactive special): {combined or 'None'}")
    return combined

def fill_with_random_collections(pool, slots):
    if slots <= 0 or not pool: return []
    avail = list(pool); random.shuffle(avail); num = min(slots, len(avail))
    logging.info(f"Selecting {num} random item(s) from {len(avail)} remaining eligible collections.")
    selected = avail[:num]
    if selected: logging.info(f"Added random: {[getattr(c, 'title', '?') for c in selected]}")
    return selected


## MODIFIED filter_collections Function (MODv9 - based on MODv8) ##
def filter_collections(config, all_collections_in_library, active_special_titles, library_pin_limit, library_name, selected_collections_history):
    """Filters and selects pins based on priorities (Special > Category(Modes) > Random), excluding random picks from served categories."""
    logging.info(f">>> MODv9 ENTERING filter_collections for LIBRARY: '{library_name}' <<<") # MODIFIED VERSION

    min_items = config.get('min_items_for_pinning', 10)
    min_items = 10 if not isinstance(min_items, int) or min_items < 0 else min_items
    titles_excluded = get_fully_excluded_collections(config, active_special_titles)
    recent_pins = get_recently_pinned_collections(selected_collections_history, config)
    regex_patterns = config.get('regex_exclusion_patterns', [])
    use_random_category_mode = config.get('use_random_category_mode', False)
    skip_perc = config.get('random_category_skip_percent', 70)
    skip_perc = max(0, min(100, skip_perc))

    try:
        raw_categories_for_library = config.get('categories', {}).get(library_name, [])
        library_categories_config = copy.deepcopy(raw_categories_for_library)
    except Exception as e:
        logging.error(f"Error deepcopying categories for '{library_name}': {e}. Proceeding with empty categories.")
        library_categories_config = []

    if library_categories_config:
        try:
            logging.info(f"DEBUG {library_name.upper()} (MODv9): Raw library_categories_config (after deepcopy) for '{library_name}': {json.dumps(library_categories_config)}")
        except Exception as e:
            logging.error(f"DEBUG {library_name.upper()} (MODv9): Error serializing library_categories_config for logging: {e}")
            logging.info(f"DEBUG {library_name.upper()} (MODv9): Raw library_categories_config (type: {type(library_categories_config)}): {library_categories_config}")

    logging.info(f"Filtering: Min Items={min_items}, Random Cat Mode={use_random_category_mode}, Cat Skip Chance={skip_perc}%")

    eligible_pool = []
    logging.info(f"Processing {len(all_collections_in_library)} collections through initial filters...")
    for c in all_collections_in_library:
        if not hasattr(c, 'title') or not c.title: continue
        title = c.title
        is_special = title in active_special_titles
        if title in titles_excluded:
            logging.debug(f" Excluding '{title}' (Explicit/Inactive Special).")
            continue
        if is_regex_excluded(title, regex_patterns):
            continue
        if not is_special and title in recent_pins:
            logging.debug(f" Excluding '{title}' (Recent Pin).")
            continue
        if not is_special:
            try:
                item_count = c.childCount
                if item_count < min_items:
                    logging.debug(f" Excluding '{title}' (Low Item Count: {item_count} < {min_items}).")
                    continue
            except Exception as e:
                logging.warning(f" Could not get item count for '{title}': {e}. Including collection anyway.")
        eligible_pool.append(c)

    logging.info(f"Found {len(eligible_pool)} eligible collections after initial filtering.")
    if not eligible_pool:
        return []

    collections_to_pin = []
    pinned_titles = set()
    remaining_slots = library_pin_limit
    random.shuffle(eligible_pool)

    logging.info(f"Selection Step 1: Processing Active Special Collections")
    specials_found = []
    pool_after_specials = []
    for c in eligible_pool:
        if c.title in active_special_titles and remaining_slots > 0 and c.title not in pinned_titles:
            logging.info(f"  Selecting ACTIVE special: '{c.title}'")
            specials_found.append(c)
            pinned_titles.add(c.title)
            remaining_slots -= 1
        else:
            pool_after_specials.append(c)
    collections_to_pin.extend(specials_found)
    logging.info(f"Selected {len(specials_found)} special(s). Slots left: {remaining_slots}")

    logging.info(f"Selection Step 2: Processing Categories (Random Mode: {use_random_category_mode})")
    category_collections_found = []
    pool_after_categories = list(pool_after_specials)
    served_category_names = set() 
    random_mode_broad_exclusion_active = False # MODv8 logic for broad exclusion in random mode

    if remaining_slots > 0:
        valid_cats = [cat_dict for cat_dict in library_categories_config if isinstance(cat_dict, dict) and cat_dict.get('pin_count', 0) > 0 and cat_dict.get('collections')]

        if valid_cats:
            try:
                logging.info(f"DEBUG {library_name.upper()} (MODv9): 'valid_cats' for '{library_name}' (count: {len(valid_cats)}): {json.dumps(valid_cats)}")
            except Exception as e:
                logging.error(f"DEBUG {library_name.upper()} (MODv9): Error serializing valid_cats for logging: {e}")
                logging.info(f"DEBUG {library_name.upper()} (MODv9): 'valid_cats' (type: {type(valid_cats)}, len: {len(valid_cats)}): {valid_cats}")

        if not valid_cats:
            logging.info(f"  No valid categories defined or found for '{library_name}'. Skipping category selection.")
        else:
            if use_random_category_mode:
                random_mode_broad_exclusion_active = True 
                logging.info(f"  Random Category Mode active for '{library_name}'. All collections from all {len(valid_cats)} defined valid categories will be excluded from random fill, regardless of picking/skipping.")
                logging.info(f"  Random Mode: Checking skip chance ({skip_perc}%).")
                if random.random() < (skip_perc / 100.0):
                    logging.info("  Category selection SKIPPED this cycle (random chance occurred).")
                else: 
                    logging.info(f"  Proceeding to select ONE random category from {len(valid_cats)} valid options.")
                    chosen_cat = random.choice(valid_cats)
                    cat_name = chosen_cat.get('category_name', 'Unnamed Category').strip()
                    cat_count = chosen_cat.get('pin_count', 0)
                    cat_titles = chosen_cat.get('collections', [])
                    logging.info(f"  Randomly chose category: '{cat_name}' (Pin Count: {cat_count}, Titles Defined: {len(cat_titles)})")

                    eligible_chosen = []
                    temp_pool = [] 
                    for c_item in pool_after_specials:
                        if c_item.title in cat_titles and c_item.title not in pinned_titles:
                            eligible_chosen.append(c_item)
                        else:
                            temp_pool.append(c_item)
                    
                    num_pick = min(cat_count, len(eligible_chosen), remaining_slots)
                    logging.info(f"  Attempting to select {num_pick} item(s) from '{cat_name}' (Eligible Found: {len(eligible_chosen)}, Slots Left: {remaining_slots}).")
                    if num_pick > 0:
                        random.shuffle(eligible_chosen)
                        selected_cat_items = eligible_chosen[:num_pick]
                        category_collections_found.extend(selected_cat_items)
                        new_pins_titles = {s_item.title for s_item in selected_cat_items}
                        pinned_titles.update(new_pins_titles)
                        remaining_slots -= len(selected_cat_items)
                        # served_category_names.add(cat_name) # Not strictly needed for exclusion logic in random mode now, but good for logging
                        logging.info(f"  Selected from '{cat_name}': {list(new_pins_titles)}")
                    
                    temp_pool_after_this_category_pick = []
                    current_pinned_for_category = {item.title for item in category_collections_found}
                    for c_item in pool_after_specials:
                        if c_item.title not in current_pinned_for_category:
                            temp_pool_after_this_category_pick.append(c_item)
                    pool_after_categories = temp_pool_after_this_category_pick
            else:  # Default Mode
                logging.info(f"  Default Mode: Processing {len(valid_cats)} valid categories.")
                cat_map = {}
                slots_rem = {}
                for cat_definition in valid_cats:
                    name = cat_definition.get('category_name', 'Unnamed Category').strip()
                    slots_rem[name] = cat_definition.get('pin_count', 0)
                    for collection_title_in_cat in cat_definition.get('collections', []):
                        cat_map.setdefault(collection_title_in_cat, []).append(cat_definition)

                temp_pool_after_all_categories = []
                for c_item in pool_after_specials:
                    title = c_item.title
                    picked_for_category_this_item = False
                    if remaining_slots <= 0:
                        temp_pool_after_all_categories.append(c_item)
                        continue

                    if title in cat_map:
                        for cat_def_for_item in cat_map.get(title, []):
                            cat_name = cat_def_for_item.get('category_name', 'Unnamed Category').strip()
                            if slots_rem.get(cat_name, 0) > 0 and remaining_slots > 0:
                                logging.info(f"  Selecting '{title}' for category '{cat_name}'.")
                                category_collections_found.append(c_item)
                                pinned_titles.add(title)
                                remaining_slots -= 1
                                slots_rem[cat_name] -= 1
                                served_category_names.add(cat_name) 
                                picked_for_category_this_item = True
                                break 
                    if not picked_for_category_this_item:
                        temp_pool_after_all_categories.append(c_item)
                pool_after_categories = temp_pool_after_all_categories
            
            collections_to_pin.extend(category_collections_found)
            logging.info(f"Selected {len(category_collections_found)} collection(s) during category step. Slots left: {remaining_slots}")
    else:
        logging.info("Skipping category selection (no slots remaining).")
        pool_after_categories = list(pool_after_specials)

    titles_to_exclude_from_random = set()

    if random_mode_broad_exclusion_active: 
        logging.info(f"Random Category Mode active for '{library_name}': EXCLUDING ALL collections from ALL {len(valid_cats)} defined valid categories from random fill.")
        if valid_cats:
            for cat_config in valid_cats:
                category_titles_to_exclude = cat_config.get('collections', [])
                if isinstance(category_titles_to_exclude, list):
                    titles_to_exclude_from_random.update(t for t in category_titles_to_exclude if isinstance(t, str))
            if titles_to_exclude_from_random:
                 logging.info(f"Total of {len(titles_to_exclude_from_random)} titles from all defined valid categories for '{library_name}' marked for exclusion from random pool.")
            else: # Should not happen if valid_cats was non-empty and they had collections
                 logging.info(f"No collections found in any defined valid categories for '{library_name}' to broadly exclude (check category definitions).")
        else: # Should not happen if random_mode_broad_exclusion_active is true
            logging.info(f"No valid categories found for library '{library_name}' to exclude collections from in random mode (this state should be rare).")

    elif served_category_names: # Default Mode exclusion
        logging.info(f"Default Mode: Categories served this cycle (items belonging to these will be excluded from random fill): {served_category_names}")
        for cat_config_item_from_lib in library_categories_config: 
            if isinstance(cat_config_item_from_lib, dict):
                current_cat_name_from_config = cat_config_item_from_lib.get('category_name', '').strip()
                if current_cat_name_from_config in served_category_names:
                    category_titles = cat_config_item_from_lib.get('collections', [])
                    if isinstance(category_titles, list):
                        titles_to_exclude_from_random.update(t for t in category_titles if isinstance(t, str))
        if titles_to_exclude_from_random:
            logging.info(f"Excluding {len(titles_to_exclude_from_random)} titles belonging to *specifically served* categories from random pool.")
        else:
            logging.info("No specific titles found listed under the *specifically served* categories to exclude from random pool.")

    original_pool_size = len(pool_after_categories)
    temp_final_pool = []
    for c_item in pool_after_categories:
        title = getattr(c_item, 'title', None)
        if title not in titles_to_exclude_from_random and title not in pinned_titles: # Ensure not already pinned by special/category either
            temp_final_pool.append(c_item)
    final_random_pool = temp_final_pool

    logging.info(f"Pool size for random fill after category exclusion: {len(final_random_pool)} (Original pool size: {original_pool_size}, Titles marked for category exclusion: {len(titles_to_exclude_from_random)})")

    if remaining_slots > 0:
        logging.info(f"Selection Step 3: Filling remaining {remaining_slots} slot(s) randomly.")
        random_found = fill_with_random_collections(final_random_pool, remaining_slots)
        collections_to_pin.extend(random_found)
    else:
        logging.info("Skipping random fill (no remaining slots).")

    final_titles = [getattr(c_item, 'title', 'Untitled') for c_item in collections_to_pin]
    logging.info(f"--- Filtering/Selection Complete for '{library_name}' ---")
    logging.info(f"Final list ({len(final_titles)} items): {final_titles}")
    return collections_to_pin

# ========================================================================
# ==              End of MODIFIED filter_collections Function           ==
# ========================================================================

# --- Main Function ---
def main():
    run_start = datetime.now()
    logging.info(f"====== Starting Run: {run_start:%Y-%m-%d %H:%M:%S} ======")
    update_status("Starting")
    try: 
        config = load_config()
        if config: # MODv9: Diagnostic log in main remains as MODv8 for now, or can be updated.
            movies_categories_from_main = config.get('categories', {}).get('Movies', 'Movies_KEY_NOT_FOUND_in_categories')
            if isinstance(movies_categories_from_main, list):
                logging.info(f"DEBUG MAIN (MODv9): 'Movies' categories directly from loaded config in main(): Count={len(movies_categories_from_main)}, Data={json.dumps(movies_categories_from_main)}")
            else:
                logging.info(f"DEBUG MAIN (MODv9): 'Movies' categories key found, but not a list: {movies_categories_from_main}")
    except SystemExit: 
        update_status("CRITICAL: Config Error")
        return

    interval = config.get('pinning_interval', 180); interval = 180 if not isinstance(interval,(int,float)) or interval<=0 else interval
    next_run_ts = (run_start + timedelta(minutes=interval)).timestamp()
    logging.info(f"Interval: {interval} min. Next run approx: {datetime.fromtimestamp(next_run_ts):%Y-%m-%d %H:%M:%S}")
    update_status("Running", next_run_ts)

    plex = connect_to_plex(config)
    if not plex: logging.critical("Plex connection failed. Aborting run."); return

    history = load_selected_collections(); libs = config.get('library_names', [])
    if not libs: logging.warning("No libraries defined in config. Nothing to process."); return

    unpin_collections(plex, libs, config)

    pin_limits = config.get('number_of_collections_to_pin', {});
    if not isinstance(pin_limits, dict): pin_limits = {}
    all_pinned_this_run = []

    for lib_name in libs:
        if not isinstance(lib_name, str): logging.warning(f"Skipping invalid library name: {lib_name}"); continue
        limit = pin_limits.get(lib_name, 0); limit = 0 if not isinstance(limit, int) or limit < 0 else limit
        if limit == 0: logging.info(f"Skipping library '{lib_name}' (pin limit 0)."); continue

        logging.info(f"===== Processing Library: '{lib_name}' (Pin Limit: {limit}) =====")
        update_status(f"Processing: {lib_name}", next_run_ts)
        lib_start_time = time.time()

        collections = get_collections_from_library(plex, lib_name)
        if not collections: logging.info(f"No collections found or retrieved from '{lib_name}'."); continue

        active_specials = get_active_special_collections(config)
        to_pin = filter_collections(config, collections, active_specials, limit, lib_name, history)

        if to_pin:
            # MODIFIED: Pass lib_name to pin_collections
            pinned_now = pin_collections(to_pin, config, plex, lib_name) 
            all_pinned_this_run.extend(pinned_now)
        else:
            logging.info(f"No collections selected for pinning in '{lib_name}' after filtering.")

        logging.info(f"===== Completed Library: '{lib_name}' in {time.time() - lib_start_time:.2f}s =====")

    if all_pinned_this_run:
        timestamp = datetime.now().isoformat()
        unique_pins = set(all_pinned_this_run)
        all_specials_list = get_all_special_collection_names(config)
        non_specials_pinned_this_run = sorted(list(unique_pins - all_specials_list))

        if non_specials_pinned_this_run:
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
    while True:
        next_run_ts_planned = None; sleep_s = 180 * 60
        try:
            interval = 180
            try:
                if os.path.exists(CONFIG_PATH):
                    with open(CONFIG_PATH,'r',encoding='utf-8') as f: cfg = json.load(f)
                    temp_interval = cfg.get('pinning_interval', 180)
                    if isinstance(temp_interval,(int,float)) and temp_interval > 0: interval = temp_interval
            except Exception as e: logging.debug(f"Minor error reading config for interval: {e}")
            sleep_s = interval * 60
            next_run_ts_planned = (datetime.now() + timedelta(seconds=sleep_s)).timestamp()
            main()
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Exiting Collexions script.")
            update_status("Stopped (Interrupt)")
            break
        except SystemExit as e:
             logging.critical(f"SystemExit called during run cycle. Exiting Collexions script. Exit code: {e.code}")
             update_status("Stopped (SystemExit)")
             break
        except Exception as e:
            logging.critical(f"CRITICAL UNHANDLED EXCEPTION in run_continuously loop: {e}", exc_info=True)
            update_status(f"CRASHED ({type(e).__name__})")
            sleep_s = 60
            logging.error(f"Sleeping for {sleep_s} seconds before next attempt after crash.")

        actual_sleep = sleep_s
        current_ts = datetime.now().timestamp()
        if next_run_ts_planned and next_run_ts_planned > current_ts:
            actual_sleep = max(1, next_run_ts_planned - current_ts)
            sleep_until = datetime.fromtimestamp(next_run_ts_planned)
            update_status("Sleeping", next_run_ts_planned)
            logging.info(f"Next run scheduled around: {sleep_until:%Y-%m-%d %H:%M:%S}")
        else:
            next_run_est_ts = current_ts + sleep_s
            sleep_until = datetime.fromtimestamp(next_run_est_ts)
            update_status("Sleeping", next_run_est_ts)
            logging.info(f"Next run approximately: {sleep_until:%Y-%m-%d %H:%M:%S}")

        logging.info(f"Sleeping for {actual_sleep:.0f} seconds...")
        try:
            sleep_end_time = time.time() + actual_sleep
            while time.time() < sleep_end_time:
                 check_interval = min(sleep_end_time - time.time(), 1.0)
                 if check_interval <= 0: break
                 time.sleep(check_interval)
        except KeyboardInterrupt:
             logging.info("Keyboard interrupt received during sleep. Exiting Collexions script.")
             update_status("Stopped (Interrupt during sleep)")
             break

# --- Script Entry Point ---
if __name__ == "__main__":
    update_status("Initializing")
    try:
        logging.info("Collexions script starting up...")
        run_continuously()
    except SystemExit:
         logging.info("Exiting due to SystemExit during initialization.")
    except Exception as e:
        logging.critical(f"FATAL STARTUP/UNHANDLED ERROR: {e}", exc_info=True)
        update_status("FATAL ERROR")
        sys.exit(1)
