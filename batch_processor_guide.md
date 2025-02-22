# Batch Processing Guide: Analyzing Multiple Research Requests

## Overview

The batch processor allows you to analyze multiple research requests simultaneously, providing comprehensive evidence gathering and analysis. For each request, you can specify:
- **`query`** (or alternatively **`queries`**):  
  - **`query`**: The natural-language research question or topic you’re investigating (single string).  
  - **`queries`**: An array of multiple queries for the same request. Each query is processed separately, and the results are merged before ranking.
- **`ranking_guidance`**: A string (short or long) telling the ranker how to prioritize papers (e.g., “focus on recent empirical studies” or “prioritize theoretical frameworks”).
- Exclusion criteria to systematically filter out irrelevant papers.
- Information extraction schemas to pull structured data from relevant papers.
- Request-specific processing parameters.

The system will:
1. Generate optimized search queries across academic databases.
2. Retrieve and analyze relevant papers.
3. Apply your exclusion criteria (if specified).
4. Extract structured information (if requested).
5. Rank papers by relevance to the request, guided by your ranking instructions.
6. Provide both detailed and concise analysis outputs.

## Basic Usage

```python
from academic_claim_analyzer import batch_analyze_requests

# Process requests from a YAML file
batch_analyze_requests("path/to/requests.yaml")
```

Results will be automatically organized in a folder named after your YAML file (e.g., `requests_results/`) in the same directory as your YAML file.

## YAML Structure

Your YAML file should contain:
1. Global configuration for processing parameters.
2. One or more requests with their associated criteria and schemas.

### 1. Global Configuration

```yaml
config:
  processing:
    num_queries: 5         # Number of search queries per request
    papers_per_query: 7    # Papers to retrieve per query
    num_papers_to_return: 3  # Top papers to include in concise results

  logging:
    level: INFO           # Logging detail level (INFO, DEBUG, WARNING, ERROR)

  search:
    platforms:
      - openalex
      - scopus
      - core
      - arxiv
    min_year: 2010      # Optional year filtering
    max_year: 2024
```

### 2. Simple Request (Single Query)

You can use the single-string **`query`** field if you only need one query per request:

```yaml
requests:
  - id: basic_request      # Optional identifier for result files
    query: "Machine learning improves crop yield predictions"
    ranking_guidance: "Rank papers primarily by relevance to the query."
```

### 3. Multi‑Query Request

Alternatively, use the **`queries`** array to supply multiple top‑level queries. The processor will run the search pipeline for each query, merge the results, and then perform a single ranking pass.

```yaml
requests:
  - id: multi_query_request
    queries:
      - "Machine learning applications in crop yield prediction"
      - "Deep learning approaches for predicting crop yields"
    ranking_guidance: "Prioritize recent studies and empirical evaluations."
```

### 4. Request with Exclusion Criteria

Exclusion criteria are used to filter out papers that don’t meet your requirements. Each criterion should be:
- Defined with a descriptive key.
- Of type boolean.
- Accompanied by a clear description.

```yaml
requests:
  - id: exclusion_criteria_test_request
    query: "Impact of climate change on coffee production"
    ranking_guidance: "Focus on studies with quantitative data and specific geographic regions."
    exclusion_criteria:
      review_paper:
        type: boolean
        description: "Is the paper a review article (not original research)?"
      pre_2022_study:
        type: boolean
        description: "Was the main data collection for the study conducted before 2022?"
```

*Note: You may also use `queries` instead of `query` for multi‑query processing in this case.*

### 5. Request with Information Extraction

When you need to extract specific structured data from papers, define an extraction schema. Valid field types include:
- `string`
- `float`
- `integer`
- `boolean`
- `list`

```yaml
requests:
  - id: information_extraction_test_request
    query: "Effectiveness of vertical farming for urban agriculture"
    ranking_guidance: "Rank papers based on detailed economic and environmental impact analysis."
    information_extraction:
      land_use_efficiency:
        type: float
        description: "Land use efficiency improvement (%) compared to traditional farming"
      energy_consumption:
        type: integer
        description: "Energy consumption (kWh per kg of produce)"
      water_usage_reduction:
        type: float
        description: "Water usage reduction (%) compared to traditional farming"
      economic_viability:
        type: boolean
        description: "Is the vertical farming system considered economically viable in the study?"
      crop_types_suitable:
        type: list
        description: "List of crop types found to be suitable for vertical farming in the study"
      system_limitations:
        type: string
        description: "Key limitations or challenges of vertical farming systems discussed"
```

### 6. Complete Example with All Features

Below is a complete YAML example that includes global configuration, multi‑query support, exclusion criteria, information extraction, and request‑specific overrides.

