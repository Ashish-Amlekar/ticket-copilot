"""All configuration comes from environment variables (12-factor style).

Nothing in the code hardcodes a model, a prompt version or a path, so the same
image can run against a local Ollama model in dev and a hosted API in prod.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# LiteLLM model string. Examples:
#   ollama/mistral            local, no API key
#   gpt-4o-mini               OpenAI
#   anthropic/claude-haiku-5-5   Anthropic
LLM_MODEL = os.getenv("LLM_MODEL", "ollama/mistral")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))  # re-asks after invalid JSON

# Which versioned prompt file to use: prompts/triage/<PROMPT_VERSION>.yaml
PROMPT_NAME = os.getenv("PROMPT_NAME", "triage")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")

# Knowledge base: a JSONL file of chunks produced by scripts/ingest_kb.py
KB_PATH = Path(os.getenv("KB_PATH", ROOT / "data" / "sample_kb" / "chunks.jsonl"))
TOP_K = int(os.getenv("TOP_K", "4"))

# "bm25" is lexical only (fast, no model download, used in CI).
# "hybrid" adds dense embeddings + reciprocal rank fusion.
RETRIEVER = os.getenv("RETRIEVER", "bm25")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Observability: one JSON line per request (swap for Langfuse/OTel later).
LOG_DIR = Path(os.getenv("LOG_DIR", ROOT / "logs"))