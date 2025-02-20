# academic_claim_analyzer/search/arxiv_search.py

import aiohttp
import asyncio
import logging
import fitz  # PyMuPDF
import xml.etree.ElementTree as ET
import html
from typing import List, Optional
from .base import BaseSearch
from ..models import Paper

logger = logging.getLogger(__name__)

class ArxivSearch(BaseSearch):
    """
    Perform a search against the arXiv API using natural language queries.

    This class fetches the arXiv RSS/Atom feed, downloads each paper's PDF 
    directly from arXiv, extracts text in-memory with PyMuPDF, and returns 
    fully populated Paper objects. 
    """

    def __init__(self):
        # You can add any settings or rate-limit semaphores if desired
        self.base_url = "http://export.arxiv.org/api/query"
        self.semaphore = asyncio.Semaphore(5)  # limit concurrency as needed

    async def search(self, query: str, limit: int = 30) -> List[Paper]:
        """
        Execute a search against the arXiv API by passing the entire 'query' 
        string as a natural-language search. The 'limit' parameter restricts 
        how many results to return.
        """
        # Example final arXiv query:
        #   http://export.arxiv.org/api/query?search_query=all:<query>&start=0&max_results=limit
        # We'll parse the Atom XML and pull out metadata.
        logger.info(f"Arxiv: Starting search with limit={limit}, query='{query}'")
        async with aiohttp.ClientSession() as session:
            async with self.semaphore:
                try:
                    # Build the search URL
                    arxiv_url = (
                        f"{self.base_url}"
                        f"?search_query=all:{self._escape_query(query)}"
                        f"&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending"
                    )

                    logger.debug(f"Arxiv: URL => {arxiv_url}")
                    async with session.get(arxiv_url) as response:
                        if response.status != 200:
                            text_resp = await response.text()
                            logger.error(f"Arxiv: API request failed ({response.status}): {text_resp[:500]}")
                            return []

                        data = await response.text()
                        entries = self._parse_atom_feed(data)
                        logger.info(f"Arxiv: Retrieved {len(entries)} entries from the feed")

                        # For each entry, try to download the PDF and extract text
                        results = []
                        for entry in entries:
                            # Build a Paper from the parsed metadata
                            paper_obj = await self._build_paper_from_entry(entry, session)
                            if paper_obj and (paper_obj.abstract or paper_obj.full_text):
                                results.append(paper_obj)

                        logger.info(f"Arxiv: Final result count => {len(results)}")
                        return results

                except Exception as ex:
                    logger.error(f"Arxiv: Unexpected error in search => {str(ex)}", exc_info=True)
                    return []

    def _escape_query(self, text: str) -> str:
        """
        Escape or encode the query if needed. Basic approach is to replace spaces with '+' 
        or something, but the arXiv API does handle normal spaces in 'all:' queries. 
        We'll just replace special characters that might break the XML.
        """
        # Minimal escaping for safety
        # In practice, you could do: urllib.parse.quote_plus(text)
        # but we keep it simpler for arXiv's 'all:' usage.
        return text.replace(" ", "+").replace(":", "")

    def _parse_atom_feed(self, xml_data: str) -> List[dict]:
        """
        Parse the raw XML from the arXiv API into a list of dict entries.
        Each dict includes fields like 'id', 'title', 'summary', 'published', 'updated', 
        'pdf_url', 'authors' (list of names), 'doi', etc.
        """
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            logger.error(f"Arxiv: Error parsing XML => {str(e)}")
            return []

        # arXiv uses the Atom 1.0 namespaces
        ns = {
            'a': 'http://www.w3.org/2005/Atom'
        }
        entries = []
        for entry_elem in root.findall('a:entry', ns):
            # Basic metadata
            entry_id = entry_elem.findtext('a:id', default="", namespaces=ns).strip()
            title = entry_elem.findtext('a:title', default="", namespaces=ns).strip()
            summary = entry_elem.findtext('a:summary', default="", namespaces=ns).strip()
            published = entry_elem.findtext('a:published', default="", namespaces=ns).strip()
            updated = entry_elem.findtext('a:updated', default="", namespaces=ns).strip()

            # Authors
            author_names = []
            for author_elem in entry_elem.findall('a:author', ns):
                name_elem = author_elem.find('a:name', ns)
                if name_elem is not None:
                    author_names.append(name_elem.text.strip())

            # PDF link
            pdf_url = ""
            for link_elem in entry_elem.findall('a:link', ns):
                if link_elem.get('title') == 'pdf':
                    pdf_url = link_elem.get('href')
                    break

            # Optional arXiv:doi is sometimes included
            doi_elem = entry_elem.find('{http://arxiv.org/schemas/atom}doi')
            doi = doi_elem.text.strip() if (doi_elem is not None and doi_elem.text) else ""

            # Build a dictionary
            entries.append({
                'id': entry_id,
                'title': html.unescape(title),
                'summary': html.unescape(summary),
                'published': published,
                'updated': updated,
                'authors': author_names or ["Unknown Author"],
                'pdf_url': pdf_url,
                'doi': doi
            })
        return entries

    async def _build_paper_from_entry(self, entry: dict, session: aiohttp.ClientSession) -> Optional[Paper]:
        """
        Given one parsed arXiv entry (dict), download its PDF (if available), extract text, 
        and build a Paper object.
        """
        title = entry.get('title') or ""
        pdf_url = entry.get('pdf_url') or ""
        summary = entry.get('summary') or ""
        authors = entry.get('authors', [])
        doi = entry.get('doi', "")
        published_year = self._extract_year(entry.get('published', ""))

        # Attempt to get full text from the PDF
        full_text = ""
        if pdf_url:
            pdf_text = await self._download_and_extract_pdf(pdf_url, session)
            full_text = pdf_text.strip()

        # Construct the Paper object 
        paper_obj = Paper(
            doi=doi,
            title=title,
            authors=authors,
            year=published_year,
            abstract=summary,
            source="arXiv",
            full_text=full_text,
            pdf_link=pdf_url,
            metadata={
                "arxiv_id": entry.get('id', ""),
                "published_date": entry.get('published', ""),
                "updated_date": entry.get('updated', "")
            }
        )
        return paper_obj

    def _extract_year(self, date_str: str) -> int:
        """
        Attempt to parse a year from a date like '2023-02-13T12:34:56Z'
        or '2020-11-02'. Return -1 if none found or out of range.
        """
        if not date_str:
            return -1
        try:
            year = int(date_str.split("-")[0])
            if 1900 <= year <= 2100:
                return year
        except Exception:
            pass
        return -1

    async def _download_and_extract_pdf(self, pdf_url: str, session: aiohttp.ClientSession) -> str:
        """
        Download the PDF bytes from arXiv in memory, then extract text with PyMuPDF.
        Return the extracted text, or "" if any error arises.
        """
        try:
            async with session.get(pdf_url) as resp:
                if resp.status == 200:
                    pdf_bytes = await resp.read()
                    if not pdf_bytes:
                        logger.warning(f"Arxiv: PDF at {pdf_url} is empty.")
                        return ""
                    return self._extract_text_from_pdf_bytes(pdf_bytes)
                else:
                    logger.warning(f"Arxiv: Unable to fetch PDF (status={resp.status}) => {pdf_url}")
                    return ""
        except Exception as ex:
            logger.error(f"Arxiv: Error downloading PDF => {str(ex)}")
            return ""

    def _extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes using PyMuPDF (fitz).
        Return the concatenated textual content of all pages.
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            extracted = []
            for page in doc:
                extracted.append(page.get_text("text"))
            doc.close()
            return "\n".join(extracted)
        except Exception as ex:
            logger.error(f"Arxiv: Error parsing PDF in memory => {str(ex)}")
            return ""