```yaml
config:
  processing:
    num_queries: 5
    papers_per_query: 7
    num_papers_to_return: 3

  logging:
    level: INFO

  search:
    platforms:
      - openalex
      - scopus
      - core
      - arxiv
    min_year: 2010
    max_year: 2024

requests:
  - id: deep_learning_crops
    queries:
      - "Deep learning outperforms traditional methods in crop disease detection"
      - "Comparative study of deep neural networks in agricultural disease diagnosis"
    ranking_guidance: "Prioritize papers with comparative studies and performance metrics."
    config:              # Request-specific processing overrides
      num_papers_to_return: 5
    exclusion_criteria:
      no_comparison:
        type: boolean
        description: "No comparison with traditional methods"
      small_dataset:
        type: boolean
        description: "Dataset contains fewer than 1000 images"
    information_extraction:
      accuracy:
        type: float
        description: "Model accuracy percentage"
      dataset_size:
        type: integer
        description: "Number of images in dataset"
      methods:
        type: list
        description: "ML methods compared"
      hardware_specs:
        type: string
        description: "Computing resources used"

  - id: iot_irrigation
    query: "IoT sensor networks improve irrigation efficiency"
    ranking_guidance: "Rank based on real-world implementations and quantified water savings."
    exclusion_criteria:
      theoretical_only:
        type: boolean
        description: "Paper is theoretical without implementation"
      no_metrics:
        type: boolean
        description: "No quantitative efficiency metrics provided"
    information_extraction:
      water_savings:
        type: float
        description: "Percentage reduction in water usage"
      implementation_cost:
        type: float
        description: "Cost per hectare in USD"
      sensor_types:
        type: list
        description: "Types of sensors used"
```

## Output Structure and Organization

The batch processor creates a results folder named after your YAML file and generates two types of JSON files for each request:

### 1. Concise Results (`{request_id}_{timestamp}.json`)
Contains only the top N papers (specified by `num_papers_to_return`) with essential information:
```json
{
  "request_text": {
    "ranked_papers": [
      {
        "title": "Paper title",
        "authors": ["Author names"],
        "year": 2023,
        "bibtex": "Complete BibTeX citation",
        "relevant_quotes": [
          "Key quote demonstrating relevance",
          "Important finding supporting request"
        ],
        "analysis": "Detailed analysis of paper's relevance to request",
        "exclusion_criteria_result": {
          "no_empirical": false,
          "insufficient_data": false
        },
        "extraction_result": {
          "accuracy": 95.7,
          "methods_used": ["CNN", "Random Forest"],
          "dataset_size": 10000
        },
        "relevance_score": 0.95
      }
    ],
    "num_total_papers": 15
  }
}
```

### 2. Full Results (`{request_id}_{timestamp}_full.json`)
Contains complete analysis data including:
- All papers found, not just the top N.
- Search queries used.
- Complete paper metadata.
- Full text extracts.
- Processing timestamps.
- All analysis details.

### Example Directory Structure

For a YAML file named `agriculture_requests.yaml`:
```
agriculture_requests.yaml
agriculture_requests_results/
  ├── batch_process.log
  ├── deep_learning_crops_20241027_123456.json      # Concise results
  ├── deep_learning_crops_20241027_123456_full.json   # Full results
  ├── iot_irrigation_20241027_123456.json
  └── iot_irrigation_20241027_123456_full.json
```

## Understanding Exclusion and Extraction

### How Exclusion Works
When you specify exclusion criteria:
1. Each paper is evaluated against all criteria.
2. Criteria are evaluated based on the paper’s full text and metadata.
3. Any paper matching **any** criterion is excluded.
4. Results include the evaluation outcome for each criterion.
5. Use this to systematically filter out irrelevant papers.

Example:
```yaml
exclusion_criteria:
  no_empirical:
    type: boolean
    description: "Paper contains no empirical evaluation"  # Excludes theoretical papers
  small_scale:
    type: boolean
    description: "Study area under 1 hectare"  # Excludes small pilot studies
  old_data:
    type: boolean
    description: "Data collected before 2015"  # Excludes outdated studies
```

### How Extraction Works
When you specify an extraction schema:
1. The system analyzes the full text of each paper to find the requested information.
2. Extracted data is validated against the defined types.
3. All extracted values are included in the results.
4. Use this to gather specific evidence for your request.

Example:
```yaml
information_extraction:
  accuracy:
    type: float
    description: "Model prediction accuracy"  # Gets specific performance metrics
  dataset_size:
    type: integer
    description: "Number of samples"  # Validates study scale
  limitations:
    type: string
    description: "Study limitations"  # Captures important caveats
  methods:
    type: list
    description: "Methods compared"  # Lists all approaches tested
```

This structured approach ensures:
- Systematic evaluation of papers.
- Consistent criteria application.
- Structured evidence gathering.
- Reproducible analysis results.
- Clear documentation of findings.

---

By using either the `query` or `queries` field in your YAML, you can now tailor each research request to include one or multiple top‑level queries, giving you greater flexibility and control over the analysis process.

Happy researching!