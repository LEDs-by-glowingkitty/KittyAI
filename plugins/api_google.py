from googleapiclient.discovery import build
import googlemaps

async def search(google_api_key,google_cx_id,query,num_results=1,page=1):
    service = build("customsearch", "v1", developerKey=google_api_key)
    results = service.cse().list(q=query, cx=google_cx_id, num=num_results, start=page).execute()
    return [{
        "title": item['title'],
        "description": item['snippet'],
        "link": item['link'],
        "thumbnail": item['pagemap']['cse_thumbnail'][0]['src'] if 'cse_thumbnail' in item['pagemap'] else ""
    } for item in results['items']]

async def searchimages(google_api_key,google_cx_id,query,num_results=1,page=1):
    service = build("customsearch", "v1", developerKey=google_api_key)
    results = service.cse().list(q=query, cx=google_cx_id, num=num_results, searchType="image", start=page).execute()
    return [{
        "title": item['title'],
        "image": item['link'],
        "source": item['image']['contextLink'],
        # get filename based on combining file ending with title in lowercase and replacing spaces with underscores and removing all other special characters
        "filename": item['title'].lower().replace(" ","_").replace(".","").replace(",","").replace(":","").replace(";","").replace("?","").replace("!","").replace("(","").replace(")","").replace("[","").replace("]","").replace("{","").replace("}","").replace("-","_").replace("+","_").replace("=","_").replace("/","_").replace("\\","_").replace("|","_").replace("*","_").replace("&","_").replace("%","_").replace("$","_").replace("#","_").replace("@","_")+"."+item['link'].split(".")[-1]
        
    } for item in results['items']]

async def searchvideos(google_api_key,query, num_results=1, page=1,order="relevance",regionCode="US",relevanceLanguage="en"):
    youtube = build("youtube", "v3", developerKey=google_api_key)

    results = youtube.search().list(
        q=query,
        part="id,snippet",
        type="video",
        maxResults=num_results,
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


async def searchlocations(google_api_key,query, where, open_now=False, num_results=1, page=1,):
    gmaps = googlemaps.Client(key=google_api_key)
    # search the first result
    results = gmaps.places(query+" in "+where,open_now=open_now)

    # return the name, photo, address, rating, link and opening hours of the results
    return [{
        "title": item['name'],
        "photo_reference": item['photos'][0]['photo_reference'] if 'photos' in item else "",
        "address": item['formatted_address'],
        "rating": item['rating'],
        "link": "https://www.google.com/maps/search/?api=1&query=Google&query_place_id="+item['place_id'],
        "open_now": item['opening_hours']['open_now'] if 'opening_hours' in item else None
    } for item in results['results'][:num_results]]
