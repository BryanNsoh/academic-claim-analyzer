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

- **Emphatically specify** the exact application domain in your ranking guidance (e.g., “IoT for precision irrigation in agriculture” or “fuzzy logic specifically for irrigation scheduling”).  
- **List mandatory criteria** that define “relevant” (e.g., must have real field data, must mention water savings).  
- **Give explicit conditions** for how to handle borderline cases (simulation, partial domain).  
- **Forbid** all off-domain usage. If it’s not about your specified application, it must drop to the bottom or be excluded entirely.

### 2.2 **What You MUST NOT Do**

- **Never** rely on the queries alone to carry domain context. The ranking logic sees only the `ranking_guidance` and the paper text.  
- **Never** be vague with statements like “prefer empirical studies.” Instead say “paper must explicitly mention real or pilot-scale deployment with measured water metrics.”  
- **Never** allow guesswork. If you want fuzzy logic in irrigation, say, “Any fuzzy logic not used for irrigation scheduling is irrelevant—rank bottom.”

---

## 3. **Anatomy of a Proper YAML Search Request**

Every well-structured request has **five** main components:

1. **ID**  
   - A unique identifier, e.g., `- id: fuzzy_logic_irrigation_scheduling`.  
2. **Queries**  
   - An array of 5–10 (or more) queries that each contains domain-specific text.  
   - Example: “Fuzzy logic for agricultural irrigation scheduling with real data,” “Comparison of fuzzy irrigation control vs. threshold-based.”  
3. **Ranking guidance**  
   - A multi-line string specifying the **exact** domain constraints, top priorities, penalties, and irrelevances.  
4. **Exclusion criteria** (optional but strongly recommended)  
   - Boolean flags that automatically exclude or heavily penalize any paper not meeting your domain.  
5. **Information extraction**  
   - (Optional) Defines fields you want pulled from relevant papers, e.g. “water_savings,” “fuzzy_inference_method,” “scale_of_experiment,” etc.

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
      # ...
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

- **Add your entire domain context**: If you want fuzzy logic for irrigation scheduling, your query text should *explicitly* contain “fuzzy logic,” “irrigation scheduling,” and “agriculture.”  
- Use synonyms or near-synonyms if needed.  
- Example:  
  ```yaml
  queries:
    - "Fuzzy logic specifically for agricultural irrigation scheduling with real pilot-scale data"
    - "Mamdani or Sugeno fuzzy inference for water management in agriculture"
    - "Comparison of fuzzy-based irrigation to threshold triggers with measured water savings"
    ...
  ```
- If you merely say “fuzzy logic for water systems,” you risk returning random fuzzy logic in municipal water distribution or fishery tank controls. So **be ultra-specific**.

### 4.2 **Ranking Guidance: Your Non-Negotiable Linchpin**

During the ranking step, the system only sees:
1. The text of each retrieved paper  
2. The `ranking_guidance` you wrote  

**Hence** the ranking guidance must restate every crucial requirement—**including** the exact domain. Below are **good vs. bad** examples.

#### 🔴 **Bad Ranking Guidance (Vague)**

```yaml
ranking_guidance: >
  1. Must describe fuzzy inference methods.
  2. Prefer real experiments.
  3. High rank if comparing fuzzy logic to other methods.
```
- This says nothing about **agricultural irrigation**. The system might rank a “fuzzy inference for automobile braking system” paper highly because it meets #1, #2, and #3.

#### 🟢 **Excellent Ranking Guidance (Concrete & Forceful)**

```yaml
ranking_guidance: >
  ABSOLUTE DOMAIN REQUIREMENT:
    - Paper must explicitly describe fuzzy logic for agricultural irrigation scheduling
      or water management in farmland/horticulture.

  TOP PRIORITY CRITERIA:
    1. Fuzzy logic must be validated in real or pilot-scale field conditions measuring
       water usage, yield, or crop stress metrics.
    2. Must compare fuzzy scheduling with at least one conventional irrigation method
       (threshold-based, timer-based, PID, or manual).
    3. Must present explicit membership functions, rule sets, or defuzzification strategies.

  EXCLUSIONS OR PENALTIES:
    - Any paper describing fuzzy logic in a domain other than agricultural irrigation
      must rank at the bottom or be excluded entirely.
    - If purely theoretical or simulation with no real data, rank lower than those
      with actual field results.
    - If no explicit mention of irrigation scheduling, also rank at bottom.
```
- **No** guesswork. If it’s not about fuzzy logic **for** irrigation scheduling, it’s out.

---

## 5. **Side-by-Side Example**

Below is a **complete** example of a single request block, demonstrating the “explicitness” standard:

