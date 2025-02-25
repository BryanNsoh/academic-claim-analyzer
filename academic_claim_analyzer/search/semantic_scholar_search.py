# semantic_scholar_search.py
import os
import logging
import asyncio
from typing import List, Optional, Dict

import aiohttp
import fitz  # PyMuPDF for PDF parsing

from .base import BaseSearch
from ..models import Paper


class SemanticScholarSearch(BaseSearch):
    """
    A search module integrating with the Semantic Scholar API.

    Rate limits per the official info (simplified):
      - Unauthenticated usage (no API key):
          * All anonymous users share a global pool ~5000 requests / 5 minutes (16.7 req/sec total).
          * We can't know how many anonymous users are there, so let's do ~1 request every 2s
            plus exponential backoff if we see 429. This is more conservative than 16.7 req/sec
            and reduces collisions.
      - Authenticated usage (with an API key):
          * /paper/search endpoint allows ~1 request/second per key.
          * We'll do 1 request every 1s plus exponential backoff on 429.

    We do:
      1. For each search page, we respect the basic delay between requests (1 or 2s).
      2. If we get 429, we retry up to 5 times with exponential backoff (2, 4, 8, 16, 32s).
      3. Once results are fetched, we concurrently download PDF files (no concurrency limit).
         Because PDF fetches are not restricted as heavily by the search endpoint's strict 1 rps.
      4. Return partial results if we exhaust retries or fail mid-search.
    """

    SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self):
        """
        Constructor. We optionally read an API key from the environment variable
        'SEMANTIC_SCHOLAR_KEY' to use authenticated searches if available.
        """
        self.api_key = os.environ.get("SEMANTIC_SCHOLAR_KEY", None)

    async def search(self, query: str, limit: int) -> List[Paper]:
        """
        Perform a Semantic Scholar search for 'query', returning up to 'limit' results.

        Each Paper includes:
          - title, authors, year, doi, abstract, pdf_link, full_text (if PDF parse works),
            and metadata (e.g., citationCount, s2_paper_id).

        We'll fetch in pages of up to 100, halting at offset=1000 or after 'limit' is reached.
        Then we'll fetch PDFs (where available) concurrently with no explicit concurrency limit.
        """
        all_papers: List[Paper] = []
        offset = 0

        # Decide normal delay between successive search requests
        if self.api_key:
            delay_between_requests = 1.0  # 1 request/sec if authenticated
        else:
            delay_between_requests = 2.0  # 1 request every 2s if unauthenticated

        while len(all_papers) < limit and offset < 1000:
            to_fetch = min(100, limit - len(all_papers))
            data = await self._fetch_search_page(query, offset, to_fetch)
            if not data:
                # If we got None or an empty result, stop
                break

            papers_json = data.get("data", [])
            if not papers_json:
                break

            new_papers = self._json_to_papers(papers_json)
            all_papers.extend(new_papers)

            if "next" in data:
                offset = data["next"]
            else:
                break

            if offset >= 1000:
                # The /paper/search endpoint doesn't go beyond offset=1000
                break

            # Basic pacing to avoid immediate 429
            await asyncio.sleep(delay_between_requests)

        # Download/parse PDFs in parallel (unbounded concurrency)
        tasks = []
        for p in all_papers:
            if p.pdf_link:
                tasks.append(self._fetch_and_parse_pdf(p))
        if tasks:
            await asyncio.gather(*tasks)

        return all_papers[:limit]

    async def _fetch_search_page(self, query: str, offset: int, limit: int) -> Optional[dict]:
        """
        Fetches one page of results from the Semantic Scholar search API, with up to 5 retries
        on 429 or exceptions (exponential backoff).
        Returns the parsed JSON, or None if it fails after 5 attempts.
        """
        params = {
            "query": query,
            "offset": offset,
            "limit": limit,
            "fields": "title,authors,year,abstract,externalIds,citationCount,openAccessPdf"
        }
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        max_retries = 5
        backoff_seconds = 2.0

        for attempt in range(1, max_retries + 1):
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        self.SEMANTIC_SCHOLAR_SEARCH_URL,
                        params=params,
                        headers=headers,
                        timeout=30
                    ) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        elif resp.status == 429:
                            # Rate-limit encountered
                            if attempt < max_retries:
                                logging.warning(
                                    f"429 from Semantic Scholar. Attempt {attempt}/{max_retries}."
                                    f" Sleeping {backoff_seconds}s before retry..."
                                )
                                await asyncio.sleep(backoff_seconds)
                                backoff_seconds *= 2
                                continue
                            else:
                                logging.warning("429 on final retry; giving up.")
                                return None
                        elif resp.status in (401, 403):
                            logging.warning(f"Unauthorized/Forbidden ({resp.status}).")
                            return None
                        else:
                            text = await resp.text()
                            logging.warning(
                                f"Unexpected status {resp.status} from Semantic Scholar. Body: {text}"
                            )
                            return None
                except Exception as ex:
                    logging.error(
                        f"Exception on attempt {attempt}/{max_retries} for offset {offset}: {ex}"
                    )
                    if attempt < max_retries:
                        logging.warning(
                            f"Retrying in {backoff_seconds}s (exponential backoff)."
                        )
                        await asyncio.sleep(backoff_seconds)
                        backoff_seconds *= 2
                        continue
                    else:
                        return None

        return None

    def _json_to_papers(self, papers_json: List[dict]) -> List[Paper]:
        """
        Converts a list of JSON records from Semantic Scholar into Paper objects.
        """
        results: List[Paper] = []
        for item in papers_json:
            title = item.get("title", "")
            year = item.get("year", 0) or 0
            abstract = item.get("abstract", "") or ""

            authors_raw = item.get("authors", [])
            authors = [a.get("name", "") for a in authors_raw if "name" in a]

            external_ids = item.get("externalIds", {})
            doi = external_ids.get("DOI", "") or item.get("paperId", "")

            pdf_link = None
            oapdf = item.get("openAccessPdf", {})
            if isinstance(oapdf, dict):
                pdf_link = oapdf.get("url")

            metadata: Dict[str, str] = {}
            if "citationCount" in item:
                metadata["citationCount"] = str(item["citationCount"])
            if "paperId" in item:
                metadata["s2_paper_id"] = item["paperId"]

            paper_obj = Paper(
                title=title,
                authors=authors,
                year=year,
                doi=doi,
                abstract=abstract,
                pdf_link=pdf_link,
                metadata=metadata
            )
            results.append(paper_obj)
        return results

    async def _fetch_and_parse_pdf(self, paper: Paper) -> None:
        """
        Fetch and parse the PDF for the given paper. We'll do this concurrently
        without bounding concurrency in the code (i.e., no semaphore).
        If the fetch or parse fails, we log a warning and leave full_text as None.
        """
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(paper.pdf_link, timeout=60) as resp:
                    if resp.status == 200:
                        pdf_bytes = await resp.read()
                        try:
                            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                                extracted_texts = [page.get_text() for page in doc]
                            paper.full_text = "\n".join(extracted_texts)
                        except Exception as parse_err:
                            logging.warning(
                                f"Failed to parse PDF for '{paper.title}': {parse_err}"
                            )
                    else:
                        logging.warning(
                            f"PDF download failed (status {resp.status}) for '{paper.title}'. "
                            "Keeping only the abstract."
                        )
            except Exception as e:
                logging.warning(
                    f"Exception fetching PDF for '{paper.title}' from '{paper.pdf_link}': {e}"
                )
