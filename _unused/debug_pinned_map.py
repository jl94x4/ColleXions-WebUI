
import os
import re
import time

LOG_FILE = "collexions.log"

def get_pinned_status_from_logs():
    pinned_map = {} # title -> bool
    if not os.path.exists(LOG_FILE):
        return pinned_map
        
    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            
        for line in lines:
            if "Starting Collexions Script Run" in line or "Starting Run at" in line:
                pinned_map = {}
                continue

            pin_match = re.search(r"Pinned '(.*)' successfully", line)
            if pin_match:
                title = pin_match.group(1).strip()
                pinned_map[title] = True
                continue
            
            unpin_match = re.search(r"Unpinned '(.*)' successfully", line)
            if unpin_match:
                title = unpin_match.group(1).strip()
                pinned_map[title] = False
    except Exception as e:
        print(f"Error: {e}")
        
    return pinned_map

if __name__ == "__main__":
    status = get_pinned_status_from_logs()
    pinned_titles = [t for t, p in status.items() if p]
    print(f"Pinned Titles found in logs (after last reset):")
    for t in pinned_titles:
        print(f" - {t}")
    if not pinned_titles:
        print("No pinned titles found.")
