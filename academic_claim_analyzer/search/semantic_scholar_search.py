# academic_claim_analyzer/search/semantic_scholar_search.py

import os
import logging
import asyncio
from typing import List, Optional, Dict

import aiohttp
import fitz  # PyMuPDF for PDF parsing

from .base import BaseSearch
from ..models import Paper
from ..search.search_config import GlobalSearchConfig, calculate_backoff


class SemanticScholarSearch(BaseSearch):
    """
    A search module integrating with the Semantic Scholar API.
    """

    SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self):
        self.api_key = os.environ.get("SEMANTIC_SCHOLAR_KEY", None)
        # concurrency from global config
        self.semaphore = asyncio.Semaphore(GlobalSearchConfig.semanticscholar_concurrency)

    async def search(self, query: str, limit: int) -> List[Paper]:
        """
        Perform a Semantic Scholar search for 'query', returning up to 'limit' results.
        We'll fetch in pages of up to 100, halting at offset=1000 or after 'limit' is reached.
        Then we'll fetch PDFs (where available) concurrently.
        """
        all_papers: List[Paper] = []
        offset = 0

        # Decide normal delay between successive search requests
        delay_between_requests = 1.0 if self.api_key else 2.0

        while len(all_papers) < limit and offset < 1000:
            to_fetch = min(100, limit - len(all_papers))
            data = await self._fetch_search_page(query, offset, to_fetch)
            if not data:
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
                break

            await asyncio.sleep(delay_between_requests)

        # fetch PDFs in parallel
        tasks = []
        for p in all_papers:
            if p.pdf_link:
                tasks.append(self._fetch_and_parse_pdf(p))
        if tasks:
            await asyncio.gather(*tasks)

        return all_papers[:limit]

    async def _fetch_search_page(self, query: str, offset: int, limit: int) -> Optional[dict]:
        """
        Fetch one page of results from the Semantic Scholar search API,
        with up to max_retries on 429 or exceptions (exponential backoff).
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

        max_attempts = GlobalSearchConfig.max_retries
        backoff_seconds = 2.0

        for attempt in range(max_attempts):
            async with aiohttp.ClientSession() as session:
                async with self.semaphore:
                    try:
                        if attempt > 0:
                            # exponential backoff
                            backoff_time = calculate_backoff(attempt - 1)
                            logging.warning(f"SemanticScholar: Retry fetch page offset={offset}, backoff={backoff_time:.1f}s attempt={attempt}")
                            await asyncio.sleep(backoff_time)

                        async with session.get(
                            self.SEMANTIC_SCHOLAR_SEARCH_URL,
                            params=params,
                            headers=headers,
                            timeout=30
                        ) as resp:
                            if resp.status == 200:
                                return await resp.json()
                            elif resp.status == 429:
                                if attempt < max_attempts - 1:
                                    logging.warning(
                                        f"429 from Semantic Scholar. attempt {attempt}/{max_attempts}."
                                    )
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
                            f"Exception on attempt {attempt}/{max_attempts} for offset {offset}: {ex}"
                        )
                        if attempt < max_attempts - 1:
                            continue
                        else:
                            return None
        return None

    def _json_to_papers(self, papers_json: List[dict]) -> List[Paper]:
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
                authors=authors if authors else ["Unknown Author"],
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
        Download and parse the PDF for the given paper concurrently.
        Up to max_retries with exponential backoff if fails.
        """
        max_attempts = GlobalSearchConfig.max_retries
        for attempt in range(max_attempts):
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
                            return
                        else:
                            logging.warning(
                                f"PDF download failed (status {resp.status}) for '{paper.title}'. "
                            )
                            return
                except Exception as e:
                    logging.warning(
                        f"Exception fetching PDF for '{paper.title}' from '{paper.pdf_link}': {e}"
                    )
                    if attempt < max_attempts - 1:
                        backoff_time = calculate_backoff(attempt)
                        logging.warning(f"SemanticScholar PDF: backoff={backoff_time:.1f}s attempt={attempt}")
                        await asyncio.sleep(backoff_time)
                        continue
                    return
