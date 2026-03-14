import requests
import json

CONFIG_FILE = "config/config.json"

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def test_trakt_fetch():
    config = load_config()
    trakt_id = config.get('trakt_client_id')
    
    urls = [
        "https://trakt.tv/users/mojoard_pk/lists/vintage-british-tv",
        "https://trakt.tv/users/movist-app/lists/oscar-winners-best-picture"
    ]
    
    headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': trakt_id,
        'User-Agent': 'CollexionsManager/1.0'
    }

    # Test Search List
    print("\n--- Testing Search List 'vintage-british-tv' ---")
    url = "https://api.trakt.tv/search/list?query=vintage-british-tv"
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Search Status: {resp.status_code}")
    if resp.status_code == 200:
        results = resp.json()
        print(f"Found {len(results)} search results.")
        for r in results:
            lst = r.get('list', {})
            usr = r.get('user', {})
            print(f" - '{lst.get('name')}' by {usr.get('username')} (Slug: {lst.get('ids', {}).get('slug')}, Trakt ID: {lst.get('ids', {}).get('trakt')})")

    for url in urls:
        print(f"\n--- Testing URL: {url} ---")
        try:
            parts = url.strip().split('/')
            u_idx = parts.index('users')
            username = parts[u_idx + 1]
            slug = parts[u_idx + 3]
            print(f"Parsed -> Username: {username}, Slug: {slug}")
            
            # Test items with slug
            api_url = f"https://api.trakt.tv/users/{username}/lists/{slug}/items"
            print(f"Fetching from: {api_url}")
            resp = requests.get(api_url, headers=headers, timeout=10)
            print(f"Items Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Items Error Text: {resp.text}")
                print(f"Items Error Headers: {resp.headers}")
            else:
                print(f"Items Success! Found {len(resp.json())} items.")
        except Exception as e:
            print(f"Exception for {url}: {e}")

if __name__ == "__main__":
    test_trakt_fetch()
