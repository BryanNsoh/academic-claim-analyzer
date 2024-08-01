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
from urllib.parse import urlparse, urljoin

class WebScraper:
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
        if url.startswith("10."):
            return f"https://doi.org/{url}"
        elif url.startswith("doi:"):
            return f"https://doi.org/{url[4:]}"
        elif not url.startswith("http"):
            return f"https://{url}"
        return url

    async def scrape_url(self, url, max_retries=3):
        normalized_url = self.normalize_url(url)
        self.logger.info(f"Attempting to scrape URL: {normalized_url}")
        
        if normalized_url.lower().endswith(".pdf"):
            return await self.scrape_pdf(normalized_url, max_retries)
        else:
            return await self.scrape_web_page(normalized_url, max_retries)

    async def scrape_web_page(self, url, max_retries=3):
        if not self.browser:
            await self.initialize()

        retry_count = 0
        page = None
        while retry_count < max_retries:
            try:
                # Attempt with requests and BeautifulSoup first
                content = await self.extract_content_with_requests(url)
                if content and "You are accessing a machine-readable page" not in content and len(content.split()) > 200:
                    self.logger.info(f"Successfully scraped URL with requests: {url}")
                    return content

                context = await self.browser.new_context(
                    user_agent=self.user_agent.random,
                    viewport={"width": 1920, "height": 1080},
                    ignore_https_errors=True,
                    java_script_enabled=True,
                )

                await context.set_extra_http_headers({
                    "User-Agent": self.user_agent.random,
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    "Connection": "keep-alive",
                    "DNT": "1",
                    "Upgrade-Insecure-Requests": "1",
                })

                page = await context.new_page()

                cookies = await self.load_cookies()
                if cookies:
                    await context.add_cookies(cookies)

                await self.navigate_to_url(page, url, max_retries=3)
                content = await self.extract_text_content(page)

                if not content:
                    self.logger.warning(f"No content extracted from {url}. Attempting to follow redirects.")
                    content = await self.follow_redirects(page, url)

                cookies = await context.cookies()
                await self.save_cookies(cookies)

                if content:
                    self.logger.info(f"Successfully scraped URL: {url}")
                    await context.close()
                    return content
                else:
                    raise Exception("No content extracted after following redirects")

            except Exception as e:
                self.logger.error(f"Error occurred while scraping URL: {url}. Error: {str(e)}")
                retry_count += 1
                await asyncio.sleep(random.uniform(1, 3))
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception as e:
                        self.logger.warning(f"Error occurred while closing page: {str(e)}")

        self.logger.warning(f"Max retries exceeded for URL: {url}")
        return ""

    async def follow_redirects(self, page, original_url):
        try:
            current_url = await page.evaluate("window.location.href")
            if current_url != original_url:
                self.logger.info(f"Redirected from {original_url} to {current_url}")
                await self.navigate_to_url(page, current_url, max_retries=2)
                return await self.extract_text_content(page)
            return ""
        except Exception as e:
            self.logger.error(f"Error following redirects: {str(e)}")
            return ""

    async def scrape_pdf(self, url, max_retries=3):
        retry_count = 0
        while retry_count < max_retries:
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        pdf_bytes = await response.read()
                        pdf_text = self.extract_text_from_pdf(pdf_bytes)
                        if pdf_text:
                            self.logger.info(f"Successfully scraped PDF URL: {url}")
                            return pdf_text
                        else:
                            raise Exception("Failed to extract text from PDF")
                    else:
                        raise Exception(f"Failed to download PDF, status code: {response.status}")
            except Exception as e:
                self.logger.error(f"Error occurred while scraping PDF URL: {url}. Error: {str(e)}")
                retry_count += 1
                await asyncio.sleep(random.uniform(1, 3))
        self.logger.warning(f"Max retries exceeded for PDF URL: {url}")
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

    async def extract_content_with_requests(self, url):
        try:
            response = requests.get(url, headers={"User-Agent": self.user_agent.random})
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                main_content = soup.find("div", id="abstract") or soup.find("main") or soup.find("body")
                if main_content:
                    for script in main_content(["script", "style"]):
                        script.decompose()
                    content_text = main_content.get_text(separator="\n", strip=True)
                    return content_text
            return ""
        except Exception as e:
            self.logger.error(f"Failed to extract content with requests. Error: {str(e)}")
            return ""

    async def get_url_content(self, url):
        async with self.semaphore:
            return await self.scrape_url(url)

    async def navigate_to_url(self, page, url, max_retries=3):
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=60000)
                if response.ok:
                    await page.wait_for_load_state("load")
                    await asyncio.sleep(2)
                    return
                else:
                    raise Exception(f"Navigation failed with status: {response.status}")
            except Exception as e:
                self.logger.warning(f"Retrying URL: {url}. Remaining retries: {max_retries - retry_count - 1}. Error: {str(e)}")
                retry_count += 1
                await asyncio.sleep(random.uniform(1, 3))
        self.logger.error(f"Failed to navigate to URL: {url} after {max_retries} retries")
        raise Exception(f"Navigation failed for URL: {url}")

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

    async def save_cookies(self, cookies):
        with open("cookies.json", "w") as file:
            json.dump(cookies, file)

    async def load_cookies(self):
        try:
            with open("cookies.json", "r") as file:
                return json.load(file)
        except FileNotFoundError:
            return None

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
        scraper = WebScraper(session=session)
        try:
            await scraper.initialize()
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            return

        urls = [
            "10.1016/j.ifacol.2020.12.237",
            "10.1016/j.agwat.2023.108536",
            "10.1016/j.atech.2023.100251",
            # ... (rest of the URLs)
        ]

        scrape_tasks = [asyncio.create_task(scraper.get_url_content(url)) for url in urls]
        scraped_contents = await asyncio.gather(*scrape_tasks)

        success_count = 0
        failure_count = 0

        print("\nScraping Results:\n" + "=" * 80)
        for url, content in zip(urls, scraped_contents):
            if content:
                first_1000_words = " ".join(content.split()[:1000])
                print(f"\nURL: {url}\nStatus: Success\nFirst 1000 words: {first_1000_words}\n" + "-" * 80)
                success_count += 1
            else:
                print(f"\nURL: {url}\nStatus: Failure\n" + "-" * 80)
                failure_count += 1

        print("\nSummary:\n" + "=" * 80)
        print(f"Total URLs scraped: {len(urls)}")
        print(f"Successful scrapes: {success_count}")
        print(f"Failed scrapes: {failure_count}")

        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())