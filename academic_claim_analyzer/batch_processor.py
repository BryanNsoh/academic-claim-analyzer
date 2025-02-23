import asyncio 
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any
import yaml

from .debug_utils import configure_logging
from .models import RequestAnalysis

logger = logging.getLogger(__name__)

# Initialize with default configuration
configure_logging()

def analyze_request(*args, **kwargs):
    """
    Thin wrapper to import the real analyze_request at runtime
    to avoid circular imports.
    """
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
        if isinstance(data, dict) and 'requests' in data:
            return data['requests']
        else:
            logger.warning("No 'requests' key found in YAML. Returning empty list.")
            return []

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

async def analyze_single_request(
    req_data: Dict[str, Any],
    global_config: Dict[str, Any]
) -> (str, dict):
    """
    Process a single request asynchronously.
    Returns (request_id, analysis_dict).
    """
    # Prepare config merges
    req_config = req_data.get('config', {})
    merged_config = merge_configs(global_config, req_config)

    # Decide between single vs multi-query
    if 'queries' in req_data and isinstance(req_data['queries'], list):
        user_query = req_data['queries']
    else:
        query_text = req_data.get('query', '').strip()
        if not query_text:
            # No query => skip
            return "empty_query", {"error": "Empty query."}
        user_query = query_text

    # Determine request_id
    request_id = req_data.get('id', '')
    if not request_id:
        if isinstance(user_query, list):
            request_id = "_".join(user_query[0].split()[:5]) or "unnamed_request"
        else:
            request_id = "_".join(user_query.split()[:5]) or "unnamed_request"

    request_id = request_id.strip()

    # Extra ranking guidance
    ranking_text = req_data.get('ranking_guidance', '').strip()

    try:
        # Actually call the analyze_request function
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
        # Convert to dict
        if isinstance(analysis, RequestAnalysis):
            return request_id, analysis.to_dict()
        else:
            # Should rarely happen, but if it returns some other format
            return request_id, analysis

    except Exception as e:
        logger.error(f"Error analyzing request '{request_id}': {str(e)}", exc_info=True)
        return request_id, {"error": str(e)}

async def process_all_requests_parallel(
    requests_data: List[Dict[str, Any]],
    config: BatchProcessorConfig
) -> Dict[str, Any]:
    """
    Process ALL requests in parallel (instead of sequentially).
    Returns a dict: { request_id: analysis_dict, ... }
    """
    # Build the shared "global_config" from BatchProcessorConfig
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

    # Create a separate coroutine task for each request
    tasks = []
    for req_data in requests_data:
        tasks.append(analyze_single_request(req_data, global_config))

    # Run them all in parallel
    results_list = await asyncio.gather(*tasks, return_exceptions=False)
    # results_list is a list of (request_id, analysis_dict)

    # Convert to a dict
    results_dict = {}
    for request_id, analysis_dict in results_list:
        results_dict[request_id] = analysis_dict

    return results_dict

def extract_concise_results(results: Dict[str, Any], default_num_papers: int = 5) -> Dict[str, Any]:
    """
    Create a shortened/concise version of each request's top papers.
    """
    from .models import RequestAnalysis, RankedPaper
    concise_results = {}

    for req_id, analysis_dict in results.items():
        if not isinstance(analysis_dict, dict):
            # e.g. error
            concise_results[req_id] = {"error": "Not a dict result"}
            continue

        ranked_papers = analysis_dict.get('ranked_papers', [])
        # Figure out how many top papers to show
        # We'll see if parameters => num_papers_to_return is present
        all_params = analysis_dict.get('parameters', {})
        n = all_params.get('num_papers_to_return', default_num_papers)

        # Just pick the first `n` from the 'ranked_papers' array
        top_papers = ranked_papers[:n]
        concise_papers = []

        for paper in top_papers:
            # The stored `paper` might be a dict
            # We only want a small subset of fields
            paper_dict = {
                'title': paper.get('title', 'Unknown'),
                'authors': paper.get('authors', []),
                'year': paper.get('year', None),
                'relevance_score': paper.get('relevance_score'),
                'analysis': paper.get('analysis', ''),
                'relevant_quotes': paper.get('relevant_quotes', [])[:3],
                'exclusion_criteria_result': paper.get('exclusion_criteria_result', {}),
                'extraction_result': paper.get('extraction_result', {}),
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

def batch_analyze_requests(yaml_file: str) -> None:
    """
    Main entry point: 
    1) Loads config + requests from YAML
    2) Runs them all in parallel
    3) Saves full results and concise results into separate JSON files
    """
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

        logger.info("Starting batch analysis of requests (in parallel).")
        logger.info(f"Results will be saved in: {output_dir}")

        requests_data = load_requests_from_yaml(yaml_file)
        if not requests_data:
            logger.warning("No requests to process. Exiting.")
            return

        # Run all requests concurrently
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            all_results = loop.run_until_complete(process_all_requests_parallel(requests_data, config))
        finally:
            loop.close()

        # Generate a "concise" version
        concise_results = extract_concise_results(all_results, default_num_papers=config.num_papers_to_return)

        # Save full and concise results in separate JSON files
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_filename = f"full_results_{timestamp_str}.json"
        concise_filename = f"concise_results_{timestamp_str}.json"
        full_path = os.path.join(output_dir, full_filename)
        concise_path = os.path.join(output_dir, concise_filename)

        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Saved full results to file: {full_path}")

        with open(concise_path, 'w', encoding='utf-8') as f:
            json.dump(concise_results, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Saved concise results to file: {concise_path}")

    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}", exc_info=True)
    finally:
        logger.info("Batch processing completed.")


if __name__ == "__main__":
    # Example usage / test
    batch_analyze_requests(
        r"C:\Users\bryan\OneDrive\Documents\Projects\ACADEMIC LITERATURE UTILITIES\academic-claim-analyzer\CLAIMS\test.yaml"
    )
