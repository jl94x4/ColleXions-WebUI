import requests
import json
import os

CONFIG_FILE = "config/config.json"

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def test_mdblist():
    config = load_config()
    api_key = config.get('mdblist_api_key')
    
    if not api_key:
        print("Error: 'mdblist_api_key' not found in config.json")
        print("Please add 'mdblist_api_key': 'YOUR_KEY_HERE' to config.json")
        return

    # Basic test to get users lists
    url = f"https://mdblist.com/api/lists/user/?apikey={api_key}"
    print(f"Testing MDBList User Lists Endpoint: {url.split('?')[0]}")
    
    try:
        resp = requests.get(url, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Success! Found {len(data)} lists.")
            if len(data) > 0:
                print("First list:", data[0].get('name'))
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

    # Top Lists test
    toplists_url = f"https://mdblist.com/api/toplists/?apikey={api_key}"
    print(f"\nTesting MDBList Top Lists Endpoint: {toplists_url.split('?')[0]}")
    try:
        resp = requests.get(toplists_url, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Success! Found {len(data)} top lists.")
            if len(data) > 0:
                for i in range(min(3, len(data))):
                    print(f"- {data[i].get('name')} (User: {data[i].get('user')}, ID: {data[i].get('id')})")
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    if not os.path.exists(CONFIG_FILE):
        print(f"{CONFIG_FILE} not found. Running from correct directory?")
    else:
        test_mdblist()
