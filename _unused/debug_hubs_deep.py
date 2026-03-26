
import os
import json
from plexapi.server import PlexServer

def load_config():
    config_path = 'config/config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def debug_hubs():
    config = load_config()
    url = config.get('plex_url')
    token = config.get('plex_token')
    lib_names = config.get('library_names', [])
    
    if not url or not token:
        return

    plex = PlexServer(url, token)
    
    for lib_name in lib_names:
        print(f"\n--- Library: {lib_name} ---")
        try:
            library = plex.library.section(lib_name)
            for coll in library.collections()[:10]:
                hubs = coll.visibility()
                print(f"\nCollection: {coll.title}")
                if not hubs:
                    print("  No hubs.")
                    continue
                if not isinstance(hubs, list): hubs = [hubs]
                
                for i, h in enumerate(hubs):
                    print(f"  Hub {i}:")
                    for attr in dir(h):
                        if attr.startswith('_') and attr != '_promoted': continue
                        if attr in ['ELEMENT', 'TAG']: continue
                        try:
                            val = getattr(h, attr)
                            if callable(val): continue
                            print(f"    {attr}: {val}")
                        except:
                            pass
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    debug_hubs()
