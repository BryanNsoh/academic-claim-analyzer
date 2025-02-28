# 🚨 **Ultimate, Exhaustive, and Extremely Explicit Guide for Writing YAML-Based Academic Search Queries** 🚨

## 1. **Why This Guide Is Absolutely, Crucially Necessary**

This guide exists because even a **slight oversight**, **generality**, or **vagueness** in your search queries or ranking guidance can **catastrophically** derail the entire academic literature search process. This is not hyperbole. If your guidance and queries are not **explicitly, exhaustively, and overwhelmingly detailed**, the search will fail miserably—returning irrelevant results and wasting significant resources.

Therefore, **every single element** of your YAML query and ranking guidance must carry the **full and complete context** necessary to precisely delineate the boundary between “relevant” and “irrelevant” papers. **Do not** assume context is preserved across steps. Each step—query formulation, ranking guidance, and exclusion criteria—must stand utterly explicit and comprehensive on its own.

---

## 2. **Core Principle: Absolute Explicitness & Unambiguous Domain Constraints**

When writing your YAML file for academic searches, you have two critical pieces:

1. **Queries** (which define what to search for)  
2. **Ranking guidance** (which decides how to prioritize or exclude the returned papers)

The search engine and ranking logic will **not** magically infer your deeper intentions. You must *scream* your domain constraints and must-have criteria. Otherwise, it is doomed to return or top-rank irrelevant papers.

### 2.1 **What You MUST Do**

- **Emphatically specify** the exact application domain in your ranking guidance (e.g., “IoT for precision irrigation in agriculture,” “multi-omics for disease biomarkers,” “fuzzy logic specifically for irrigation scheduling,” etc.).  
- **List mandatory criteria** that define “relevant” (e.g., must have real field data, must mention water savings, must detail membership functions, must mention a certain type of multi-omics pipeline).  
- **Give explicit conditions** for how to handle borderline cases (simulation only vs. real pilot, partial domain, etc.).  
- **Forbid** all off-domain usage. If it’s not about your specified application, it must drop to the bottom or be excluded entirely.

### 2.2 **What You MUST NOT Do**

- **Never** rely on the queries alone to carry domain context. The ranking logic sees only the `ranking_guidance` and the paper text—**not** your original mental context.  
- **Never** be vague with statements like “prefer empirical studies.” Instead say “papers must explicitly mention real or pilot-scale deployment with measured water metrics,” or “papers must have validated multi-omics pipeline for disease classification with real patient data.”  
- **Never** allow guesswork. If you want fuzzy logic in irrigation, say: “If the paper does not mention fuzzy logic explicitly for agricultural irrigation scheduling, it is irrelevant—rank bottom.”

---

## 3. **Anatomy of a Proper YAML Search Request**

Every well-structured request has **five** main components:

1. **ID**  
   - A unique identifier, e.g., `- id: fuzzy_logic_irrigation_scheduling`.  
2. **Queries**  
   - An array of 5–10 (or more) queries that each contains domain-specific text.  
3. **Ranking guidance**  
   - A multi-line string specifying the **exact** domain constraints, top priorities, penalties, and irrelevances.  
4. **Exclusion criteria** (optional but strongly recommended)  
   - Boolean flags that automatically exclude or heavily penalize any paper not meeting your domain.  
5. **Information extraction**  
   - (Optional) Defines fields you want pulled from relevant papers, e.g. “water_savings,” “fuzzy_inference_method,” “multi_omics_pipeline,” “differential_expression_method,” etc.

Below is the typical YAML structure to keep in mind:

```yaml
config:
  processing:
    num_queries: 5
    papers_per_query: 7
    num_papers_to_return: 3
  # ... global config omitted for brevity

requests:
  - id: my_unique_request_id
    queries:
      - "First very explicit query"
      - "Second very explicit query"
      ...
    ranking_guidance: >
      <massively explicit domain constraints, desired metrics, do/don't, etc.>
    exclusion_criteria:
      <boolean flags for quick rejection>
    information_extraction:
      <structured data fields you want from each relevant paper>
```

**You must** fill out each section with the entire “gospel” of your domain. No assumptions!

---

