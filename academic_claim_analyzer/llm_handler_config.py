# academic_claim_analyzer/llm_handler_config.py

import os
from llmhandler.api_handler import UnifiedLLMHandler

# Set the default model from the environment, or use google-gla:gemini-2.0-flash-001 as fallback.
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "google-gla:gemini-2.0-flash-001")

# Initialize a global LLM handler with 1500 rpm and the default model.
LLM_HANDLER = UnifiedLLMHandler(requests_per_minute=1500, default_model=DEFAULT_LLM_MODEL)
