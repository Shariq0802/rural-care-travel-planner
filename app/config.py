import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://care:care@localhost:5432/care")

# Which extractor /extract uses: "llm" (Ollama) or "baseline" (simple rules, for comparison)
EXTRACTOR = os.getenv("EXTRACTOR", "llm")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))