## 4. **Detailed Breakdown: Queries vs. Ranking Guidance**

### 4.1 **Queries: Powerful & Domain-Specific**

- **Add your entire domain context**: If you want “fuzzy logic for irrigation scheduling,” explicitly mention “fuzzy logic,” “irrigation scheduling,” “agriculture,” and any key performance metrics or required details.  
- Use synonyms or near-synonyms if needed: e.g., “fuzzy inference system,” “Mamdani approach for farm water scheduling,” “Sugeno fuzzy in farmland.”  
- Example:
  ```yaml
  queries:
    - "Fuzzy logic specifically for agricultural irrigation scheduling with real pilot-scale data"
    - "Mamdani or Sugeno fuzzy inference for water management in agriculture"
    - "Comparison of fuzzy-based irrigation to threshold triggers with measured water savings"
  ```
- If you just say “fuzzy logic for agriculture,” you risk returning fuzzy logic for fertilizer, fuzzy logic for pest control, fuzzy logic for greenhouse climate, etc.—**not** irrigation scheduling specifically.

### 4.2 **Ranking Guidance: Your Non-Negotiable Linchpin**

During the ranking step, the system only sees:
1. The text of each retrieved paper  
2. The `ranking_guidance` you wrote  

**Hence** the ranking guidance must restate every crucial requirement—**including** the exact domain. The next section shows some powerful examples.

---

## 5. **Concrete, Detailed Ranking Guidance Examples**

### 5.1 **Example #1: Fuzzy Logic for Irrigation Scheduling in Agriculture**

This is the example from your prompt. **Keep it exactly**:

```yaml
ranking_guidance: >
  1. This request is ONLY about “fuzzy logic methods for irrigation scheduling
     in agriculture.” If a paper does not explicitly confirm it applies fuzzy logic 
     (in any variant: Mamdani, Sugeno, etc.) to agricultural irrigation or 
     water management, it must be deprioritized or effectively filtered out.

  2. The topmost rank goes to papers that demonstrate fuzzy irrigation scheduling 
     in real-world or pilot-scale agricultural settings with actual crops, 
     water stress metrics, or field data. Among these:
       - The more comprehensive the discussion of membership functions, 
         rulesets, crop stress factors, and success metrics (like water savings, yield, 
         or stress reduction), the better.
       - If a study only simulates or uses a purely laboratory hydroponic approach 
         without a real crop or real farmland environment, it is still valid 
         if it explicitly states "irrigation scheduling" in the context of agriculture, 
         but it ranks lower than full field or greenhouse trials.

  3. Next in priority are those that compare fuzzy-based irrigation to 
     other scheduling methods (like threshold triggers, PID, or standard 
     ET-based approaches). The presence of a performance comparison with 
     numeric results or at least robust methodology for measuring 
     irrigation outcomes is a plus.

  4. If a paper uses fuzzy logic for general agriculture tasks but NOT 
     specifically for irrigation scheduling (e.g., fuzzy logic for fertilizer 
     control or pest management only), rank it significantly lower 
     (close to the bottom).

  5. If a paper claims “fuzzy irrigation” but does not detail the rule-base 
     or membership functions, or does not present any real or simulated 
     performance metrics, it should rank lower than those with clear 
     methodological detail. Real empirical validation (even partial) 
     outranks purely conceptual or heuristic approaches.

  6. If the paper’s domain is not agriculture or not about irrigation 
     (for example, fuzzy logic for auto-braking systems or fuzzy 
     logic for medical diagnosis), that is completely irrelevant; 
     it should end up at the bottom of the rankings or excluded entirely. 

  7. Whenever multiple relevant studies exist, we prefer the most recent 
     (2015–present) especially if they use modern hardware or data-logging, 
     or mention IoT-based sensors. But older pioneering papers that 
     still strongly match “fuzzy logic in irrigation scheduling” can 
     rank high if they are seminal references with data.

  8. Any mention of “water-saving results” or “crop yield improvements” 
     plus fuzzy logic scheduling is a key bonus. 
     The more robust the result, the higher the priority.
```

You see how it **absolutely** forbids confusion between irrigation scheduling and other fuzzy logic domains.

---

