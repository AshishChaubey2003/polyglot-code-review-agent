"""
Centralized configuration and logging for the Polyglot AI Code Review &
Repair Agent.

Phase 1 scope: environment loading + logging only. Which provider/model
to use lives here as plain env-driven constants; HOW to call that
provider lives in services/llm_service.py, so swapping providers later
never touches this file.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Behavior verification (verification/tests.py) runs pytest against
# user-supplied code in a subprocess. OFF by default -- see that
# module's docstring for why. Only set true in an environment you trust.
ALLOW_TEST_EXECUTION = os.getenv("ALLOW_TEST_EXECUTION", "false").lower() == "true"

# RAG knowledge base location (Phase 5+).
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "data/documents")
VECTOR_INDEX_DIR = os.getenv("VECTOR_INDEX_DIR", "data/indexes")


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger("polyglot_reviewer")


logger = configure_logging()


def is_configured() -> bool:
    """True if the currently selected provider has the credentials it needs.

    Only 'groq' exists in Phase 1. Adding a provider means adding one
    branch here and one branch in LLMService._build_client() -- nothing
    else in the app needs to change.
    """
    if LLM_PROVIDER == "groq":
        return bool(GROQ_API_KEY)
    return False
