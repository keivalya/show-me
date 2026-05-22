import os
import requests
import logging

logger = logging.getLogger(__name__)

CHANNEL_ALLOWLIST = [
    "UCG36_h6K8pSByUIsTz-fRWA", # Example official channel
    # Manufacturer official channels
    "UCn6U-iN_S2_D_L8oZ1A5kIg", # Keurig
    "UCq4N26i_iS7yv0-S2M9LpEw", # Nespresso
]

class YouTubeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def search_repair_video(self, make, model, symptom):
        query = f"{make} {model} {symptom} repair fix"
        logger.info(f"Searching YouTube for: {query}")
        
        params = {
            "part": "snippet",
            "q": query,
            "maxResults": 5,
            "type": "video",
            "videoEmbeddable": "true",
            "key": self.api_key
        }
        
        try:
            response = requests.get(f"{self.base_url}/search", params=params)
            response.raise_for_status()
            items = response.json().get("items", [])
            
            results = []
            for item in items:
                results.append({
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"]
                })
            return results
        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return []
