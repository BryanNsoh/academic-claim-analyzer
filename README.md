# Academic Claim Analyzer

An advanced tool for rigorously analyzing academic claims using multi-source search, intelligent scraping, and AI-powered ranking across scholarly databases.

## Features

- Multi-source academic search (OpenAlex, Scopus, CORE)
- LLM-powered query formulation for optimal search results
- Full-text paper scraping with fallback mechanisms
- AI-driven paper ranking and relevance analysis
- Batch processing for efficient multi-claim analysis
- Flexible exclusion criteria and information extraction schemas
- BibTeX generation for seamless citation management
- Comprehensive logging and error handling

## Installation

```bash
pip install academic-claim-analyzer
```

Ensure you have Python 3.7+ and install required dependencies:

```bash
pip install -r requirements.txt
playwright install
```

## Configuration

Set environment variables:
- `SCOPUS_API_KEY`: Your Scopus API key
- `CORE_API_KEY`: Your CORE API key
- `OPENAI_API_KEY`: Your OpenAI API key (for LLM-powered components)

Or use a `.env` file:

```
SCOPUS_API_KEY=your_scopus_key
CORE_API_KEY=your_core_key
OPENAI_API_KEY=your_openai_key
```

## Usage

### Single Claim Analysis

```python
import asyncio
from academic_claim_analyzer import analyze_claim

async def main():
    claim = "Urban green spaces enhance community well-being and mental health in cities."
    
    # Define exclusion criteria
    exclusion_criteria = {
        "is_review": {"description": "Is the paper a review article? True if yes."},
        "published_before_2010": {"description": "Was the paper published before 2010? True if yes."}
    }
    
    # Define information extraction schema
    extraction_schema = {
        "discussed_topics": {"description": "List of key topics discussed in the paper."},
        "methodology": {"description": "Brief description of the methodology used in the paper."}
    }
    
    result = await analyze_claim(
        claim=claim,
        exclusion_criteria=exclusion_criteria,
        extraction_schema=extraction_schema,
        num_queries=3,
        papers_per_query=5,
        num_papers_to_return=3
    )
    
    # Print top papers
    for paper in result.get_top_papers(3):
        print(f"Title: {paper.title}")
        print(f"Relevance: {paper.relevance_score}")
        print(f"Analysis: {paper.analysis}")
        print(f"Exclusion Criteria: {paper.exclusion_criteria_result}")
        print(f"Extracted Info: {paper.extraction_result}")
        print(f"BibTeX: {paper.bibtex}")
        print("---")

asyncio.run(main())
```

### Batch Processing with YAML Files

1. Create a YAML file (e.g., `claims.yaml`) with the following structure:

```yaml
- claim_set_id: urban_planning_claims
  claims:
    - claim: "Urban green spaces enhance community well-being and mental health in cities."
      exclusion_criteria:
        is_review:
          description: "Is the paper a review article? True if yes."
        published_before_2010:
          description: "Was the paper published before 2010? True if yes."
      information_extraction:
        discussed_topics:
          description: "List of key topics discussed in the paper."
        methodology:
          description: "Brief description of the methodology used in the paper."
    - claim: "Implementing smart traffic management systems reduces urban congestion and improves air quality."
      exclusion_criteria:
        sample_size_too_small:
          description: "Does the study have a sample size less than 100? True if yes."
      information_extraction:
        key_findings:
          description: "Main results or conclusions of the study."
        technologies_used:
          description: "List of technologies or systems mentioned in the study."

- claim_set_id: climate_change_claims
  claims:
    - claim: "Renewable energy adoption significantly reduces greenhouse gas emissions in developed countries."
      exclusion_criteria:
        not_peer_reviewed:
          description: "Is the paper not peer-reviewed? True if yes."
      information_extraction:
        energy_sources:
          description: "List of renewable energy sources discussed."
        emission_reduction:
          description: "Quantitative data on emission reduction, if available."
```

2. Use the following code to process the claims:

```python
import asyncio
from academic_claim_analyzer import batch_analyze_claims, load_claims_from_yaml

async def main():
    # Load claims from the YAML file
    claims_data = load_claims_from_yaml("path/to/your/claims.yaml")

    # Process the claims
    results = await batch_analyze_claims(
        claims_data, 
        output_dir="results", 
        num_queries=3, 
        papers_per_query=5, 
        num_papers_to_return=3
    )

    # Print results summary
    for claim_set_id, claim_results in results.items():
        print(f"\nResults for claim set: {claim_set_id}")
        for claim, papers in claim_results.items():
            print(f"\nClaim: {claim}")
            for paper in papers:
                print(f"  Title: {paper['title']}")
                print(f"  Relevance: {paper['relevance_score']}")
                print(f"  Analysis: {paper['analysis'][:100]}...")  # Truncated for brevity
                print(f"  Exclusion Criteria: {paper['exclusion_criteria_result']}")
                print(f"  Extracted Info: {paper['extraction_result']}")
                print("  ---")

asyncio.run(main())
```

## Advanced Usage

### Custom LLM Model Configuration

You can customize the LLM model used for analysis:

```python
from academic_claim_analyzer import LLMAPIHandler

handler = LLMAPIHandler(
    request_timeout=60.0,
    custom_rate_limits={
        "gpt-4o-mini": {
            "rpm": 3000,
            "tpm": 250000,
            "max_tokens": 8000,
            "context_window": 8000
        }
    }
)

# Use this handler in your analysis functions
```

### Implementing Custom Search Modules

You can create custom search modules by inheriting from the `BaseSearch` class:

```python
from academic_claim_analyzer.search import BaseSearch
from academic_claim_analyzer.models import Paper

class CustomSearch(BaseSearch):
    async def search(self, query: str, limit: int) -> List[Paper]:
        # Implement your custom search logic here
        # Return a list of Paper objects
        pass

# Use your custom search in the analysis pipeline
```

## Performance Optimization

- Use `batch_analyze_claims` for processing multiple claims efficiently
- Adjust `num_queries` and `papers_per_query` based on desired depth vs. speed
- Implement caching mechanisms for frequently accessed papers or search results

## Logging and Debugging

The tool uses Python's logging module. Adjust logging level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Testing

Run the test suite:

```bash
pytest tests/
```

For integration tests (requires API keys):

```bash
pytest tests/ --runintegration
```

## Contributing

Please read `CONTRIBUTING.md` for details on our code of conduct and development process.

## License

Distributed under the MIT License. See `LICENSE` file for more information.

## Acknowledgments

- OpenAlex, Scopus, and CORE for providing access to their databases
- OpenAI for powering the LLM components