```yaml
- id: fuzzy_logic_irrigation_scheduling

  queries:
    - "Fuzzy logic specifically for agricultural irrigation scheduling with real field experiments"
    - "Mamdani or Sugeno fuzzy inference for water management in row crops, including pilot-scale data"
    - "Comparison of fuzzy-based irrigation scheduling vs. threshold triggers, measuring water savings"
    - "Quantitative results from fuzzy irrigation controllers in horticulture or field crops"
    - "Explicit membership function design for fuzzy irrigation control with yield or water metrics"

  ranking_guidance: >
    CRITICAL REQUIREMENT (NO EXCEPTIONS):
      - Papers must explicitly mention fuzzy logic methods for controlling or scheduling irrigation
        in agriculture (field, greenhouse, orchard, horticulture). If it's fuzzy logic in any
        unrelated domain, rank it near zero or exclude.

    TOP RANK FACTORS:
      1. Real or pilot-scale demonstration with measurable results (water usage, yield, stress metrics).
      2. Comparison to at least one standard irrigation method (threshold, timer, manual, etc.).
      3. Clear description of fuzzy inference approach (Mamdani, Sugeno, membership functions,
         defuzzification) specifically for irrigation.

    PENALTIES/LOW RANK:
      - Papers with only a conceptual or purely simulation approach (no real data) rank below
        those with actual tested data.
      - If fuzzy logic is used for some general purpose (like pest control or industrial process),
        with no mention of irrigation scheduling, it belongs at the bottom.

  exclusion_criteria:
    fuzzy_not_irrigation:
      type: boolean
      description: "Exclude if fuzzy logic is not explicitly about agricultural irrigation scheduling."

  information_extraction:
    fuzzy_inference_type:
      type: string
      description: "Which fuzzy method was used: Mamdani, Sugeno, Tsukamoto?"
    real_experiment_data:
      type: boolean
      description: "Whether the paper describes real or pilot-scale data"
    comparative_approach:
      type: boolean
      description: "Does the paper compare fuzzy to threshold or other conventional methods?"
    performance_metrics:
      type: string
      description: "Mentioned water savings, yield improvement, or other outcomes?"
```

Observe how:

- **Queries** specifically mention “agricultural irrigation scheduling” and “real field experiments,” etc.  
- **Ranking guidance** forbids “fuzzy logic in any other domain.”  
- **Exclusion criteria** adds an explicit boolean for quick rejection.  
- **Information extraction** clarifies which data to pull from top papers.

---

## 6. **Comparisons: Good vs. Bad Queries**

**Bad Query**: “IoT sensor networks in agriculture”  
- Too broad. Might retrieve papers about IoT in general farm monitoring, not necessarily irrigation scheduling.

**Better Query**: “IoT sensor networks specifically for real-time irrigation scheduling in crop fields with measured water savings”  
- Mentions IoT, irrigation scheduling, “real-time,” “crop fields,” “measured water savings.” Minimizes ambiguity.

---

## 7. **Exclusion Criteria**: The Quick Filter

If you know certain traits instantly disqualify a paper, define a boolean in `exclusion_criteria`. For instance:

```yaml
exclusion_criteria:
  not_irrigation:
    type: boolean
    description: "Paper does not address irrigation scheduling in agriculture at all."
  no_real_data:
    type: boolean
    description: "Paper is purely theoretical, no real or pilot-scale data."
```

Now the system can ask: “Does the paper fail the `not_irrigation` check? If yes, exclude it.” This ensures worthless papers never get near the top.

---

## 8. **Information Extraction**: Gleaning Key Data Points

If you want specific fields from the top papers (like “accuracy,” “water_savings,” or “cost_analysis”), define them under `information_extraction`. For instance:

```yaml
information_extraction:
  water_savings:
    type: float
    description: "Percentage of water savings reported in the study"
  yield_improvement:
    type: float
    description: "Percentage yield increase or improvement, if any"
  approach_details:
    type: string
    description: "Specific mention of how the approach is implemented"
```

---

## 9. **Putting It All Together: A “Full” Example**

Below is a more comprehensive snippet, combining global config plus a single request. (In actual usage, you might have multiple requests each with different domain instructions.)

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
    min_year: 2012
    max_year: 2025

