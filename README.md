# Academic Claim Analyzer

An advanced tool for rigorously analyzing academic claims using multi-source search, intelligent scraping, and AI-powered ranking across scholarly databases.

## Features

- Multi-source academic search (OpenAlex, Scopus, CORE)
- LLM-powered query formulation for optimal search results
- Full-text paper scraping with fallback mechanisms
- AI-driven paper ranking and relevance analysis
- Batch processing for efficient multi-claim analysis
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

## Quick Start

```python
import asyncio
from academic_claim_analyzer import analyze_claim

async def main():
    claim = "Coffee consumption is associated with reduced risk of type 2 diabetes."
    result = await analyze_claim(claim)
    print(f"Top paper: {result.get_top_papers(1)[0].title}")
    print(f"Analysis: {result.get_top_papers(1)[0].analysis}")

asyncio.run(main())
```

## Detailed Usage

### Single Claim Analysis

```python
from academic_claim_analyzer import analyze_claim

claim = "Coffee consumption is associated with reduced risk of type 2 diabetes."
result = await analyze_claim(claim, num_queries=3, papers_per_query=5, num_top_papers=3)

for paper in result.get_top_papers(3):
    print(f"Title: {paper.title}")
    print(f"Relevance: {paper.relevance_score}")
    print(f"Analysis: {paper.analysis}")
    print(f"BibTeX: {paper.bibtex}")
```

### Batch Processing

```python
from academic_claim_analyzer import batch_analyze_claims, load_claims_from_yaml

claims_data = load_claims_from_yaml("claims.yaml")
batch_analyze_claims(claims_data, output_dir="results", num_top_papers=5)
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

## Performance Optimization

- Use `batch_analyze_claims` for processing multiple claims efficiently
- Adjust `num_queries` and `papers_per_query` based on desired depth vs. speed

## Error Handling and Logging

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

