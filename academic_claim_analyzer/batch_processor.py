import asyncio
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import yaml

from .debug_utils import configure_logging
from .models import RequestAnalysis

logger = logging.getLogger(__name__)

# Initialize with default configuration
configure_logging()

def analyze_request(*args, **kwargs):
    from . import get_analyze_request
    return get_analyze_request()(*args, **kwargs)

class BatchProcessorConfig:
    """Configuration container for batch processing settings."""
    def __init__(self, config_data: Dict[str, Any]):
        # Processing settings
        processing = config_data.get('processing', {})
        self.num_queries = processing.get('num_queries', 5)
        self.papers_per_query = processing.get('papers_per_query', 5)
        self.num_papers_to_return = processing.get('num_papers_to_return', 3)

        # Logging settings
        logging_config = config_data.get('logging', {})
        self.log_level = logging_config.get('level', 'INFO')

        # Search settings
        search = config_data.get('search', {})
        self.search_platforms = search.get('platforms', ['openalex', 'scopus', 'core', 'arxiv'])
        self.min_year = search.get('min_year', None)
        self.max_year = search.get('max_year', None)

def load_batch_config(yaml_file: str) -> BatchProcessorConfig:
    """Load batch processing configuration from YAML file."""
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning("YAML is empty or invalid. Using default config.")
            return BatchProcessorConfig({})

        if isinstance(data, dict) and 'config' in data:
            config_data = data.get('config', {})
        else:
            # Possibly top-level list or unexpected structure
            config_data = {}

        return BatchProcessorConfig(config_data)

    except Exception as e:
        logger.error(f"Error loading batch configuration: {str(e)}")
        return BatchProcessorConfig({})

def load_requests_from_yaml(yaml_file: str) -> List[Dict[str, Any]]:
    """Load user requests from a YAML file."""
    logger.info(f"Loading requests from YAML file: {yaml_file}")
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning("No content in YAML.")
            return []

        # The user must place requests under "requests"
        requests_data = []
        if isinstance(data, dict) and 'requests' in data:
            requests_data = data['requests']
        else:
            logger.warning("No 'requests' key found in YAML. Returning empty list.")

        return requests_data

    except Exception as e:
        logger.error(f"Error loading requests from YAML: {str(e)}")
        raise

def merge_configs(global_config: dict, request_config: dict) -> dict:
    """
    Deep merge two configuration dictionaries.
    In case of conflict, the request_config values take precedence.
    """
    merged = global_config.copy()
    for key, value in request_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

async def process_requests(requests_data: List[Dict[str, Any]], config: BatchProcessorConfig) -> Dict[str, Any]:
    """Process a list of requests using the provided configuration."""
    results = {}
    logger.info(f"Full requests data object: {requests_data}")

    # Build a global configuration dictionary from BatchProcessorConfig
    global_config = {
        "processing": {
            "num_queries": config.num_queries,
            "papers_per_query": config.papers_per_query,
            "num_papers_to_return": config.num_papers_to_return
        },
        "logging": {"level": config.log_level},
        "search": {
            "platforms": config.search_platforms,
            "min_year": config.min_year,
            "max_year": config.max_year,
        }
    }

    for req_data in requests_data:
        ranking_text = req_data.get('ranking_guidance', '').strip()
        
        # Check for multi-query: if 'queries' key is provided and is a list, use it; else fallback to single 'query'
        if 'queries' in req_data and isinstance(req_data['queries'], list):
            user_query = req_data['queries']
        else:
            query_text = req_data.get('query', '').strip()
            if not query_text:
                logger.warning("Skipping request with empty query.")
                continue
            user_query = query_text

        # ID fallback
        request_id = req_data.get('id', '')
        if not request_id:
            if isinstance(user_query, list):
                # Fallback to first few words of first query
                request_id = "_".join(user_query[0].split()[:5]) or "unnamed_request"
            else:
                request_id = "_".join(user_query.split()[:5]) or "unnamed_request"

        # Merge global config with request-specific config
        req_config = req_data.get('config', {})
        merged_config = merge_configs(global_config, req_config)

        try:
            # Analyze this request with the merged configuration.
            # Note that 'query' may be a list or a string.
            analysis = await analyze_request(
                query=user_query,
                ranking_guidance=ranking_text,
                exclusion_criteria=req_data.get('exclusion_criteria', {}),
                data_extraction_schema=req_data.get('information_extraction', {}),
                num_queries=merged_config["processing"]["num_queries"],
                papers_per_query=merged_config["processing"]["papers_per_query"],
                num_papers_to_return=merged_config["processing"]["num_papers_to_return"],
                config=merged_config
            )

            if isinstance(analysis, RequestAnalysis):
                results[request_id] = analysis.to_dict()
            else:
                results[request_id] = analysis

        except Exception as e:
            logger.error(f"Error analyzing request '{request_id}': {str(e)}", exc_info=True)
            results[request_id] = {"error": str(e)}

    return results

