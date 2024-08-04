import os
import re
import asyncio
import random
import aiohttp
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from fake_useragent import UserAgent
import logging
import sys
import json
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse
from markdownify import markdownify as md

class UnifiedWebScraper:
    def __init__(self, session, max_concurrent_tasks=5):
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.user_agent = UserAgent()
        self.browser = None
        self.session = session
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.logger.info("Browser initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {str(e)}")
            raise

    async def close(self):
        if self.browser:
            await self.browser.close()
            self.logger.info("Browser closed")

    def normalize_url(self, url):
        if url.startswith("10.") or url.startswith("doi:"):
            return f"https://doi.org/{url.replace('doi:', '')}"
        parsed = urlparse(url)
        if not parsed.scheme:
            return f"http://{url}"
        return url

    async def scrape(self, url, min_words=700, max_retries=3):
        normalized_url = self.normalize_url(url)
        self.logger.info(f"Attempting to scrape URL: {normalized_url}")

        scraping_methods = [
            self.scrape_with_requests,
            self.scrape_with_playwright
        ]

        if normalized_url.lower().endswith('.pdf'):
            scraping_methods.append(self.scrape_pdf)

        best_result = ("", 0)
        for method in scraping_methods:
            self.logger.info(f"Trying method: {method.__name__}")
            for attempt in range(max_retries):
                try:
                    self.logger.info(f"Attempt {attempt + 1} with {method.__name__}")
                    content = await method(normalized_url)
                    word_count = len(content.split())
                    self.logger.info(f"Got {word_count} words from {method.__name__}")
                    if word_count > best_result[1]:
                        best_result = (content, word_count)
                    if word_count >= min_words:
                        self.logger.info(f"Successfully scraped URL: {normalized_url}")
                        return content
                except Exception as e:
                    self.logger.error(f"Error in {method.__name__} (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = random.uniform(1, 3)
                    self.logger.info(f"Waiting {wait_time:.2f} seconds before next attempt")
                    await asyncio.sleep(wait_time)

        self.logger.warning(f"Failed to meet minimum word count for URL: {normalized_url}")
        return best_result[0]

    async def scrape_with_requests(self, url):
        self.logger.info(f"Scraping with requests: {url}")
        response = requests.get(url, headers={"User-Agent": self.user_agent.random})
        if response.status_code == 200:
            return md(response.text)
        return ""

    async def scrape_with_playwright(self, url):
        self.logger.info(f"Scraping with Playwright: {url}")
        if not self.browser:
            await self.initialize()
        context = await self.browser.new_context(
            user_agent=self.user_agent.random,
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
            content = await page.content()
            return md(content)
        except PlaywrightTimeoutError:
            self.logger.warning(f"Timeout occurred while loading {url}")
            return ""
        finally:
            await page.close()

    async def scrape_pdf(self, url):
        self.logger.info(f"Scraping PDF: {url}")
        async with self.session.get(url) as response:
            if response.status == 200:
                pdf_bytes = await response.read()
                return self.extract_text_from_pdf(pdf_bytes)
        return ""

    def extract_text_from_pdf(self, pdf_bytes):
        try:
            document = fitz.open("pdf", pdf_bytes)
            text = ""
            for page in document:
                text += page.get_text()
            return text.strip()
        except Exception as e:
            self.logger.error(f"Failed to extract text from PDF. Error: {str(e)}")
            return ""

def sanitize_filename(url):
    # Remove the protocol and www. if present
    url = re.sub(r'^https?://(www\.)?', '', url)
    # Replace non-alphanumeric characters with underscores
    filename = re.sub(r'[^\w\-_\.]', '_', url)
    # Truncate if too long (max 255 characters for most file systems)
    return filename[:255] + '.md'

async def main():
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler("scraper.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    output_folder = r"C:\Users\bnsoh2\Desktop\test"
    os.makedirs(output_folder, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        scraper = UnifiedWebScraper(session=session)
        try:
            await scraper.initialize()
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            return

        urls = [
            "10.1016/j.ifacol.2020.12.237",
            "10.1016/j.agwat.2023.108536",
            "10.1016/j.atech.2023.100251",
            "10.1016/j.atech.2023.100179",
            "10.1016/j.ifacol.2023.10.677",
            "10.1016/j.ifacol.2023.10.1655",
            "10.1016/j.ifacol.2023.10.667",
            "10.1002/cjce.24764",
            "10.3390/app13084734",
            "10.1016/j.atech.2022.100074",
            "10.1007/s10668-023-04028-9",
            "10.1109/IJCNN54540.2023.10191862",
            "10.1201/9780429290152-5",
            "10.1016/j.jprocont.2022.10.003",
            "10.1016/j.rser.2022.112790",
            "10.1007/s11269-022-03191-4",
            "10.3390/app12094235",
            "10.3390/w14060889",
            "10.3390/su14031304",
        ]

        success_count = 0
        failure_count = 0

        for url in urls:
            try:
                content = await scraper.scrape(url)
                word_count = len(content.split())
                
                normalized_url = scraper.normalize_url(url)
                filename = sanitize_filename(normalized_url)
                file_path = os.path.join(output_folder, filename)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                if word_count >= 700:
                    print(f"\nURL: {url}\nStatus: Success\nWord count: {word_count}\nSaved as: {filename}\n" + "-" * 80)
                    success_count += 1
                else:
                    print(f"\nURL: {url}\nStatus: Failure (insufficient words)\nWord count: {word_count}\nSaved as: {filename}\n" + "-" * 80)
                    failure_count += 1
            
            except Exception as e:
                print(f"\nURL: {url}\nStatus: Error\nError message: {str(e)}\n" + "-" * 80)
                failure_count += 1

        print("\nSummary:\n" + "=" * 80)
        print(f"Total URLs scraped: {len(urls)}")
        print(f"Successful scrapes: {success_count}")
        print(f"Failed scrapes: {failure_count}")
        print(f"Results saved in: {output_folder}")

        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())