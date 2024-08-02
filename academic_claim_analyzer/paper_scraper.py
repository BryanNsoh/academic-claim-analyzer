import asyncio
import random
import aiohttp
from playwright.async_api import async_playwright
from fake_useragent import UserAgent
import logging
import sys
import json
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse

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
            self.scrape_with_playwright,
            self.scrape_pdf
        ]

        results = []
        for method in scraping_methods:
            content = await method(normalized_url, max_retries)
            word_count = len(content.split())
            results.append((content, word_count))
            if word_count >= min_words:
                self.logger.info(f"Successfully scraped URL: {normalized_url}")
                return content

        # If all methods fail to meet the minimum word count, return the longest result
        longest_content = max(results, key=lambda x: x[1])[0]
        self.logger.warning(f"Failed to meet minimum word count for URL: {normalized_url}")
        return longest_content

    async def scrape_with_requests(self, url, max_retries):
        for _ in range(max_retries):
            try:
                response = requests.get(url, headers={"User-Agent": self.user_agent.random})
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser")
                    main_content = soup.find("div", id="abstract") or soup.find("main") or soup.find("body")
                    if main_content:
                        for script in main_content(["script", "style"]):
                            script.decompose()
                        return main_content.get_text(separator="\n", strip=True)
            except Exception as e:
                self.logger.error(f"Error in scrape_with_requests: {str(e)}")
            await asyncio.sleep(random.uniform(1, 3))
        return ""

    async def scrape_with_playwright(self, url, max_retries):
        if not self.browser:
            await self.initialize()

        for _ in range(max_retries):
            try:
                context = await self.browser.new_context(
                    user_agent=self.user_agent.random,
                    viewport={"width": 1920, "height": 1080},
                    ignore_https_errors=True,
                )
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=60000)
                content = await self.extract_text_content(page)
                await page.close()
                return content
            except Exception as e:
                self.logger.error(f"Error in scrape_with_playwright: {str(e)}")
            await asyncio.sleep(random.uniform(1, 3))
        return ""

    async def scrape_pdf(self, url, max_retries):
        for _ in range(max_retries):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        pdf_bytes = await response.read()
                        return self.extract_text_from_pdf(pdf_bytes)
            except Exception as e:
                self.logger.error(f"Error in scrape_pdf: {str(e)}")
            await asyncio.sleep(random.uniform(1, 3))
        return ""

    async def extract_text_content(self, page):
        try:
            await page.wait_for_selector("body", timeout=10000)
            text_content = await page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, td, th');
                    return Array.from(elements).map(element => element.innerText).join(' ');
                }
            """)
            return text_content.strip()
        except Exception as e:
            self.logger.error(f"Failed to extract text content. Error: {str(e)}")
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

        scrape_tasks = [asyncio.create_task(scraper.scrape(url)) for url in urls]
        scraped_contents = await asyncio.gather(*scrape_tasks)

        success_count = 0
        failure_count = 0

        print("\nScraping Results:\n" + "=" * 80)
        for url, content in zip(urls, scraped_contents):
            word_count = len(content.split())
            if word_count >= 700:
                first_100_words = " ".join(content.split()[:100])
                print(f"\nURL: {url}\nStatus: Success\nWord count: {word_count}\nFirst 100 words: {first_100_words}\n" + "-" * 80)
                success_count += 1
            else:
                print(f"\nURL: {url}\nStatus: Failure (insufficient words)\nWord count: {word_count}\n" + "-" * 80)
                failure_count += 1

        print("\nSummary:\n" + "=" * 80)
        print(f"Total URLs scraped: {len(urls)}")
        print(f"Successful scrapes: {success_count}")
        print(f"Failed scrapes: {failure_count}")

        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())