### 5.2 **Example #2: Multi-Omics for Disease Biomarkers (Bioinformatics)**

Let’s present a **completely different** domain with extreme specificity. Suppose we only care about “multi-omics integration for disease biomarker discovery, requiring real human data.” We can write:

```yaml
ranking_guidance: >
  1. This request is ONLY about "multi-omics integration for disease biomarker discovery
     in humans." If a paper does not explicitly confirm it applies multi-omics data 
     (genomics, transcriptomics, proteomics, metabolomics, etc.) to identify or validate 
     disease biomarkers in human subjects, it must be deprioritized or effectively filtered out.

  2. The topmost rank goes to papers demonstrating integrative analysis of at least 
     TWO distinct omics layers (e.g., genomics + proteomics) in actual human disease 
     studies. Among these:
       - The more comprehensive the omics coverage (like genomics, transcriptomics, epigenomics, 
         proteomics, metabolomics) and the more robust the sample size, the higher the rank.
       - If a study only uses publicly available cell-line data or purely in silico 
         simulations without real human samples, it is still valid if it clearly states 
         it's for disease biomarker discovery with multi-omics, but ranks lower than 
         studies using actual patient data.

  3. Next in priority are those that compare integrated multi-omics approaches to 
     single-omics or traditional biomarkers. The presence of quantitative performance 
     metrics (e.g., AUC, accuracy, or p-values for biomarker significance) is a plus.

  4. If a paper uses multi-omics techniques for general systems biology research 
     but NOT specifically for disease biomarker identification or validation, 
     rank it significantly lower (close to the bottom).

  5. If a paper claims “multi-omics biomarker discovery” but does not detail 
     the omics layers or does not present any real or simulated 
     performance metrics or significance tests, it should rank lower 
     than those with clear methodological detail. Real empirical validation 
     with patient cohorts outranks purely conceptual or heuristic approaches.

  6. If the paper’s domain is not disease biomarkers in humans (for example, 
     multi-omics for plant breeding or for microbial communities), 
     that is completely irrelevant; it should end up at the bottom 
     of the rankings or excluded entirely. 

  7. Whenever multiple relevant studies exist, we prefer the most recent 
     (2018–present), especially if they use advanced pipeline tools 
     (like Nextflow, Snakemake) or mention integrated big data approaches. 
     But older pioneering papers that still strongly match "multi-omics 
     for disease biomarkers in humans" can rank high if they are seminal references.

  8. Any mention of “clinically validated biomarkers” or “patient-derived multi-omics data” 
     is a key bonus. The more robust the result (e.g., validated in multiple cohorts), 
     the higher the priority.
```

Notice how we replicate the same style of **ultra-strict** domain constraints, but in a **completely different** field (bioinformatics / multi-omics). The principle is the same: absolutely forbid any confusion—**only** multi-omics for disease biomarker discovery with real human data is relevant.

---

### 5.3 **Example #3: Edge-Computing IoT for Real-Time River Flood Monitoring**  
(Another random domain example of “extreme specificity”)

```yaml
ranking_guidance: >
  1. This request is ONLY about "edge-computing-based IoT systems for real-time 
     river flood monitoring or early warning." Any paper that does not explicitly 
     confirm it focuses on IoT edge devices monitoring river water levels or 
     flood prediction must be deprioritized or effectively filtered out.

  2. The topmost rank goes to papers demonstrating actual or pilot-scale river 
     monitoring deployments, where edge devices measure water level, flow rate, 
     or rainfall data. Among these:
       - The more comprehensive the discussion of hardware constraints, power usage, 
         data transmission, and real-time analysis, the better.
       - If a study only simulates or uses purely hypothetical data 
         without referencing real river or flood conditions, it is still valid 
         if it explicitly states "river flood monitoring," but it ranks lower 
         than full field trials.

  3. Next in priority are those that compare edge-computing IoT solutions to 
     traditional centralized or offline monitoring approaches. The presence 
     of performance metrics (latency, power usage, reliability under harsh 
     conditions, etc.) is a plus.

  4. If a paper uses IoT or edge computing for general environmental tasks (like 
     air quality or forest fire) but NOT specifically for river flood monitoring, 
     rank it significantly lower (close to the bottom).

  5. If a paper claims “river flood IoT” but does not detail the edge-computing 
     approach or does not present any real or simulated performance metrics, 
     it should rank lower than those with clear methodological detail. Real 
     empirical validation (even partial) outranks purely conceptual or heuristic approaches.

  6. If the paper’s domain is not about rivers/flood management at all 
     (for example, IoT for smart homes, city traffic, or farmland irrigation), 
     that is completely irrelevant; it should end up at the bottom 
     of the rankings or excluded entirely. 

  7. Whenever multiple relevant studies exist, we prefer the most recent (2016–present) 
     especially if they mention LoRa, NB-IoT, or edge ML. But older pioneering 
     papers that still strongly match "edge-based IoT for flood monitoring" 
     can rank high if they are seminal references with data.

  8. Any mention of “water-level sensors,” “real-time flood alarms,” or “low-power 
     edge devices” plus actual field deployment is a key bonus. The more robust the 
     result, the higher the priority.
```

