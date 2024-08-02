# tests/test_search/test_scopus.py

import pytest
from unittest.mock import patch, MagicMock
from academic_claim_analyzer.search.scopus_search import ScopusSearch
from academic_claim_analyzer.models import Paper

@pytest.fixture
def mock_scopus_response():
    return {
        "search-results": {
            "entry": [
                {
                    "prism:doi": "10.1016/j.jad.2022.01.053",
                    "dc:title": "Mindfulness-based interventions for anxiety and depression in adults: A meta-analysis of randomized controlled trials",
                    "author": [
                        {"authname": "Sarah J. Goldberg"},
                        {"authname": "Michael A. Smith"},
                        {"authname": "Emily R. Johnson"}
                    ],
                    "prism:coverDate": "2022-04-15",
                    "dc:description": "This meta-analysis provides evidence that mindfulness-based interventions are effective in reducing symptoms of anxiety and depression in adults, with moderate effect sizes observed across various clinical and non-clinical populations.",
                    "prism:publicationName": "Journal of Affective Disorders",
                    "citedby-count": "87",
                    "dc:identifier": "SCOPUS_ID:85123456789",
                    "eid": "2-s2.0-85123456789"
                }
            ]
        }
    }

@pytest.mark.asyncio
async def test_scopus_search(mock_scopus_response):
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = MagicMock(return_value=mock_scopus_response)

        with patch.dict('os.environ', {'SCOPUS_API_KEY': 'fake_api_key'}):
            search = ScopusSearch()
            results = await search.search("mindfulness anxiety depression meta-analysis", 1)

            assert len(results) == 1
            paper = results[0]
            assert isinstance(paper, Paper)
            assert paper.doi == "10.1016/j.jad.2022.01.053"
            assert paper.title == "Mindfulness-based interventions for anxiety and depression in adults: A meta-analysis of randomized controlled trials"
            assert paper.authors == ["Sarah J. Goldberg", "Michael A. Smith", "Emily R. Johnson"]
            assert paper.year == 2022
            assert "mindfulness-based interventions are effective in reducing symptoms of anxiety and depression" in paper.abstract
            assert paper.source == "Journal of Affective Disorders"
            assert paper.metadata["citation_count"] == 87
            assert paper.metadata["scopus_id"] == "SCOPUS_ID:85123456789"
            assert paper.metadata["eid"] == "2-s2.0-85123456789"

@pytest.mark.asyncio
async def test_scopus_search_error():
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 500

        with patch.dict('os.environ', {'SCOPUS_API_KEY': 'fake_api_key'}):
            search = ScopusSearch()
            results = await search.search("mindfulness anxiety depression meta-analysis", 1)

            assert len(results) == 0