def extract_concise_results(results: Dict[str, Any], num_papers: int = 5) -> Dict[str, Any]:
    """Extract concise results for each request."""
    from .models import RequestAnalysis, RankedPaper
    concise_results = {}

    for req_id, analysis_dict in results.items():
        if not isinstance(analysis_dict, dict):
            continue
        # If we stored the data from a RequestAnalysis .to_dict(), attempt to replicate top N
        ranked_papers = analysis_dict.get('ranked_papers', [])
        all_params = analysis_dict.get('parameters', {})

        # Just pick the first `num_papers` from the 'ranked_papers' array in that dict
        top_papers = ranked_papers[:num_papers]

        concise_papers = []

        for paper in top_papers:
            paper_dict = {
                'title': getattr(paper, 'title', paper.get('title', 'Unknown')),
                'authors': getattr(paper, 'authors', paper.get('authors', [])),
                'year': getattr(paper, 'year', paper.get('year')),
                'score': getattr(paper, 'relevance_score', paper.get('relevance_score')),
                'extraction_result': getattr(paper, 'extraction_result', paper.get('extraction_result', {})),
                'exclusion_criteria_result': getattr(paper, 'exclusion_criteria_result', paper.get('exclusion_criteria_result', {})),
                'analysis': getattr(paper, 'analysis', paper.get('analysis', '')),
                'relevant_quotes': getattr(paper, 'relevant_quotes', paper.get('relevant_quotes', []))[:3]
            }

            if paper_dict['extraction_result']:
                paper_dict['metrics'] = {
                    'dataset_size': paper_dict['extraction_result'].get('dataset_size', -1),
                    'accuracy': paper_dict['extraction_result'].get('accuracy', 'N/A'),
                    'methods_compared': paper_dict['extraction_result'].get('methods', 'N/A'),
                    'hardware': paper_dict['extraction_result'].get('hardware_specs', 'N/A')
                }

            if paper_dict['exclusion_criteria_result']:
                paper_dict['criteria'] = {
                    'no_comparison': paper_dict['exclusion_criteria_result'].get('no_comparison', False),
                    'small_dataset': paper_dict['exclusion_criteria_result'].get('small_dataset', False)
                }

            concise_papers.append(paper_dict)


        concise_results[req_id] = {
            'request_id': req_id,
            'parameters': all_params,
            'top_papers': concise_papers,
            'num_total_papers': len(ranked_papers),
            'timestamp': analysis_dict.get('timestamp', datetime.now().isoformat())
        }
    return concise_results

def sanitize_filename(name: str) -> str:
    """Convert a string into a valid filename."""
    import re
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\s_]+', '_', name)
    name = name.strip('. ')
    return name if name else 'unnamed_request'

def batch_analyze_requests(yaml_file: str) -> None:
    """Process multiple requests in batch using configuration from a YAML file."""
    try:
        yaml_dir = os.path.dirname(os.path.abspath(yaml_file))
        yaml_name = os.path.splitext(os.path.basename(yaml_file))[0]
        output_dir = os.path.join(yaml_dir, f"{yaml_name}_results")
        os.makedirs(output_dir, exist_ok=True)

        config = load_batch_config(yaml_file)
        configure_logging(
            log_file=os.path.join(output_dir, 'batch_process.log'),
            console_level=config.log_level
        )

        logger.info("Starting batch analysis of requests.")
        logger.info(f"Results will be saved in: {output_dir}")

        requests_data = load_requests_from_yaml(yaml_file)
        if not requests_data:
            logger.warning("No requests to process. Exiting.")
            return

        results = asyncio.run(process_requests(requests_data, config))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save each request's results
        for req_data in requests_data:
            # Determine query for file naming
            if 'queries' in req_data and isinstance(req_data['queries'], list):
                query_text = req_data['queries'][0]
            else:
                query_text = req_data.get('query', '').strip()
            if not query_text:
                continue
            request_id = req_data.get('id', '')
            if not request_id:
                request_id = "_".join(query_text.split()[:5]) or "unnamed_request"
            request_id = sanitize_filename(request_id)

            # Determine how many top papers for concise results
            req_conf = req_data.get('config', {})
            num_papers = req_conf.get('num_papers_to_return', config.num_papers_to_return)

            if request_id not in results:
                logger.warning(f"No results found for '{request_id}' - skipping file creation.")
                continue

            full_result = {request_id: results[request_id]}
            concise_result = extract_concise_results(full_result, num_papers)

            base_filename = f"{request_id}_{timestamp}"
            with open(os.path.join(output_dir, f"{base_filename}_full.json"), 'w', encoding='utf-8') as f:
                json.dump(full_result, f, ensure_ascii=False, indent=2, default=str)

            with open(os.path.join(output_dir, f"{base_filename}.json"), 'w', encoding='utf-8') as f:
                json.dump(concise_result, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"Saved results for request '{request_id}'")

    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}", exc_info=True)
    finally:
        logger.info("Batch processing completed.")


if __name__ == "__main__":
    batch_analyze_requests(r"C:\Users\bryan\OneDrive\Documents\Projects\ACADEMIC LITERATURE UTILITIES\academic-claim-analyzer\CLAIMS\test.yaml")