Again, same structure: domain-limiting statement, top rank conditions, next priority, partial domain penalty, total irrelevance penalty, recency preference, and mention of bonus points.

---

## 6. **Side-by-Side Example of a Full YAML for Fuzzy Logic Irrigation**

Below is a complete snippet, referencing the *same* user-provided ranking guidance. We simply embed it under the `requests:` block along with queries, exclusion criteria, and info extraction:

```yaml
config:
  processing:
    num_queries: 8
    papers_per_query: 10
    num_papers_to_return: 5
  logging:
    level: DEBUG
  search:
    platforms:
      - openalex
      - scopus
      - core
      - arxiv
      - semantic_scholar
    min_year: 2010
    max_year: 2025

requests:

  - id: fuzzy_logic_irrigation
    queries:
      - "Fuzzy logic specifically for agricultural irrigation scheduling with real-world field data"
      - "Comparisons of Mamdani fuzzy irrigation control vs threshold-based or PID methods with numeric results"
      - "Pilot-scale or greenhouse trials applying fuzzy logic for water management in crops"
      - "Rule-based fuzzy membership functions for soil moisture and crop stress factors in irrigation scheduling"
      - "Any study demonstrating fuzzy logic and water-saving outcomes in agriculture"

    ranking_guidance: >
      1. This request is ONLY about “fuzzy logic methods for irrigation scheduling
         in agriculture.” If a paper does not explicitly confirm it applies fuzzy logic 
         (in any variant: Mamdani, Sugeno, etc.) to agricultural irrigation or 
         water management, it must be deprioritized or effectively filtered out.

      2. The topmost rank goes to papers that demonstrate fuzzy irrigation scheduling 
         in real-world or pilot-scale agricultural settings with actual crops, 
         water stress metrics, or field data. Among these:
           - The more comprehensive the discussion of membership functions, 
             rulesets, crop stress factors, and success metrics (like water savings, yield, 
             or stress reduction), the better.
           - If a study only simulates or uses a purely laboratory hydroponic approach 
             without a real crop or real farmland environment, it is still valid 
             if it explicitly states "irrigation scheduling" in the context of agriculture, 
             but it ranks lower than full field or greenhouse trials.

      3. Next in priority are those that compare fuzzy-based irrigation to 
         other scheduling methods (like threshold triggers, PID, or standard 
         ET-based approaches). The presence of a performance comparison with 
         numeric results or at least robust methodology for measuring 
         irrigation outcomes is a plus.

      4. If a paper uses fuzzy logic for general agriculture tasks but NOT 
         specifically for irrigation scheduling (e.g., fuzzy logic for fertilizer 
         control or pest management only), rank it significantly lower 
         (close to the bottom).

      5. If a paper claims “fuzzy irrigation” but does not detail the rule-base 
         or membership functions, or does not present any real or simulated 
         performance metrics, it should rank lower than those with clear 
         methodological detail. Real empirical validation (even partial) 
         outranks purely conceptual or heuristic approaches.

      6. If the paper’s domain is not agriculture or not about irrigation 
         (for example, fuzzy logic for auto-braking systems or fuzzy 
         logic for medical diagnosis), that is completely irrelevant; 
         it should end up at the bottom of the rankings or excluded entirely. 

      7. Whenever multiple relevant studies exist, we prefer the most recent 
         (2015–present) especially if they use modern hardware or data-logging, 
         or mention IoT-based sensors. But older pioneering papers that 
         still strongly match “fuzzy logic in irrigation scheduling” can 
         rank high if they are seminal references with data.

      8. Any mention of “water-saving results” or “crop yield improvements” 
         plus fuzzy logic scheduling is a key bonus. 
         The more robust the result, the higher the priority.

    exclusion_criteria:
      fuzzy_not_irrigation:
        type: boolean
        description: "Exclude or deprioritize if fuzzy logic is NOT explicitly about irrigation scheduling in agriculture."

    information_extraction:
      fuzzy_inference_type:
        type: string
        description: "Which fuzzy method is used? (Mamdani, Sugeno, etc.)"
      scale_of_study:
        type: string
        description: "Field-scale, pilot, greenhouse, or purely simulation/hydroponic?"
      performance_metrics:
        type: string
        description: "Mentioned water savings, yield improvement, or numeric results"
      comparison_to_baseline:
        type: boolean
        description: "Does the paper compare fuzzy scheduling to threshold, PID, or standard ET-based approaches?"
```

