import { AppConfig } from "./types";

export const DEFAULT_CONFIG: AppConfig = {
    plex_url: "",
    plex_token: "",
    collexions_label: "Collexions",
    dry_run: false,
    pinning_interval: 180,
    repeat_block_hours: 12,
    min_items_for_pinning: 10,
    discord_webhook_url: "",
    use_random_category_mode: false,
    random_category_skip_percent: 70,
    exclusion_list: [],
    regex_exclusion_patterns: [],
    special_collections: [],
    library_names: [],
    number_of_collections_to_pin: {},
    categories: {},
    tmdb_api_key: "",
    trakt_client_id: "",
    mdblist_api_key: "",
    enable_trending_pinning: false,
};

export const USER_PROVIDED_CONFIG: AppConfig = {
    "plex_url": "http://192.168.1.6:32400",
    "plex_token": "nYVkubKz4qeN6kMez6n2",
    "collexions_label": "Collexions",
    "dry_run": true,
    "pinning_interval": 30,
    "repeat_block_hours": 6,
    "min_items_for_pinning": 12,
    "discord_webhook_url": "https://discord.com/api/webhooks/1296267195999064074/3wotRqLa9peVcWZY4C0eKeBd8N08dhEFJ6VoEW8g6mvyVpFrZ2rfWWwFMjZSkcl-xnFR",
    "use_random_category_mode": true,
    "random_category_skip_percent": 70,
    "library_names": [
        "Movies",
        "Movies - Misc",
        "Music",
        "TV Shows",
        "TV Shows - Kids",
        "TV Shows - Reality",
        "TV Shows - Sports"
    ],
    "exclusion_list": [
        "Top Films This Week",
        "Trending",
        "Trending TV Shows",
        "Movies Available in 4K/UHD",
        "Top 20 TV Shows This Week",
        "Latest Streaming Network Shows",
        "Trending Reality",
        "Trending Kids",
        "Trending Documentaries",
        "Recently Added in Kids - Movies",
        "Hallmark Christmas Movies",
        "BAFTA Television Awards 2025 - Winners"
    ],
    "regex_exclusion_patterns": [
        "007",
        "Carry",
        "Star Wars"
    ],
    "number_of_collections_to_pin": {
        "TV Shows": 2,
        "TV Shows - Reality": 1,
        "TV Shows - Kids": 1,
        "Movies": 2,
        "Movies Misc": 1,
        "TV Shows - Sports": 1,
        "Music": 1
    },
    "special_collections": [
        {
            "start_date": "03-16",
            "end_date": "03-17",
            "collection_names": [
                "St. Patrick's Day Movies"
            ]
        },
        {
            "start_date": "10-01",
            "end_date": "10-31",
            "collection_names": [
                "Halloween Movies",
                "Halloween Movies"
            ]
        },
        {
            "start_date": "06-01",
            "end_date": "06-15",
            "collection_names": [
                "LGBTQ+ Pride Month Movies",
                "LGBTQ+ Pride Month"
            ]
        },
        {
            "start_date": "04-19",
            "end_date": "04-22",
            "collection_names": [
                "Easter Movies"
            ]
        },
        {
            "start_date": "12-27",
            "end_date": "01-01",
            "collection_names": [
                "New Year's Eve Movies"
            ]
        },
        {
            "start_date": "02-10",
            "end_date": "02-14",
            "collection_names": [
                "Valentine's Day Movies",
                "Chick Flicks",
                "Rotten Tomatoes Best Rom Com"
            ]
        },
        {
            "start_date": "11-03",
            "end_date": "11-11",
            "collection_names": [
                "Memorial Day"
            ]
        },
        {
            "start_date": "11-19",
            "end_date": "11-26",
            "collection_names": [
                "Thanksgiving Movies"
            ]
        },
        {
            "start_date": "12-01",
            "end_date": "12-25",
            "collection_names": [
                "Tis The Season To Be Jolly",
                "Hallmark Christmas Movies",
                "Christmas Favourites"
            ]
        }
    ],
    "categories": {
        "Movies": [
            {
                "category_name": "Heroes",
                "pin_count": 1,
                "collections": [
                    "In Association With Marvel",
                    "DC Comics",
                    "DC Universe (DCU)",
                    "Marvel Cinematic Universe",
                    "Marvel Studios",
                    "MARVEL Cinematic Universe Chronological Order",
                    "Everyone Needs A Hero",
                    "DC Animated Universe",
                    "The Infinity Saga",
                    "Worlds of DC (DCEU)"
                ]
            },
            {
                "category_name": "Kids Collections",
                "pin_count": 1,
                "collections": [
                    "🌙 Dreamworks Movies",
                    "DreamWorks Studios",
                    "Barbie Animated Movies",
                    "Sony Picture Animation Movies",
                    "Blue Sky Studios Animation",
                    "Pixar Animation Studios",
                    "Walt Disney Animated Feature Films",
                    "Curious George Collection"
                ]
            },
            {
                "category_name": "Winners",
                "pin_count": 1,
                "collections": [
                    "Oscar Winners 2023",
                    "Oscar Nominated 2022",
                    "Golden Globes 2022",
                    "Oscar Noiminated 2024"
                ]
            }
        ],
        "TV Shows": [
            {
                "category_name": "Country",
                "pin_count": 1,
                "collections": [
                    "Best UK TV Shows",
                    "Best US TV Shows",
                    "🇦🇺 Austrailain TV Shows",
                    "Best of British"
                ]
            }
        ]
    }
};


export const API_BASE = '/api';