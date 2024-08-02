# tests/test_search/test_openalex.py

import pytest
from unittest.mock import patch, MagicMock
from academic_claim_analyzer.search.openalex_search import OpenAlexSearch
from academic_claim_analyzer.models import Paper

@pytest.fixture
def mock_openalex_response():
    return {
        "results": [
            {
                "doi": "10.1016/j.diabres.2023.03.050",
                "title": "Coffee consumption and risk of type 2 diabetes: An updated meta-analysis of prospective cohort studies",
                "authorships": [
                    {"author": {"display_name": "Jiali Zheng"}},
                    {"author": {"display_name": "Jingjing Zhang"}},
                    {"author": {"display_name": "Yong Zhou"}}
                ],
                "publication_year": 2023,
                "abstract": "This meta-analysis of prospective cohort studies suggests that coffee consumption is associated with a reduced risk of type 2 diabetes, with the strongest effect observed for 3-4 cups per day.",
                "primary_location": {
                    "pdf_url": "https://www.sciencedirect.com/science/article/pii/S0168822723001512/pdf",
                    "source": {"display_name": "Diabetes Research and Clinical Practice"}
                },
                "cited_by_count": 12,
                "id": "W4235689012"
            }
        ]
    }

@pytest.mark.asyncio
async def test_openalex_search(mock_openalex_response):
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = MagicMock(return_value=mock_openalex_response)

        search = OpenAlexSearch(email="researcher@university.edu")
        results = await search.search("coffee consumption type 2 diabetes", 1)

        assert len(results) == 1
        paper = results[0]
        assert isinstance(paper, Paper)
        assert paper.doi == "10.1016/j.diabres.2023.03.050"
        assert paper.title == "Coffee consumption and risk of type 2 diabetes: An updated meta-analysis of prospective cohort studies"
        assert paper.authors == ["Jiali Zheng", "Jingjing Zhang", "Yong Zhou"]
        assert paper.year == 2023
        assert "coffee consumption is associated with a reduced risk of type 2 diabetes" in paper.abstract
        assert paper.pdf_link == "https://www.sciencedirect.com/science/article/pii/S0168822723001512/pdf"
        assert paper.source == "Diabetes Research and Clinical Practice"
        assert paper.metadata["citation_count"] == 12
        assert paper.metadata["openalex_id"] == "W4235689012"

@pytest.mark.asyncio
async def test_openalex_search_error():
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 500

        search = OpenAlexSearch(email="researcher@university.edu")
        results = await search.search("coffee consumption type 2 diabetes", 1)

        assert len(results) == 0