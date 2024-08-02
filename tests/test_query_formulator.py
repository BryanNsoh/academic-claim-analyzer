# tests/test_query_formulator.py

import pytest
from academic_claim_analyzer.query_formulator import formulate_queries
from unittest.mock import patch 

@pytest.mark.asyncio
@pytest.mark.parametrize("claim, num_queries, query_type", [
    (
        "Coffee consumption is associated with reduced risk of type 2 diabetes.",
        3,
        "scopus"
    ),
    (
        "Mindfulness meditation can help reduce symptoms of anxiety and depression.",
        4,
        "openalex"
    ),
    (
        "Regular exercise is linked to improved cardiovascular health in older adults.",
        5,
        "scopus"
    ),
])
async def test_formulate_queries(claim, num_queries, query_type):
    queries = await formulate_queries(claim, num_queries, query_type)
    assert isinstance(queries, list)
    assert len(queries) == num_queries
    for query in queries:
        print(query)  # Added for debugging, can be removed later
        assert isinstance(query, str)
        assert len(query) > 0

        if query_type.lower() == 'scopus':
            assert query.startswith("TITLE-ABS-KEY(") and query.endswith(")")
        elif query_type.lower() == 'openalex':
            assert query.startswith("https://api.openalex.org/works?search=")

@pytest.mark.asyncio
async def test_formulate_queries_invalid_query_type():
    with pytest.raises(ValueError, match="Unsupported query type"):
        await formulate_queries("Test claim", 3, "invalid_type")