[![Build Status](https://scrutinizer-ci.com/g/jl94x4/ColleXions/badges/build.png?b=main)](https://scrutinizer-ci.com/g/jl94x4/ColleXions/build-status/main) [![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/jl94x4/ColleXions/badges/quality-score.png?b=main)](https://scrutinizer-ci.com/g/jl94x4/ColleXions/?branch=main)

## Preview

**Dark Mode**
![image](https://github.com/user-attachments/assets/9c76e1fc-f18b-43da-89d1-3f1dd64558db)

**Light Mode**

![image](https://github.com/user-attachments/assets/a1564d7b-8d3e-4ab0-acc3-13bf657b82c1)

# ColleXions with Web-UI
ColleXions automates the process of pinning collections to your Plex home screen, making it easier to showcase your favorite content. With customizable features, it enhances your Plex experience by dynamically adjusting what is displayed either controlled or completely randomly - the choice is yours. All options are configurable with a Web-UI.
Includes collaboration with @[defluophoenix](https://github.com/jl94x4/ColleXions/commits?author=defluophoenix)

## Key Features
- **Randomized Pinning:** ColleXions randomly selects collections to pin each cycle, ensuring that your home screen remains fresh and engaging. This randomness prevents the monotony of static collections, allowing users to discover new content easily.

- **Special Occasion Collections:** Automatically prioritizes collections linked to specific dates, making sure seasonal themes are highlighted when appropriate.

- **Exclusion List:** Users can specify collections to exclude from pinning, ensuring that collections you don't want to see on the home screen are never selected. This is also useful if you manually pin items to your homescreen and do not want this tool to interfere with those.

  - **Regex Filtered Exclusion:** Uses regex to filter out keywords that are specified in the config file, ColleXions will automatically exclude any collection that have the specific keyword listed in the title.

- **Label Support:** Collexions will add a label (user defined in config) to each collection that is pinned, and will remove the collection when unpinned. This is great for Kometa support with labels.

- **Inclusion List:** Users can specify collections to include from pinning, ensuring full control over the collections you see on your home screen.

- **Customizable Settings:** Users can easily adjust library names, pinning intervals, and the number of collections to pin, tailoring the experience to their preferences.

- **Categorize Collections:** Users can put collections into categories to ensure a variety of collection are chosen if some are too similar

- **Collection History:** Collections are remembered so they don't get chosen too often

## Include & Exclude Collections

- **Exclude Collections:** The exclusion list allows you to specify collections that should never be pinned or unpinned by ColleXions. These collections are "blacklisted," meaning that even if they are randomly selected or included in the special collections, they will be skipped, any collections you have manually pinned that are in this list will not be unpinned either. This is especially useful if you have "Trending" collections that you wish to be pinned to your home screen at all times.

- **Include Collections:** The inclusion list is the opposite of the exclusion list. It allows you to specify exactly which collections should be considered for pinning. This gives you control over which collections can be pinned, filtering the selection to only a few curated options. Make sure ```"use_inclusion_list": false,``` is set appropriately for your use case.

## How Include & Exclude Work Together 

- If the inclusion list is enabled (i.e., use_inclusion_list is set to True), ColleXions will only pick collections from the inclusion list. Special collections are added if they are active during the date range.

- If no inclusion list is provided, ColleXions will attempt to pick collections randomly from the entire library while respecting the exclusion list. The exclusion list is always active and prevents specific collections from being pinned.

- If the inclusion list is turned off or not defined (use_inclusion_list is set to False or missing), the exclusion list will still be honored, ensuring that any collections in the exclusion list are never pinned.

## Collection Priority Enforcement

The ColleXions tool organizes pinned collections based on a defined priority system to ensure important or seasonal collections are featured prominently:

- **Special Collections First:** Collections marked as special (e.g., seasonal or themed collections) are prioritized and pinned first, these typically are collections that have a start and an end date.

- **Category-Based Collections:** After special collections are pinned, ColleXions will then fill any remaining slots with collections from specified categories, if defined in the config.

- **Random Selections:** If there are still available slots after both special and category-based collections have been selected, random collections from each library are pinned to fill the remaining spaces.

If no special collections or categories are defined, ColleXions will automatically fill all slots with random collections, ensuring your library's home screen remains populated with the amounts specified in your config.

## Selected Collections

A file titled ``selected_collections.json`` is created on first run and updated each run afterwards and keeps track of what's been selected to ensure collections don't get picked repeatedly leaving other collections not being pinned as much. It resets after 3 days so hopefully you will only see a collection once every three days at most. This will depend on the amount of collections you have available and the amount you are asking ColleXions to pin will also play a part.

## Installation
## Docker Run

> docker run -d \
>   --name collexions-webui \
>   -p 5000:5000 \
>   -v /path/to/files/config:/app/config \
>   -v /path/to/files/logs:/app/logs \
>   -v /path/to/files:/app/data \
>   --restart unless-stopped \
>   jl94x4/collexions-web:latest

## Docker Compose

<coming soon>

> [!TIP]
> pinning_interval is in minutes

## Discord Webhooks (optional)

ColleXions now includes a Discord Webhook Integration feature. This enhancement enables real-time notifications directly to your designated Discord channel whenever a collection is pinned to the Home and Friends' Home screens.

**Configuration:** Include your Discord webhook URL in the ```config.json``` file.

**Notifications:** Every time a collection is successfully pinned, the tool sends a formatted message to the specified Discord channel, highlighting the collection name in bold.

This feature helps you keep track of which collections are being pinned, allowing for easy monitoring and tweaks to ensure diversity and relevance.

## Logging

After every run ```collexions.log``` will be created with a full log of the last successful run. It will be overwritten on each new run.

## Acknowledgments
Thanks to the PlexAPI library and the open-source community for their support.
Thanks to defluophoenix for the additional work they've done on this

## License
This project is licensed under the MIT License.