requests:
  - id: fuzzy_logic_irrigation_scheduling
    queries:
      - "Fuzzy logic specifically for agricultural irrigation scheduling with real field trials"
      - "Comparisons of Mamdani fuzzy irrigation control vs threshold-based methods measuring water usage"
      - "Pilot-scale demonstration of fuzzy logic for crop water management, including yield metrics"
      - "Fuzzy membership function design for soil moisture and canopy temperature in irrigation scheduling"
      - "Quantitative performance results of fuzzy irrigation strategies in horticulture or row crops"
      - "Real-world adoption of fuzzy irrigation scheduling with data on water savings"
      - "Implementation details of fuzzy logic controllers for farmland water management"
      - "Empirical evaluation of fuzzy vs. manual irrigation with yield or water efficiency improvements"
    ranking_guidance: >
      MANDATORY DOMAIN RESTRICTION:
        - Paper MUST explicitly apply fuzzy logic to the scheduling or control of irrigation
          in an agricultural context (fields, greenhouses, horticulture, orchard).
        - Any fuzzy logic application not addressing irrigation water management is irrelevent,
          rank it at the bottom.

      TOP-RANK CRITERIA:
        1. Highest rank if real or pilot-scale data is explicitly provided: measured water usage,
           yield data, stress metrics, or soil moisture results.
        2. Extra priority if comparing fuzzy scheduling to other standard or conventional methods
           (timer-based, threshold, PID) with numeric performance metrics.
        3. Must detail membership functions, rules, or defuzzification steps specifically for
           irrigation scheduling. Vague references to “fuzzy logic” alone are insufficient.

      PENALTIES / LOWER RANK:
        - If only a theoretical or simulation approach with no real data, rank it lower than
          those with actual field or greenhouse experiments.
        - If the paper’s domain is not irrigation scheduling (pest control, fertilization, or
          an entirely different domain), place it near the bottom or exclude.

    exclusion_criteria:
      no_irrigation_context:
        type: boolean
        description: "Exclude if the paper does not explicitly apply fuzzy logic to irrigation scheduling."

    information_extraction:
      fuzzy_inference_type:
        type: string
        description: "Which fuzzy method is used? (Mamdani, Sugeno, etc.)"
      scale_of_study:
        type: string
        description: "Field-scale, pilot, greenhouse, or purely simulation?"
      performance_metrics:
        type: string
        description: "Mentioned water savings, yield improvement, or other numerical results?"
      comparison_with_baseline:
        type: boolean
        description: "Does it compare fuzzy scheduling to threshold/manual/PID methods?"
      membership_function_detail:
        type: boolean
        description: "Do they explicitly describe membership functions or defuzzification?"
```

---

## 10. **Most Common Failure Modes (and How This Guide Prevents Them)**

1. **Ranking Irrelevant Domains Highly**  
   - Caused by leaving out your domain in ranking guidance.  
   - **Solution**: “Strict domain requirement: must mention irrigation scheduling in agriculture.”  

2. **Failing to Demand Real Data**  
   - Caused by vague wording like “prefers empirical approach.”  
   - **Solution**: “Highest rank if real or pilot-scale data is explicitly provided. Otherwise, rank lower.”  

3. **Ending Up with No or Few Valid Papers**  
   - Possibly the domain is too narrow or your criteria are too strict. But typically, it’s safer to have stricter criteria than meaningless sprawl.  

4. **Overlooking Must-Have Performance Metrics**  
   - If you never mention “water savings or yield improvements,” you’ll get random “fuzzy logic, done.”  
   - **Solution**: In the ranking guidance, “papers must mention explicit performance metrics (water usage, yield).”  

---

## 11. **Summary: The Hard Rules**

1. **Start from the top**: Provide the reason for your domain constraints.  
2. **Queries**: Repeatedly mention your domain and must-have aspects.  
3. **Ranking Guidance**: 
   - At least a paragraph that says “Any paper not about X is worthless—bottom rank.”  
   - Then a list of explicit bullet points specifying top-rank conditions.  
   - Then a list of explicit penalty conditions.  
4. **(Optional) Exclusion Criteria**:  
   - If you want an auto-flag for “No mention of irrigation,” define it and label it as a reason to exclude.  
5. **Information Extraction**:  
   - For each data point you want, define a typed field.  

**Everything** must be spelled out. **Never** assume the system will “get it.” If you want something, **say it**—with unstoppable clarity.

---

## 12. **Final Takeaway**

This guide is meant to be your authoritative blueprint for constructing YAML-based academic search queries. **Never** cut corners on specificity. The success or failure of your entire literature review hinges on how precisely you specify your domain constraints in the ranking guidance (and queries). If you do it right—**with the level of detail shown above**—you will get high-quality, relevant results every time. If you do it wrong—**even just a little**—the search collapses, returning random irrelevance.

Therefore:

> **Write your ranking guidance and queries as though an extremely obtuse, obstinate, hyper-literal agent will interpret them with zero background knowledge.**  
> If you do this, you will produce an unambiguous, domain-locked search that excludes unrelated junk.  

Follow each section in this guide meticulously and you’ll reap the benefits of a focused, highly efficient academic literature search.