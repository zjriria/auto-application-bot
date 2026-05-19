import asyncio
import re
import random
from pathlib import Path
import pandas as pd
from playwright.async_api import async_playwright, Page

CSV_FILE = "applications.csv"
SEARCH_TERMS = ["Ausbildung zum Fachinformatiker"]
BASE_URL = "https://www.stepstone.de"

async def random_delay(min_sec=2, max_sec=5):
    """Mimic human behavior with random delays."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)

async def accept_cookies(page: Page):
    """Attempt to click common German GDPR cookie banner buttons."""
    print("Looking for cookie banners...")
    try:
        cookie_selectors = [
            "button:has-text('Alle Akzeptieren')",
            "button:has-text('Zustimmen')",
            "button:has-text('Akzeptieren')",
            "button#ccmgt_explicit_accept",
            "[data-genesis-element='button']:has-text('Alle akzeptieren')"
        ]
        for selector in cookie_selectors:
            elements = await page.locator(selector).all()
            for el in elements:
                if await el.is_visible():
                    await el.click()
                    print(f"Cookie banner accepted via selector: {selector}")
                    await random_delay(1, 2)
                    return
    except Exception as e:
        print(f"Cookie banner handling error (can be ignored if no banner): {e}")

def extract_email(text):
    """Extract email address from text using regex."""
    if not text:
        return None
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_regex, text)
    if match:
        return match.group(0)
    return None

async def scrape_job_details(page: Page, url: str):
    """Navigate to the job posting and find contact email/method."""
    print(f"Scraping details for: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await random_delay(2, 4)
        
        # Attempt to find location in the header usually
        location = "Unknown"
        loc_elements = await page.locator("[data-genesis-element='text']:has-text('Ort'), .job-location, .listing-location").all()
        for loc in loc_elements:
            if await loc.is_visible():
                location = await loc.inner_text()
                break
                
        # Extract entire page text to find email
        page_text = await page.locator("body").inner_text()
        email = extract_email(page_text)
        
        if email:
            return email, "Email", location
        else:
            return None, "Portal", location
    except Exception as e:
        print(f"Failed to scrape details from {url}: {e}")
        return None, "Portal", "Unknown"

async def scrape_stepstone():
    # Load existing CSV to prevent duplicates
    if Path(CSV_FILE).exists():
        try:
            df_existing = pd.read_csv(CSV_FILE)
            existing_urls = set(df_existing['Job URL'].tolist())
        except pd.errors.EmptyDataError:
            existing_urls = set()
    else:
        existing_urls = set()
        
    results = []

    async with async_playwright() as p:
        # Launching with headless=False can help avoid basic bot detections
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            locale="de-DE"
        )
        page = await context.new_page()

        for term in SEARCH_TERMS:
            print(f"=== Searching for: {term} ===")
            search_url = f"{BASE_URL}/jobs/{term.replace(' ', '-')}?action=facet_selected"
            try:
                await page.goto(search_url, wait_until="domcontentloaded")
            except Exception as e:
                print(f"Failed to load search page: {e}")
                continue
                
            await random_delay(3, 5)
            await accept_cookies(page)
            
            # StepStone job cards
            job_cards = await page.locator("article").all()
            print(f"Found {len(job_cards)} job cards on the first page.")
            
            jobs_to_process = []
            
            for card in job_cards:
                try:
                    link_el = card.locator("a").first
                    if await link_el.count() == 0:
                        continue
                        
                    url_path = await link_el.get_attribute("href")
                    if not url_path:
                        continue
                        
                    full_url = url_path if url_path.startswith("http") else f"{BASE_URL}{url_path}"
                    
                    if full_url in existing_urls:
                        continue
                        
                    # Basic extraction from card
                    title_el = card.locator("h2, h3, [data-genesis-element='text']").first
                    title = await title_el.inner_text() if await title_el.count() > 0 else "Unknown Title"
                    
                    jobs_to_process.append({
                        "Job Title": title,
                        "Company/Klinik": "See Details",  # Will refine in details
                        "Job URL": full_url,
                        "Search Term": term
                    })
                    
                except Exception as e:
                    print(f"Error parsing job card: {e}")
            
            # Process job details for the new ones found
            for job in jobs_to_process:
                email, method, location = await scrape_job_details(page, job["Job URL"])
                
                # Attempt to get company name from details page title or generic class
                company = "Unknown"
                try:
                    title_text = await page.title()
                    # Often "Job Title bei Company"
                    if " bei " in title_text:
                        company = title_text.split(" bei ")[-1].split(" |")[0].strip()
                except:
                    pass

                job["Company/Klinik"] = company if company != "Unknown" else job["Company/Klinik"]
                job["Location"] = location
                job["Application Method"] = method
                job["Contact Email"] = email
                job["Status"] = "Pending"
                
                results.append(job)
                existing_urls.add(job["Job URL"])
                
                print(f"--> Extracted: {job['Job Title']} at {job['Company/Klinik']} | Method: {method}")
                await random_delay(2, 4)

        await browser.close()

    # Save to CSV
    if results:
        df_new = pd.DataFrame(results)
        # Ensure column order matches user requirements
        cols = ["Job Title", "Company/Klinik", "Job URL", "Location", "Application Method", "Contact Email", "Status", "Search Term"]
        df_new = df_new[cols]
        
        if Path(CSV_FILE).exists():
            df_new.to_csv(CSV_FILE, mode='a', header=False, index=False)
        else:
            df_new.to_csv(CSV_FILE, index=False)
        print(f"\nSuccessfully added {len(results)} new jobs to {CSV_FILE}.")
    else:
        print("\nNo new jobs found or all existing URLs.")

if __name__ == "__main__":
    asyncio.run(scrape_stepstone())