---

## 7. **Exclusion Criteria**: The Quick Filter

If you know certain traits instantly disqualify a paper, define a boolean in `exclusion_criteria`. For instance:

```yaml
exclusion_criteria:
  not_irrigation:
    type: boolean
    description: "Paper never mentions irrigation scheduling or water management in an agricultural context."

  no_real_data:
    type: boolean
    description: "Paper has no real or pilot-scale data, not even simulation mention for irrigation scheduling."
```

Now the system can ask: “Does the paper fail the `not_irrigation` check? If yes, exclude it.” This ensures worthless papers never get near the top.

---

## 8. **Information Extraction**: Gleaning Key Data Points

If you want specific fields from the top papers (like “accuracy,” “water_savings,” or “omics layers used”), define them under `information_extraction`. For instance:

```yaml
information_extraction:
  water_savings:
    type: float
    description: "Percentage of water savings reported in the study"
  membership_function_detail:
    type: boolean
    description: "Does the paper explicitly describe membership functions for the fuzzy system?"
  cost_analysis:
    type: boolean
    description: "Any mention of cost or economic analysis of the irrigation approach?"
```

---

## 9. **Most Common Failure Modes (and How This Guide Prevents Them)**

1. **Ranking Irrelevant Domains Highly**  
   - Caused by leaving out your domain in ranking guidance.  
   - **Solution**: “STRICT domain requirement: must mention [XYZ domain + application]. Anything else is bottom rank.”

2. **Failing to Demand Real Data**  
   - Caused by vague wording like “prefers empirical approach.”  
   - **Solution**: “Highest rank if real or pilot-scale data is explicitly provided with measured performance metrics.”

3. **Ending Up with Too Few Papers**  
   - Possibly you’re being extremely strict. Usually better than drowning in irrelevant results, but keep an eye on it.

4. **Overlooking Must-Have Performance Metrics**  
   - If you never mention “water savings” or “AUC” or “yield,” you get random results.  
   - **Solution**: “papers must mention these metrics or they rank lower.”

**Key**: Over-specify everything. If you think the system might “figure out” your domain, you are wrong. Spell it out.

---

## 10. **Final Takeaway**

This guide is meant to be your authoritative blueprint for constructing YAML-based academic search queries. **Never** cut corners on specificity. The success or failure of your entire literature review hinges on how precisely you specify your domain constraints in the ranking guidance (and queries). If you do it right—**with the level of detail shown above**—you will get high-quality, relevant results every time. If you do it wrong—**even just a little**—the search collapses, returning random irrelevance.

Therefore:

> **Write your ranking guidance and queries as though an extremely obtuse, obstinate, hyper-literal agent will interpret them with zero background knowledge.**  
> If you do this, you will produce an unambiguous, domain-locked search that excludes unrelated junk.  

Follow each section in this guide meticulously and you’ll reap the benefits of a focused, highly efficient academic literature search.