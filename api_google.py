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
        "snippet": item['snippet'],
        "link": item['link']
    } for item in results['items']]

async def searchimages(query,num=1,page=1):
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    results = service.cse().list(q=query, cx=GOOGLE_CX_ID, num=num, searchType="image", start=page).execute()
    return [{
        "title": item['title'],
        "link": item['link']
    } for item in results['items']]
