# tests/test_search/test_core.py

import pytest
from unittest.mock import patch, MagicMock

from academic_claim_analyzer.search.core_search import CORESearch
from academic_claim_analyzer.models import Paper

@pytest.fixture
def mock_core_response():
    return {
        "results": [
            {
                "doi": "10.1161/CIRCULATIONAHA.120.050775",
                "title": "Physical Activity and Cardiovascular Health in Older Adults: A Comprehensive Review",
                "authors": [
                    {"name": "Jennifer L. Carter"},
                    {"name": "Robert A. Thompson"},
                    {"name": "Lisa M. Brown"}
                ],
                "publicationYear": 2021,
                "abstract": "This comprehensive review examines the relationship between regular physical activity and cardiovascular health in older adults. The evidence strongly supports that engagement in regular exercise is associated with improved cardiovascular outcomes, including reduced risk of heart disease, stroke, and mortality.",
                "downloadUrl": "https://www.ahajournals.org/doi/pdf/10.1161/CIRCULATIONAHA.120.050775",
                "publisher": "Circulation",
                "fullText": "This is the full text of the paper, including detailed methods, results, and discussion...",
                "citationCount": 45,
                "id": "core:98765432"
            }
        ]
    }

@pytest.mark.asyncio
async def test_core_search(mock_core_response):
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        mock_post.return_value.__aenter__.return_value.json = MagicMock(return_value=mock_core_response)

        with patch.dict('os.environ', {'CORE_API_KEY': 'fake_api_key'}):
            search = CORESearch()
            results = await search.search("physical activity cardiovascular health older adults", 1)

            assert len(results) == 1
            paper = results[0]
            assert isinstance(paper, Paper)
            assert paper.doi == "10.1161/CIRCULATIONAHA.120.050775"
            assert paper.title == "Physical Activity and Cardiovascular Health in Older Adults: A Comprehensive Review"
            assert paper.authors == ["Jennifer L. Carter", "Robert A. Thompson", "Lisa M. Brown"]
            assert paper.year == 2021
            assert "relationship between regular physical activity and cardiovascular health in older adults" in paper.abstract
            assert paper.pdf_link == "https://www.ahajournals.org/doi/pdf/10.1161/CIRCULATIONAHA.120.050775"
            assert paper.source == "Circulation"
            assert "This is the full text of the paper" in paper.full_text
            assert paper.metadata["citation_count"] == 45
            assert paper.metadata["core_id"] == "core:98765432"

@pytest.mark.asyncio
async def test_core_search_error():
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 500

        with patch.dict('os.environ', {'CORE_API_KEY': 'fake_api_key'}):
            search = CORESearch()
            results = await search.search("physical activity cardiovascular health older adults", 1)

            assert len(results) == 0