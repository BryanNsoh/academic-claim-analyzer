# tests/test_main.py

import pytest
from unittest.mock import patch, MagicMock
from src.academic_claim_analyzer.main import analyze_claim
from src.academic_claim_analyzer.models import ClaimAnalysis, Paper, RankedPaper

@pytest.fixture
def mock_search_results():
    return [
        Paper(
            doi="10.1016/j.diabres.2023.03.050",
            title="Coffee consumption and risk of type 2 diabetes: An updated meta-analysis of prospective cohort studies",
            authors=["Jiali Zheng", "Jingjing Zhang", "Yong Zhou"],
            year=2023,
            abstract="This meta-analysis of prospective cohort studies suggests that coffee consumption is associated with a reduced risk of type 2 diabetes, with the strongest effect observed for 3-4 cups per day.",
            source="Diabetes Research and Clinical Practice"
        ),
        Paper(
            doi="10.2337/dc20-1800",
            title="Long-term coffee consumption, caffeine metabolism genetics, and risk of cardiovascular disease: a prospective analysis of up to 347,077 individuals and 8368 cases",
            authors=["Licia Iacoviello", "Marialaura Bonaccio", "Augusto Di Castelnuovo"],
            year=2021,
            abstract="This large prospective study suggests that coffee consumption is associated with a lower risk of cardiovascular disease, with the relationship influenced by caffeine metabolism genetics.",
            source="Diabetes Care"
        )
    ]

@pytest.fixture
def mock_ranked_papers():
    return [
        RankedPaper(
            doi="10.1016/j.diabres.2023.03.050",
            title="Coffee consumption and risk of type 2 diabetes: An updated meta-analysis of prospective cohort studies",
            authors=["Jiali Zheng", "Jingjing Zhang", "Yong Zhou"],
            year=2023,
            abstract="This meta-analysis of prospective cohort studies suggests that coffee consumption is associated with a reduced risk of type 2 diabetes, with the strongest effect observed for 3-4 cups per day.",
            source="Diabetes Research and Clinical Practice",
            relevance_score=0.95,
            relevant_quotes=["coffee consumption is associated with a reduced risk of type 2 diabetes"],
            analysis="This meta-analysis provides strong evidence supporting the claim that coffee consumption is associated with reduced risk of type 2 diabetes."
        ),
        RankedPaper(
            doi="10.2337/dc20-1800",
            title="Long-term coffee consumption, caffeine metabolism genetics, and risk of cardiovascular disease: a prospective analysis of up to 347,077 individuals and 8368 cases",

            authors=["Licia Iacoviello", "Marialaura Bonaccio", "Augusto Di Castelnuovo"],
            year=2021,
            abstract="This large prospective study suggests that coffee consumption is associated with a lower risk of cardiovascular disease, with the relationship influenced by caffeine metabolism genetics.",
            source="Diabetes Care",
            relevance_score=0.75,
            relevant_quotes=["coffee consumption is associated with a lower risk of cardiovascular disease"],
            analysis="While this study focuses on cardiovascular disease, it provides indirect support for the potential health benefits of coffee consumption, which may be relevant to the claim about type 2 diabetes risk reduction."
        )
    ]

