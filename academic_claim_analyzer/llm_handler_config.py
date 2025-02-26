# academic_claim_analyzer/llm_handler_config.py

import os
from llmhandler.api_handler import UnifiedLLMHandler

# Initialize a global LLM handler with 1500 rpm and the model directly from env
llm_handler = UnifiedLLMHandler(
    requests_per_minute=1500, 
    default_model=os.getenv("DEFAULT_LLM_MODEL")
)