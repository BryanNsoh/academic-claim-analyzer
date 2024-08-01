# tests/test_query_formulator.py

import pytest
from src.academic_claim_analyzer.query_formulator import formulate_queries

@pytest.mark.asyncio
@pytest.mark.parametrize("claim, num_queries, query_type, expected_keywords", [
    (
        "Coffee consumption is associated with reduced risk of type 2 diabetes.",
        3,
        "scopus",
        ["coffee", "consumption", "reduced risk", "type 2 diabetes", "association"]
    ),
    (
        "Mindfulness meditation can help reduce symptoms of anxiety and depression.",
        4,
        "openalex",
        ["mindfulness", "meditation", "anxiety", "depression", "symptoms", "reduce"]
    ),
    (
        "Regular exercise is linked to improved cardiovascular health in older adults.",
        5,
        "scopus",
        ["regular exercise", "cardiovascular health", "older adults", "linked", "improved"]
    ),
])
async def test_formulate_queries(claim, num_queries, query_type, expected_keywords):
    queries = await formulate_queries(claim, num_queries, query_type)
    assert isinstance(queries, list)
    assert len(queries) == num_queries
    for query in queries:
        assert isinstance(query, str)
        assert len(query) > 0
        assert any(keyword.lower() in query.lower() for keyword in expected_keywords)

    # Check if queries are different from each other
    assert len(set(queries)) == num_queries

    # Check if queries adhere to the specified query type format
    if query_type.lower() == 'scopus':
        assert all("TITLE-ABS-KEY" in query for query in queries)
    elif query_type.lower() == 'openalex':
        assert all(query.startswith('"') or query.startswith('-') or query.startswith('+') for query in queries)

@pytest.mark.asyncio
async def test_formulate_queries_invalid_query_type():
    with pytest.raises(ValueError, match="Unsupported query type"):
        await formulate_queries("Test claim", 3, "invalid_type")

@pytest.mark.asyncio
async def test_formulate_queries_error_handling():
    # Test with invalid JSON response (simulated by mocking the LLMHandler)
    with pytest.patch('src.academic_claim_analyzer.query_formulator.LLMHandler') as mock_handler:
        mock_handler.return_value.query.return_value = "Invalid JSON"
        with pytest.raises(ValueError, match="Failed to parse the response as JSON"):
            await formulate_queries("Test claim", 3, "scopus")

    # Test with valid JSON but incorrect format
    with pytest.patch('src.academic_claim_analyzer.query_formulator.LLMHandler') as mock_handler:
        mock_handler.return_value.query.return_value = '{"key": "value"}'
        with pytest.raises(ValueError, match="Invalid response format"):
            await formulate_queries("Test claim", 3, "scopus")