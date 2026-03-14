
import requests
import json

def check_api():
    try:
        resp = requests.get('http://localhost:5000/api/collections')
        data = resp.json()
        
        # We handle the list response
        target_titles = ['Top 250 Sci-Fi Films', 'Reddit Selections']
        for coll in data:
            if coll['title'] in target_titles:
                print(f"\nCOLLECTION: {coll['title']}")
                print(f"  is_pinned (from logs): {coll['is_pinned']}")
                print(f"  hub_debug: {json.dumps(coll['hub_debug'], indent=2)}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_api()