@pytest.mark.asyncio
async def test_analyze_claim(mock_search_results, mock_ranked_papers):
    with patch('src.academic_claim_analyzer.query_formulator.formulate_queries') as mock_formulate_queries, \
         patch('src.academic_claim_analyzer.search.OpenAlexSearch.search') as mock_search, \
         patch('src.academic_claim_analyzer.paper_scraper.scrape_papers') as mock_scrape_papers, \
         patch('src.academic_claim_analyzer.paper_ranker.rank_papers') as mock_rank_papers:

        mock_formulate_queries.return_value = [
            "TITLE-ABS-KEY(coffee AND consumption AND (\"type 2 diabetes\" OR \"diabetes mellitus\") AND risk)",
            "TITLE-ABS-KEY(\"coffee intake\" AND \"diabetes risk\" AND (meta-analysis OR \"systematic review\"))"
        ]
        mock_search.return_value = mock_search_results
        mock_scrape_papers.return_value = mock_search_results
        mock_rank_papers.return_value = mock_ranked_papers

        claim = "Coffee consumption is associated with reduced risk of type 2 diabetes."
        result = await analyze_claim(claim, num_queries=2, papers_per_query=2, num_papers_to_return=2)

        assert isinstance(result, ClaimAnalysis)
        assert result.claim == claim
        assert len(result.queries) == 2
        assert len(result.search_results) == 4  # 2 queries * 2 papers per query
        assert len(result.ranked_papers) == 2

        top_papers = result.get_top_papers(2)
        assert len(top_papers) == 2
        assert top_papers[0].relevance_score >= top_papers[1].relevance_score
        assert "meta-analysis" in top_papers[0].title.lower()
        assert "type 2 diabetes" in top_papers[0].title.lower()

@pytest.mark.asyncio
async def test_analyze_claim_error_handling():
    with patch('src.academic_claim_analyzer.query_formulator.formulate_queries', side_effect=Exception("API rate limit exceeded")):
        claim = "Mindfulness meditation can help reduce symptoms of anxiety and depression."
        result = await analyze_claim(claim)
        assert isinstance(result, ClaimAnalysis)
        assert result.claim == claim
        assert "error" in result.metadata
        assert result.metadata["error"] == "API rate limit exceeded"
        assert len(result.queries) == 0
        assert len(result.search_results) == 0
        assert len(result.ranked_papers) == 0

@pytest.mark.asyncio
async def test_analyze_claim_no_results():
    with patch('src.academic_claim_analyzer.query_formulator.formulate_queries') as mock_formulate_queries, \
         patch('src.academic_claim_analyzer.search.OpenAlexSearch.search') as mock_search:

        mock_formulate_queries.return_value = ["TITLE-ABS-KEY(non_existent_topic AND improbable_research)"]
        mock_search.return_value = []

        claim = "Non-existent topic is related to improbable research outcomes."
        result = await analyze_claim(claim, num_queries=1, papers_per_query=5, num_papers_to_return=2)

        assert isinstance(result, ClaimAnalysis)
        assert result.claim == claim
        assert len(result.queries) == 1
        assert len(result.search_results) == 0
        assert len(result.ranked_papers) == 0
        assert "No relevant papers found" in result.metadata.get("analysis", "")

@pytest.mark.asyncio
async def test_analyze_claim_partial_results():
    with patch('src.academic_claim_analyzer.query_formulator.formulate_queries') as mock_formulate_queries, \
         patch('src.academic_claim_analyzer.search.OpenAlexSearch.search') as mock_search, \
         patch('src.academic_claim_analyzer.paper_scraper.scrape_papers') as mock_scrape_papers, \
         patch('src.academic_claim_analyzer.paper_ranker.rank_papers') as mock_rank_papers:

        mock_formulate_queries.return_value = [
            "TITLE-ABS-KEY(exercise AND \"cardiovascular health\" AND \"older adults\")",
            "TITLE-ABS-KEY(\"physical activity\" AND \"heart disease\" AND elderly)"
        ]
        mock_search.side_effect = [mock_search_results[:1], []]  # First query returns one result, second query returns no results
        mock_scrape_papers.return_value = mock_search_results[:1]
        mock_rank_papers.return_value = mock_ranked_papers[:1]

        claim = "Regular exercise is linked to improved cardiovascular health in older adults."
        result = await analyze_claim(claim, num_queries=2, papers_per_query=2, num_papers_to_return=2)

        assert isinstance(result, ClaimAnalysis)
        assert result.claim == claim
        assert len(result.queries) == 2
        assert len(result.search_results) == 1
        assert len(result.ranked_papers) == 1
        assert "Partial results found" in result.metadata.get("analysis", "")

if __name__ == "__main__":
    pytest.main()