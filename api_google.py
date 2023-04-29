from googleapiclient.discovery import build
import os
from dotenv import load_dotenv
load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CX_ID = os.getenv('GOOGLE_CX_ID')


async def search(query,num=1,page=1):
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    results = service.cse().list(q=query, cx=GOOGLE_CX_ID, num=num, start=page).execute()
    return [{
        "title": item['title'],
        "description": item['snippet'],
        "link": item['link'],
        "thumbnail": item['pagemap']['cse_thumbnail'][0]['src'] if 'cse_thumbnail' in item['pagemap'] else ""
    } for item in results['items']]

async def searchimages(query,num=1,page=1):
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    results = service.cse().list(q=query, cx=GOOGLE_CX_ID, num=num, searchType="image", start=page).execute()
    return [{
        "title": item['title'],
        "image": item['link'],
        "source": item['image']['contextLink'],
        "filename": item['link'].split("/")[-1]
    } for item in results['items']]

async def searchvideos(query, num=1, page=1,order="relevance",regionCode="US",relevanceLanguage="en"):
    youtube = build("youtube", "v3", developerKey=GOOGLE_API_KEY)

    results = youtube.search().list(
        q=query,
        part="id,snippet",
        type="video",
        maxResults=num,
        order=order,
        regionCode=regionCode,
        relevanceLanguage=relevanceLanguage
    ).execute()

    return [{
        "title": item['snippet']['title'],
        "description": item['snippet']['description'],
        "thumbnail": item['snippet']['thumbnails']['high']['url'],
        "link": "https://www.youtube.com/watch?v="+item['id']['videoId']
    } for item in results['items']]
