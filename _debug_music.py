"""
Run from the project root: python _debug_music.py
Prints thumbnail-related attributes for every collection in every library.
"""
import json, os
from plexapi.server import PlexServer

with open('config/config.json') as f:
    config = json.load(f)

plex = PlexServer(config['plex_url'], config['plex_token'])

for lib_name in config.get('library_names', []):
    try:
        library = plex.library.section(lib_name)
        print(f"\n=== {lib_name} (type={library.type}) ===")
        for coll in library.collections():
            thumb     = getattr(coll, 'thumb',     None)
            composite = getattr(coll, 'composite', None)
            art       = getattr(coll, 'art',       None)
            print(f"  {coll.title!r:40s}  thumb={str(thumb)[:60]!r}  composite={str(composite)[:60]!r}")
    except Exception as e:
        print(f"  ERROR in {lib_name}: {e}")
