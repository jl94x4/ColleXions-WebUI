
import os
import json
from plexapi.server import PlexServer

def load_config():
    config_path = 'config/config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def debug_pinning():
    config = load_config()
    url = config.get('plex_url')
    token = config.get('plex_token')
    lib_names = config.get('library_names', [])
    
    if not url or not token:
        print("Plex not configured")
        return

    plex = PlexServer(url, token)
    
    for lib_name in lib_names:
        print(f"\n--- Checking Library: {lib_name} ---")
        try:
            library = plex.library.section(lib_name)
            colls = library.collections()
            
            for coll in colls[:5]: # Just check a few
                hubs = coll.visibility()
                print(f"\nCOLLECTION: {coll.title}")
                if not hubs:
                    print("  No visibility hubs found.")
                    continue
                
                if not isinstance(hubs, list):
                    hubs = [hubs]
                
                for i, hub in enumerate(hubs):
                    print(f"  HUB {i}:")
                    attrs = ["context", "promoted", "_promoted", "identifier", "hubIdentifier", "title"]
                    for attr in attrs:
                        val = getattr(hub, attr, 'N/A')
                        print(f"    {attr}: {val} (type: {type(val)})")
                    
                    # Also print the raw elements if possible
                    try:
                        print(f"    Raw XML tag: {hub._element.tag}")
                        print(f"    Raw XML attrs: {hub._element.attrib}")
                    except:
                        pass
                        
        except Exception as e:
            print(f"Error in {lib_name}: {e}")

if __name__ == "__main__":
    debug_pinning()
