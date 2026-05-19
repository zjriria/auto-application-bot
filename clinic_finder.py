import argparse
import requests
import pandas as pd
import time
import re

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/cgi/interpreter",
]
HTTP_HEADERS = {"User-Agent": "pflegefachmann-bewerbung/1.0 (contact: automation)"}


def _resolve_area_id(city_name):
    """Resolve a city/state name to an Overpass area id via Nominatim."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": city_name, "format": "json", "addressdetails": 1, "limit": 1},
            headers=HTTP_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"⚠️ Failed to resolve area id for {city_name}: {exc}")
        return None

    if not payload:
        return None

    entry = payload[0]
    osm_id = entry.get("osm_id")
    osm_type = entry.get("osm_type")

    if not osm_id or not osm_type:
        return None

    offsets = {"relation": 3600000000, "way": 2400000000, "node": 1600000000}
    offset = offsets.get(osm_type)
    if offset is None:
        return None

    return offset + int(osm_id)

def find_care_facilities(city_name):
    print(f"🌍 Querying OpenStreetMap for medical and care facilities in {city_name}...")

    area_id = _resolve_area_id(city_name)
    if not area_id:
        print("⚠️ Unable to locate that region in OpenStreetMap. Try a different spelling or nearby metro area.")
        return []

    overpass_query = f"""
    [out:json][timeout:50];
    area({area_id})->.searchArea;
    (
      node["amenity"="hospital"](area.searchArea);
      way["amenity"="hospital"](area.searchArea);
      relation["amenity"="hospital"](area.searchArea);
      node["amenity"="nursing_home"](area.searchArea);
      way["amenity"="nursing_home"](area.searchArea);
      relation["amenity"="nursing_home"](area.searchArea);
      node["amenity"="clinic"](area.searchArea);
      way["amenity"="clinic"](area.searchArea);
      relation["amenity"="clinic"](area.searchArea);
    );
    out tags;
    """

    data = None
    for idx, endpoint in enumerate(OVERPASS_URLS, start=1):
        try:
            response = requests.post(endpoint, data={'data': overpass_query}, headers=HTTP_HEADERS, timeout=50)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            print(f"⚠️ Overpass endpoint {idx} failed: {e}")
            time.sleep(2)

    if data is None:
        print("⚠️ All Overpass endpoints failed. Try again later or adjust the search term.")
        return []

    facilities = []
    
    # Parse the JSON response to extract the useful data
    for element in data.get('elements', []):
        tags = element.get('tags', {})
        
        # We only want facilities that actually have a website, 
        # otherwise our email scraper can't do its job!
        name = tags.get('name')
        website = tags.get('website') or tags.get('contact:website')
        
        if name and website:
            # Clean up the website URL if necessary
            if not website.startswith('http'):
                website = 'https://' + website
                
            facilities.append({
                "Clinic Name": name,
                "URL": website,
                "City": city_name
            })
            
    # Remove duplicates based on URL
    unique_facilities = {fac['URL']: fac for fac in facilities}.values()
    return list(unique_facilities)

def _slugify_city(name):
    slug = name.lower().strip()
    slug = slug.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def main():
    parser = argparse.ArgumentParser(description="Find clinics with websites for downstream email scraping.")
    parser.add_argument("--city", default="Sachsen", help="City or federal state name to search via Overpass (default: Sachsen)")
    parser.add_argument("--output", help="Optional explicit Excel output path. Defaults to found_clinics_<city>.xlsx")
    args = parser.parse_args()

    target_city = args.city
    print("🤖 Booting up Clinic Finder Bot...")
    results = find_care_facilities(target_city)

    if results:
        print(f"✅ Successfully found {len(results)} facilities with websites in {target_city}!")

        df = pd.DataFrame(results)
        filename = args.output or f"found_clinics_{_slugify_city(target_city)}.xlsx"
        df.to_excel(filename, index=False)
        print(f"📁 Saved to {filename}")

        print("\nPreview of found leads:")
        print(df.head())
    else:
        print(f"❌ No facilities with websites found in {target_city}. Try a larger city.")


if __name__ == "__main__":
    main()
